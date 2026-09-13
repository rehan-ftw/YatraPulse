"""YatraPulse FastAPI application entrypoint."""
from __future__ import annotations

import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.api import alerts, simulation, trains
from app.config import get_settings
from app.data import seed_data as sd
from app.db import SessionLocal
from app.models import Station, Train, TrainRoute
from app.simulation.engine import engine
from app.simulation.ws import manager


def _select_live_fleet(db, target: int = 12) -> list[tuple[int, str]]:
    """Resolve the curated live-fleet train numbers that exist with usable
    coordinates, topping up from the catalogue to reach `target` trains."""
    SrcS = aliased(Station)
    DstS = aliased(Station)

    def has_coords(t: Train) -> bool:
        s, d = t.source_station, t.destination_station
        return (
            s and d
            and s.latitude is not None and s.longitude is not None
            and d.latitude is not None and d.longitude is not None
        )

    chosen: list[tuple[int, str]] = []
    seen: set[int] = set()
    for num in sd.LIVE_FLEET_NUMBERS:
        t = db.scalar(select(Train).where(Train.train_number == num))
        if t and t.id not in seen and has_coords(t):
            chosen.append((t.id, t.train_number))
            seen.add(t.id)

    if len(chosen) < target:
        rows = db.scalars(
            select(Train)
            .join(SrcS, Train.source_station_id == SrcS.id)
            .join(DstS, Train.destination_station_id == DstS.id)
            .join(TrainRoute, TrainRoute.train_id == Train.id)
            .where(
                Train.is_demo.is_(False),
                SrcS.latitude.is_not(None),
                DstS.latitude.is_not(None),
                Train.id.not_in(seen or {-1}),
            )
            .order_by(Train.train_number)
            .limit(target * 3)
        ).all()
        for t in rows:
            if len(chosen) >= target:
                break
            if t.id not in seen:
                chosen.append((t.id, t.train_number))
                seen.add(t.id)
    return chosen[:target]

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup, put the flagship demo train into a perpetual LIVE journey so
    the app always shows a train being tracked live (labelled 'Simulated live
    operations'). This does not require any external feed or API key."""
    demo_number = next((t["number"] for t in sd.TRAINS if t.get("role") == "demo"), None)
    if demo_number:
        try:
            with SessionLocal() as db:
                train = db.scalar(select(Train).where(Train.train_number == demo_number))
                demo = (train.id, train.train_number) if train else None
            if demo:
                # reset() restores the pristine start AND (for demo trains) starts
                # the perpetual live loop.
                await engine.reset(demo[0], demo[1])
        except Exception:
            # never let auto-start break the app (e.g. DB not seeded yet)
            pass

    # Put a fleet of real catalogue trains into perpetual simulated live journeys
    # so the Live Status page shows many trains being tracked live.
    try:
        with SessionLocal() as db:
            fleet = _select_live_fleet(db, target=12)
        for train_id, number in fleet:
            await engine.start(train_id, number, loop=True)
    except Exception:
        pass
    yield
    # graceful shutdown: halt any running simulation tasks
    for tid in list(engine._tasks.keys()):  # noqa: SLF001
        with contextlib.suppress(Exception):
            await engine._halt_task(tid)  # noqa: SLF001


app = FastAPI(
    title="YatraPulse API",
    version="1.0.0",
    description="Dynamic ETA for coaching trains — historical data + simulated live operations.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trains.router)
app.include_router(alerts.router)
app.include_router(simulation.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "yatrapulse"}


@app.websocket("/ws/live-updates")
async def live_updates(ws: WebSocket):
    await manager.connect(ws)
    try:
        # send a hello so clients can confirm the live connection
        await ws.send_json({"type": "CONNECTED", "message": "live updates connected"})
        while True:
            # we don't require inbound messages; keep the socket open
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)
