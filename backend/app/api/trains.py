"""Passenger-facing train endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.db import get_db
from app.models import HistoricalDelay, RouteStation, Station, Train, TrainRoute, TrainStatus
from app.providers import resolve as resolve_state
from app.schemas import (
    AffectedTrainOut,
    DownstreamImpactOut,
    ETAOut,
    HistoricalDelayOut,
    RouteStopOut,
    StationOut,
    TrainDetailOut,
    TrainStatusOut,
    TrainSummary,
)
from app.services.impact import compute_downstream_for_train
from app.services.status import latest_reason, predict_for_status

router = APIRouter(prefix="/api/trains", tags=["trains"])


def _summary(db: Session, train: Train, status: TrainStatus | None = None) -> TrainSummary:
    if status is None:
        status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    st = resolve_state(train, status)
    return TrainSummary(
        id=train.id,
        train_number=train.train_number,
        train_name=train.train_name,
        source=train.source_station.station_name,
        destination=train.destination_station.station_name,
        status_text=st.status_text,
        delay_minutes=st.delay_minutes,
        current_station=st.current_station,
        next_station=st.next_station,
        current_eta=st.current_eta,
        is_live=st.is_live,
        data_source=st.source,
        tracked=st.tracked,
    )


def _status_out(train: Train, status: TrainStatus) -> TrainStatusOut:
    st = resolve_state(train, status)
    return TrainStatusOut(
        train_id=train.id,
        train_number=train.train_number,
        train_name=train.train_name,
        source=train.source_station.station_name,
        destination=train.destination_station.station_name,
        current_station=st.current_station,
        next_station=st.next_station,
        current_lat=status.current_lat,
        current_lng=status.current_lng,
        delay_minutes=st.delay_minutes,
        scheduled_arrival_dest=status.scheduled_arrival_dest,
        current_eta=st.current_eta,
        status_text=st.status_text,
        is_live=st.is_live,
        last_updated=status.last_updated,
        data_source=st.source,
        tracked=st.tracked,
    )


def _get_train_or_404(db: Session, train_id: int) -> Train:
    train = db.get(Train, train_id)
    if not train:
        raise HTTPException(status_code=404, detail="Train not found")
    return train


@router.get("", response_model=list[TrainSummary])
def list_trains(db: Session = Depends(get_db)):
    """Trains worth surfacing on Home / Live Status: the curated demo trains and
    anything currently being simulated. (The full catalogue is via /search.)"""
    trains = db.scalars(
        select(Train)
        .join(TrainStatus, TrainStatus.train_id == Train.id)
        .where(or_(Train.is_demo.is_(True), TrainStatus.is_live.is_(True)))
        .order_by(Train.is_demo.desc(), Train.train_number)
    ).all()
    return [_summary(db, t) for t in trains]


@router.get("/search", response_model=list[TrainSummary])
def search_trains(
    q: str = Query("", description="train number (full/partial), name, source or destination"),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = q.strip()
    if not q:
        # empty query: show the curated demo trains rather than 5,000+ rows
        trains = db.scalars(
            select(Train).where(Train.is_demo.is_(True)).order_by(Train.train_number)
        ).all()
        return [_summary(db, t) for t in trains]

    like = f"%{q}%"
    SrcS = aliased(Station)
    DstS = aliased(Station)
    stmt = (
        select(Train)
        .join(SrcS, Train.source_station_id == SrcS.id)
        .join(DstS, Train.destination_station_id == DstS.id)
        .where(
            or_(
                Train.train_number.like(like),
                Train.train_name.like(like),
                SrcS.station_name.like(like),
                DstS.station_name.like(like),
            )
        )
        .order_by(Train.is_demo.desc(), Train.train_number)
        .limit(limit)
    )
    trains = db.scalars(stmt).all()
    return [_summary(db, t) for t in trains]


@router.get("/{train_id}", response_model=TrainDetailOut)
def train_detail(train_id: int, db: Session = Depends(get_db)):
    train = _get_train_or_404(db, train_id)
    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    if not status:
        raise HTTPException(status_code=404, detail="Train status unavailable")

    # route with timeline state relative to current position
    rows = db.execute(
        select(RouteStation, Station)
        .join(Station, RouteStation.station_id == Station.id)
        .where(RouteStation.train_id == train.id)
        .order_by(RouteStation.sequence_number)
    ).all()
    route: list[RouteStopOut] = []
    for rs, st in rows:
        if rs.sequence_number < status.segment_index:
            state = "done"
        elif rs.sequence_number == status.segment_index:
            state = "current"
        else:
            state = "upcoming"
        route.append(
            RouteStopOut(
                station_code=st.station_code,
                station_name=st.station_name,
                sequence_number=rs.sequence_number,
                scheduled_arrival=rs.scheduled_arrival,
                scheduled_departure=rs.scheduled_departure,
                distance_from_origin=rs.distance_from_origin,
                latitude=st.latitude,
                longitude=st.longitude,
                state=state,
            )
        )

    hist_rows = db.execute(
        select(HistoricalDelay, Station)
        .join(Station, HistoricalDelay.station_id == Station.id)
        .where(HistoricalDelay.train_id == train.id)
    ).all()
    historical = [
        HistoricalDelayOut(
            station_code=st.station_code,
            station_name=st.station_name,
            average_delay_minutes=hd.average_delay_minutes,
            punctuality_percent=hd.punctuality_percent,
            delay_category=hd.delay_category,
        )
        for hd, st in hist_rows
    ]

    tr = db.scalar(select(TrainRoute).where(TrainRoute.train_id == train.id))
    polyline = json.loads(tr.polyline) if tr and tr.polyline else []

    return TrainDetailOut(
        train_id=train.id,
        train_number=train.train_number,
        train_name=train.train_name,
        source=StationOut.model_validate(train.source_station),
        destination=StationOut.model_validate(train.destination_station),
        status=_status_out(train, status),
        route=route,
        historical=historical,
        polyline=polyline,
        # imported catalogue trains only have source+destination stops for now;
        # detailed intermediate stops are shown when available (curated trains)
        intermediate_stops_available=len(route) > 2,
        is_demo=bool(train.is_demo),
    )


@router.get("/{train_id}/status", response_model=TrainStatusOut)
def train_status(train_id: int, db: Session = Depends(get_db)):
    train = _get_train_or_404(db, train_id)
    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    if not status:
        raise HTTPException(status_code=404, detail="Train status unavailable")
    return _status_out(train, status)


@router.get("/{train_id}/eta", response_model=ETAOut)
def train_eta(train_id: int, db: Session = Depends(get_db)):
    train = _get_train_or_404(db, train_id)
    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    if not status:
        raise HTTPException(status_code=404, detail="Prediction unavailable")
    result = predict_for_status(db, status)
    return ETAOut(
        train_id=train.id,
        current_eta=result.current_eta,
        scheduled_arrival=result.scheduled_arrival,
        delay_minutes=result.delay_minutes,
        reason=result.reason,
        predictor=result.predictor,
        components=result.components,
    )


@router.get("/{train_id}/route", response_model=list[RouteStopOut])
def train_route(train_id: int, db: Session = Depends(get_db)):
    train = _get_train_or_404(db, train_id)
    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    seg = status.segment_index if status else 0
    rows = db.execute(
        select(RouteStation, Station)
        .join(Station, RouteStation.station_id == Station.id)
        .where(RouteStation.train_id == train.id)
        .order_by(RouteStation.sequence_number)
    ).all()
    out = []
    for rs, st in rows:
        state = "done" if rs.sequence_number < seg else "current" if rs.sequence_number == seg else "upcoming"
        out.append(
            RouteStopOut(
                station_code=st.station_code,
                station_name=st.station_name,
                sequence_number=rs.sequence_number,
                scheduled_arrival=rs.scheduled_arrival,
                scheduled_departure=rs.scheduled_departure,
                distance_from_origin=rs.distance_from_origin,
                latitude=st.latitude,
                longitude=st.longitude,
                state=state,
            )
        )
    return out


@router.get("/{train_id}/impact", response_model=DownstreamImpactOut)
def train_impact(train_id: int, db: Session = Depends(get_db)):
    """Current simulated downstream impact for a train (does not mutate state)."""
    train = _get_train_or_404(db, train_id)
    status = db.scalar(select(TrainStatus).where(TrainStatus.train_id == train.id))
    # source impact = operational delay currently on this train
    from app.services.status import operational_impact

    src_impact = operational_impact(db, train.id)
    affected_raw = (
        compute_downstream_for_train(db, train, src_impact, apply=False)
        if src_impact
        else []
    )
    return DownstreamImpactOut(
        source_train=train.train_number,
        source_train_name=train.train_name,
        reason=latest_reason(db, train.id),
        affected_count=len(affected_raw),
        affected_trains=[AffectedTrainOut(**a) for a in affected_raw],
    )
