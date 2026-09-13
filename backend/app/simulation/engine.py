"""Lightweight, deterministic-enough journey simulation.

Runs an asyncio movement loop per active train, pushing TRAIN_MOVEMENT_UPDATED
messages over the WebSocket. Operational events (congestion, signal hold,
station delay) recalculate the ETA through the model-agnostic predictor and
fan out ETA_UPDATED + DOWNSTREAM_IMPACT_UPDATED messages.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import OperationalEvent, RouteStation, SimulationState, Station, Train, TrainStatus
from app.services.geo import interpolate
from app.services.impact import compute_downstream_for_train
from app.services.status import init_simulation_start, predict_for_status, reset_train
from app.simulation import ws

TICK_SECONDS = 2.0
STEP_PER_TICK = 0.12  # fraction of a segment advanced per tick (~17s per segment)

EVENT_DEFAULTS = {
    "congestion": ("Heavy congestion detected near {loc}", None),  # None -> configured dwell
    "signal_hold": ("Signal hold near {loc}", 4),
    "station_delay": ("Extended station dwell at {loc}", 5),
}


@dataclass
class RoutePoint:
    station_id: int
    code: str
    name: str
    lat: float
    lng: float


class SimulationEngine:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._pause_events: dict[int, asyncio.Event] = {}
        self._stop_flags: dict[int, bool] = {}
        # demo trains loop their journey forever so they are always "live"
        self._loop_ids: set[int] = set()

    def _arm_task(self, train_id: int, train_number: str, loop: bool) -> None:
        """(Re)create the movement task for a train."""
        self._stop_flags[train_id] = False
        ev = asyncio.Event()
        ev.set()
        self._pause_events[train_id] = ev
        if loop:
            self._loop_ids.add(train_id)
        else:
            self._loop_ids.discard(train_id)
        self._tasks[train_id] = asyncio.create_task(self._run(train_id, train_number))

    # --- route geometry -----------------------------------------------------
    def _load_points(self, db: Session, train_id: int) -> list[RoutePoint]:
        rows = db.execute(
            select(RouteStation, Station)
            .join(Station, RouteStation.station_id == Station.id)
            .where(RouteStation.train_id == train_id)
            .order_by(RouteStation.sequence_number)
        ).all()
        return [
            RoutePoint(s.id, s.station_code, s.station_name, s.latitude, s.longitude)
            for _, s in rows
            if s.latitude is not None and s.longitude is not None
        ]

    def _set_sim_state(self, db: Session, train_id: int, state: str) -> None:
        sim = db.scalar(select(SimulationState).where(SimulationState.train_id == train_id))
        if sim:
            sim.state = state
            db.commit()

    def state_of(self, db: Session, train_id: int) -> tuple[str, int, bool]:
        sim = db.scalar(select(SimulationState).where(SimulationState.train_id == train_id))
        status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train_id))
        state = sim.state if sim else "idle"
        tick = sim.tick if sim else 0
        is_live = bool(status.is_live) if status else False
        return state, tick, is_live

    # --- lifecycle ----------------------------------------------------------
    async def start(self, train_id: int, train_number: str, loop: bool | None = None) -> None:
        if train_id in self._tasks and not self._tasks[train_id].done():
            # already running/paused -> ensure resumed
            self._pause_events.get(train_id, asyncio.Event()).set()
            return
        with SessionLocal() as db:
            train = db.get(Train, train_id)
            is_demo = bool(train.is_demo) if train else False
            if train:
                init_simulation_start(db, train)
            self._set_sim_state(db, train_id, "running")
        # `loop` overrides; otherwise demo trains loop forever (perpetually live)
        do_loop = is_demo if loop is None else loop
        self._arm_task(train_id, train_number, loop=do_loop)
        await ws.manager.broadcast(ws.simulation_state_changed(train_id, train_number, "running"))

    async def pause(self, train_id: int, train_number: str) -> None:
        ev = self._pause_events.get(train_id)
        if ev:
            ev.clear()
        with SessionLocal() as db:
            self._set_sim_state(db, train_id, "paused")
        await ws.manager.broadcast(ws.simulation_state_changed(train_id, train_number, "paused"))

    async def resume(self, train_id: int, train_number: str) -> None:
        ev = self._pause_events.get(train_id)
        if ev:
            ev.set()
        with SessionLocal() as db:
            self._set_sim_state(db, train_id, "running")
        await ws.manager.broadcast(ws.simulation_state_changed(train_id, train_number, "running"))

    async def _halt_task(self, train_id: int) -> None:
        self._stop_flags[train_id] = True
        ev = self._pause_events.get(train_id)
        if ev:
            ev.set()  # unblock so the loop can observe the stop flag
        task = self._tasks.get(train_id)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.pop(train_id, None)
        self._loop_ids.discard(train_id)

    async def stop(self, train_id: int, train_number: str) -> None:
        """Halt movement but keep the train where it is (state stays visible,
        just no longer live)."""
        await self._halt_task(train_id)
        with SessionLocal() as db:
            status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train_id))
            if status:
                status.is_live = False
                db.commit()
            self._set_sim_state(db, train_id, "idle")
        await ws.manager.broadcast(ws.simulation_state_changed(train_id, train_number, "stopped"))

    async def reset(self, train_id: int, train_number: str) -> None:
        """Halt and restore the train to its pristine starting state so the demo
        can be replayed cleanly (demo -> seeded corridor + downstream; imported ->
        timetable-only). Demo trains immediately resume their perpetual live
        journey so they are always tracked."""
        await self._halt_task(train_id)
        with SessionLocal() as db:
            train = db.get(Train, train_id)
            is_demo = bool(train.is_demo) if train else False
            if train:
                reset_train(db, train)
            if is_demo:
                # re-arm the live journey from the pristine starting point
                init_simulation_start(db, train)
                self._set_sim_state(db, train_id, "running")
            else:
                self._set_sim_state(db, train_id, "idle")
        if is_demo:
            self._arm_task(train_id, train_number, loop=True)
        await ws.manager.broadcast(ws.simulation_state_changed(train_id, train_number, "reset"))

    # --- movement loop ------------------------------------------------------
    async def _run(self, train_id: int, train_number: str) -> None:
        with SessionLocal() as db:
            points = self._load_points(db, train_id)
        if len(points) < 2:
            return
        try:
            while not self._stop_flags.get(train_id):
                await self._pause_events[train_id].wait()
                if self._stop_flags.get(train_id):
                    break

                msg = None
                with SessionLocal() as db:
                    status = db.scalar(
                        select(TrainStatus).where(TrainStatus.train_id == train_id)
                    )
                    sim = db.scalar(
                        select(SimulationState).where(SimulationState.train_id == train_id)
                    )
                    seg = status.segment_index
                    if seg >= len(points) - 1:
                        if train_id in self._loop_ids:
                            # perpetual demo train: wrap back to the origin and
                            # keep running so it is always live
                            status.segment_index = seg = 0
                            status.segment_progress = 0.0
                        else:
                            # arrived at destination
                            status.is_live = False
                            status.segment_progress = 1.0
                            if sim:
                                sim.state = "arrived"
                            db.commit()
                            await ws.manager.broadcast(
                                ws.simulation_state_changed(train_id, train_number, "arrived")
                            )
                            break

                    status.segment_progress += STEP_PER_TICK
                    if status.segment_progress >= 1.0 - 1e-9:
                        status.segment_progress = 0.0
                        status.segment_index = seg = seg + 1
                    nxt_idx = seg + 1
                    a, b = points[seg], points[min(nxt_idx, len(points) - 1)]
                    lat, lng = interpolate(
                        a.lat, a.lng, b.lat, b.lng, status.segment_progress
                    )
                    status.current_lat, status.current_lng = lat, lng
                    status.current_station_id = a.station_id
                    status.next_station_id = (
                        points[nxt_idx].station_id if nxt_idx < len(points) else None
                    )
                    status.is_live = True
                    if sim:
                        sim.tick += 1
                    cur_name = a.name
                    nxt_name = points[nxt_idx].name if nxt_idx < len(points) else None
                    db.commit()
                    msg = ws.train_movement_updated(
                        train_id, train_number, lat, lng, cur_name, nxt_name
                    )
                if msg:
                    await ws.manager.broadcast(msg)
                await asyncio.sleep(TICK_SECONDS)
        except asyncio.CancelledError:
            pass

    # --- operational events -------------------------------------------------
    async def inject_event(self, train_id: int, train_number: str, event_type: str) -> dict:
        settings = get_settings()
        template, default_impact = EVENT_DEFAULTS.get(
            event_type, EVENT_DEFAULTS["congestion"]
        )
        impact = (
            settings.eta_congestion_dwell if default_impact is None else default_impact
        )

        with SessionLocal() as db:
            train = db.scalar(select(Train).where(Train.id == train_id))
            status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train_id))
            previous_eta = status.current_eta
            loc = (
                status.next_station.station_name
                if status.next_station
                else (status.current_station.station_name if status.current_station else "the section ahead")
            )
            reason = template.format(loc=loc)

            db.add(
                OperationalEvent(
                    train_id=train_id,
                    type=event_type,
                    location=loc,
                    impact_minutes=impact,
                    reason=reason,
                )
            )
            status.delay_minutes = (status.delay_minutes or 0) + impact
            db.commit()

            # recompute ETA through the model-agnostic predictor
            result = predict_for_status(db, status)
            status.current_eta = result.current_eta
            status.status_text = (
                "ON TIME" if result.delay_minutes <= 0 else f"{result.delay_minutes} MIN LATE"
            )
            db.commit()
            new_eta = status.current_eta
            delay = status.delay_minutes

            affected = compute_downstream_for_train(db, train, impact, apply=True)
            train_name = train.train_name

        # broadcast the fan-out
        await ws.manager.broadcast(
            ws.operational_event(event_type, train_id, train_number, loc, impact, reason)
        )
        await ws.manager.broadcast(
            ws.eta_updated(train_id, train_number, previous_eta, new_eta, delay, reason)
        )
        await ws.manager.broadcast(
            ws.downstream_impact_updated(train_number, train_name, reason, affected)
        )
        return {
            "event_type": event_type,
            "location": loc,
            "impact_minutes": impact,
            "reason": reason,
            "previous_eta": previous_eta,
            "new_eta": new_eta,
            "delay_minutes": delay,
            "affected_trains": affected,
        }


engine = SimulationEngine()
