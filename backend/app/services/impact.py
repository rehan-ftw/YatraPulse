"""Simulated downstream impact propagation.

A deliberately simple, transparent model: when a source train is delayed by
`source_impact` minutes, each trailing train on the same corridor absorbs a
fraction of that delay given by a configurable propagation factor. This is
labelled SIMULATED IMPACT everywhere — it is not a validated dispatch model.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.seed_data import DOWNSTREAM_CHAIN
from app.models import Train, TrainStatus
from app.services.eta import status_text_for
from app.services.geo import hhmm_to_min, min_to_hhmm


def compute_downstream_impact(
    db: Session, source_impact: int, apply: bool = True
) -> list[dict]:
    """Return (and optionally apply to train_status) the downstream chain."""
    settings = get_settings()
    factors = settings.downstream_factor_list
    affected: list[dict] = []

    for i, number in enumerate(DOWNSTREAM_CHAIN):
        factor = factors[i] if i < len(factors) else factors[-1] if factors else 0.0
        added = round(source_impact * factor)
        if added <= 0:
            continue

        train = db.scalar(select(Train).where(Train.train_number == number))
        if not train:
            continue
        status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
        if not status:
            continue

        new_eta = status.current_eta
        if apply:
            status.delay_minutes = (status.delay_minutes or 0) + added
            base = hhmm_to_min(status.scheduled_arrival_dest)
            if base is not None:
                new_eta = min_to_hhmm(base + status.delay_minutes)
                status.current_eta = new_eta
            status.status_text = status_text_for(status.delay_minutes)
        else:
            base = hhmm_to_min(status.scheduled_arrival_dest)
            if base is not None:
                new_eta = min_to_hhmm(base + (status.delay_minutes or 0) + added)

        affected.append(
            {
                "train_number": train.train_number,
                "train_name": train.train_name,
                "added_delay_minutes": added,
                "new_eta": new_eta,
            }
        )

    if apply:
        db.commit()
    return affected


def _apply_factor(status: TrainStatus, added: int) -> str | None:
    base = hhmm_to_min(status.scheduled_arrival_dest)
    if base is None:
        return status.current_eta
    return min_to_hhmm(base + (status.delay_minutes or 0) + added)


def compute_downstream_for_train(
    db: Session, train: Train, source_impact: int, apply: bool = True
) -> list[dict]:
    """Downstream impact for ANY train.

    - Curated demo corridor (12952): uses the real, hand-picked trailing chain and
      applies the delay so those trains' own pages reflect it.
    - Other trains: a clearly-labelled SIMULATED propagation onto up to N other
      real trains sharing the same destination corridor. We do NOT persist these
      (apply is ignored) so we never invent a lasting delay on a timetable train.
    """
    if train.is_demo:
        return compute_downstream_impact(db, source_impact, apply=apply)

    settings = get_settings()
    factors = settings.downstream_factor_list
    others = db.scalars(
        select(Train)
        .where(
            Train.destination_station_id == train.destination_station_id,
            Train.id != train.id,
        )
        .order_by(Train.train_number)
        .limit(len(factors))
    ).all()

    affected: list[dict] = []
    for i, other in enumerate(others):
        factor = factors[i] if i < len(factors) else (factors[-1] if factors else 0.0)
        added = round(source_impact * factor)
        if added <= 0:
            continue
        st = db.scalar(select(TrainStatus).where(TrainStatus.train_id == other.id))
        new_eta = _apply_factor(st, added) if st else None
        affected.append(
            {
                "train_number": other.train_number,
                "train_name": other.train_name,
                "added_delay_minutes": added,
                "new_eta": new_eta,
            }
        )
    return affected
