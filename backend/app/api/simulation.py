"""Simulation / demo control endpoints.

These live under a clearly-labelled Demo/Simulation surface — there is no
separate control-center role. They drive the simulated live operations only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Train, TrainStatus
from app.schemas import SimulationStatusOut
from app.simulation.engine import engine

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class TrainRef(BaseModel):
    train_id: int


class EventRef(BaseModel):
    train_id: int
    event_type: str = "congestion"


def _train_or_404(db: Session, train_id: int) -> Train:
    train = db.get(Train, train_id)
    if not train:
        raise HTTPException(status_code=404, detail="Train not found")
    return train


@router.post("/start")
async def start(ref: TrainRef, db: Session = Depends(get_db)):
    train = _train_or_404(db, ref.train_id)
    await engine.start(train.id, train.train_number)
    return {"ok": True, "state": "running", "train_id": train.id}


@router.post("/pause")
async def pause(ref: TrainRef, db: Session = Depends(get_db)):
    train = _train_or_404(db, ref.train_id)
    await engine.pause(train.id, train.train_number)
    return {"ok": True, "state": "paused", "train_id": train.id}


@router.post("/resume")
async def resume(ref: TrainRef, db: Session = Depends(get_db)):
    train = _train_or_404(db, ref.train_id)
    await engine.resume(train.id, train.train_number)
    return {"ok": True, "state": "running", "train_id": train.id}


@router.post("/stop")
async def stop(ref: TrainRef, db: Session = Depends(get_db)):
    train = _train_or_404(db, ref.train_id)
    await engine.stop(train.id, train.train_number)
    return {"ok": True, "state": "stopped", "train_id": train.id}


@router.post("/reset")
async def reset(ref: TrainRef, db: Session = Depends(get_db)):
    train = _train_or_404(db, ref.train_id)
    await engine.reset(train.id, train.train_number)
    return {"ok": True, "state": "reset", "train_id": train.id}


@router.post("/congestion")
async def congestion(ref: EventRef, db: Session = Depends(get_db)):
    train = _train_or_404(db, ref.train_id)
    result = await engine.inject_event(train.id, train.train_number, ref.event_type)
    return {"ok": True, **result}


@router.get("/status", response_model=SimulationStatusOut)
def status(train_id: int, db: Session = Depends(get_db)):
    train = _train_or_404(db, train_id)
    state, tick, is_live = engine.state_of(db, train.id)
    return SimulationStatusOut(train_id=train.id, state=state, tick=tick, is_live=is_live)
