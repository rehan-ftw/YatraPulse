"""Helpers that tie the ORM state to the model-agnostic ETA predictor, plus a
reset-to-seed used to make the demo repeatable."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.data import seed_data as sd
from app.models import (
    HistoricalDelay,
    OperationalEvent,
    RouteStation,
    SimulationState,
    Station,
    Train,
    TrainStatus,
)
from app.services.eta import ETAContext, ETAResult, active_predictor, status_text_for
from app.config import get_settings
from app.services.geo import hhmm_to_min, min_to_hhmm


def operational_impact(db: Session, train_id: int) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(OperationalEvent.impact_minutes), 0)).where(
            OperationalEvent.train_id == train_id
        )
    )
    return int(total or 0)


def latest_reason(db: Session, train_id: int) -> str:
    ev = db.scalar(
        select(OperationalEvent)
        .where(OperationalEvent.train_id == train_id)
        .order_by(OperationalEvent.created_at.desc())
        .limit(1)
    )
    return ev.reason if ev else "Running to schedule"


def historical_avg_at_next(db: Session, status: TrainStatus) -> float:
    if not status.next_station_id:
        return 0.0
    hd = db.scalar(
        select(HistoricalDelay).where(
            HistoricalDelay.train_id == status.train_id,
            HistoricalDelay.station_id == status.next_station_id,
        )
    )
    return hd.average_delay_minutes if hd else 0.0


def predict_for_status(db: Session, status: TrainStatus) -> ETAResult:
    """Build an ETAContext from current state and run the active predictor."""
    op_impact = operational_impact(db, status.train_id)
    baseline_delay = (status.delay_minutes or 0) - op_impact
    ctx = ETAContext(
        scheduled_arrival=status.scheduled_arrival_dest,
        current_delay=baseline_delay,
        operational_impact=op_impact,
        historical_avg_delay=historical_avg_at_next(db, status),
        historical_weight=get_settings().eta_historical_weight,
        next_station=status.next_station.station_name if status.next_station else None,
        reason=latest_reason(db, status.train_id),
    )
    return active_predictor.predict(ctx)


def reset_train_to_seed(db: Session, train_number: str) -> None:
    """Restore a train's live status to its seeded initial state and clear its
    operational events. Used by STOP so the demo can be replayed cleanly."""
    spec = next((t for t in sd.TRAINS if t["number"] == train_number), None)
    if not spec:
        return
    train = db.scalar(select(Train).where(Train.train_number == train_number))
    if not train:
        return

    db.execute(delete(OperationalEvent).where(OperationalEvent.train_id == train.id))

    route = spec["route"]
    route_codes = [r[0] for r in route]
    code_to_station = {
        s.station_code: s
        for s in db.scalars(select(Station).where(Station.station_code.in_(route_codes)))
    }
    cur = code_to_station[spec["current_code"]]
    nxt = code_to_station.get(spec["next_code"]) if spec.get("next_code") else None
    sched_dest = route[-1][1] or route[-1][2]
    delay = int(spec["delay"])
    eta = min_to_hhmm((hhmm_to_min(sched_dest) or 0) + delay) if sched_dest else None

    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    status.current_station_id = cur.id
    status.next_station_id = nxt.id if nxt else None
    status.current_lat = cur.latitude
    status.current_lng = cur.longitude
    status.segment_index = route_codes.index(spec["current_code"])
    status.segment_progress = 0.0
    status.delay_minutes = delay
    status.scheduled_arrival_dest = sched_dest
    status.current_eta = eta
    status.status_text = status_text_for(delay)
    status.is_live = False
    status.source = "SIMULATED"

    sim = db.scalar(select(SimulationState).where(SimulationState.train_id == train.id))
    if sim:
        sim.state = "idle"
        sim.tick = 0
    db.commit()


def reset_scheduled(db: Session, train: Train) -> None:
    """Restore an imported (catalogue) train to honest timetable-only state:
    no live position, no invented delay — just the scheduled arrival."""
    db.execute(delete(OperationalEvent).where(OperationalEvent.train_id == train.id))
    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    if status:
        status.current_station_id = None
        status.next_station_id = None
        status.current_lat = None
        status.current_lng = None
        status.segment_index = 0
        status.segment_progress = 0.0
        status.delay_minutes = 0
        status.current_eta = status.scheduled_arrival_dest
        status.status_text = "SCHEDULED"
        status.is_live = False
        status.source = "SCHEDULED"
    sim = db.scalar(select(SimulationState).where(SimulationState.train_id == train.id))
    if sim:
        sim.state = "idle"
        sim.tick = 0
    db.commit()


def reset_train(db: Session, train: Train) -> None:
    """Reset any train to its pristine starting state (demo -> seeded corridor,
    imported -> timetable-only)."""
    if train.is_demo:
        reset_demo_and_downstream(db)
    else:
        reset_scheduled(db, train)


def init_simulation_start(db: Session, train: Train) -> None:
    """Prepare a train for a simulated journey. Demo trains keep their curated
    starting position; imported trains begin at their origin. Either way the
    state becomes SIMULATED + live."""
    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    if not status:
        return
    if not train.is_demo:
        # begin a fresh simulated run from the origin (no fabricated prior delay)
        db.execute(delete(OperationalEvent).where(OperationalEvent.train_id == train.id))
        rows = db.execute(
            select(RouteStation, Station)
            .join(Station, RouteStation.station_id == Station.id)
            .where(RouteStation.train_id == train.id)
            .order_by(RouteStation.sequence_number)
        ).all()
        if rows:
            first_rs, first_st = rows[0]
            status.current_station_id = first_st.id
            status.next_station_id = rows[1][1].id if len(rows) > 1 else None
            status.current_lat = first_st.latitude
            status.current_lng = first_st.longitude
            status.segment_index = 0
            status.segment_progress = 0.0
            status.delay_minutes = 0
            status.current_eta = status.scheduled_arrival_dest
            status.status_text = status_text_for(0)
    status.is_live = True
    status.source = "SIMULATED"
    db.commit()


def reset_demo_and_downstream(db: Session) -> None:
    demo = next((t for t in sd.TRAINS if t["role"] == "demo"), None)
    if demo:
        reset_train_to_seed(db, demo["number"])
    for number in sd.DOWNSTREAM_CHAIN:
        reset_train_to_seed(db, number)
