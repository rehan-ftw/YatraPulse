"""Passenger-facing alerts derived from operational events."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import OperationalEvent, Train, TrainStatus
from app.schemas import AlertOut
from app.services.geo import hhmm_to_min, min_to_hhmm

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

TITLES = {
    "congestion": "Congestion detected",
    "signal_hold": "Signal hold",
    "station_delay": "Station delay",
}


@router.get("", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db)):
    events = db.scalars(
        select(OperationalEvent).order_by(OperationalEvent.created_at.asc())
    ).all()

    # reconstruct cumulative delay per train to derive previous/new ETA
    cumulative: dict[int, int] = {}
    train_cache: dict[int, Train] = {}
    sched_cache: dict[int, str | None] = {}
    alerts: list[AlertOut] = []

    for ev in events:
        train = train_cache.get(ev.train_id)
        if train is None:
            train = db.get(Train, ev.train_id)
            train_cache[ev.train_id] = train
            status = db.scalar(
                select(TrainStatus).where(TrainStatus.train_id == ev.train_id)
            )
            sched_cache[ev.train_id] = status.scheduled_arrival_dest if status else None

        sched = sched_cache[ev.train_id]
        before = cumulative.get(ev.train_id, 0)
        after = before + ev.impact_minutes
        cumulative[ev.train_id] = after

        prev_eta = min_to_hhmm((hhmm_to_min(sched) or 0) + before) if sched else None
        new_eta = min_to_hhmm((hhmm_to_min(sched) or 0) + after) if sched else None

        alerts.append(
            AlertOut(
                id=ev.id,
                type=ev.type,
                train_number=train.train_number if train else "",
                train_name=train.train_name if train else "",
                title=TITLES.get(ev.type, "Journey update"),
                reason=ev.reason,
                impact_minutes=ev.impact_minutes,
                previous_eta=prev_eta,
                new_eta=new_eta,
                timestamp=ev.created_at,
            )
        )

    alerts.reverse()  # newest first
    return alerts
