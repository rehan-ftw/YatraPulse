"""Pydantic response/request schemas (the API contract).

The frontend depends only on these shapes — it does not know how the ETA is
computed. This keeps the door open for swapping the Dynamic ETA engine for an
ML predictor later without changing the passenger UI.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    station_code: str
    station_name: str
    latitude: float | None
    longitude: float | None


class RouteStopOut(BaseModel):
    station_code: str
    station_name: str
    sequence_number: int
    scheduled_arrival: str | None
    scheduled_departure: str | None
    distance_from_origin: float
    latitude: float | None
    longitude: float | None
    # timeline state relative to current position: done / current / upcoming
    state: str = "upcoming"


class HistoricalDelayOut(BaseModel):
    station_code: str
    station_name: str
    average_delay_minutes: float
    punctuality_percent: float
    delay_category: str


class TrainSummary(BaseModel):
    """Compact shape used in search results and live-status lists."""
    id: int
    train_number: str
    train_name: str
    source: str          # source station name
    destination: str     # destination station name
    status_text: str
    delay_minutes: int | None
    current_station: str | None
    next_station: str | None
    current_eta: str | None
    is_live: bool
    data_source: str = "SCHEDULED"  # SCHEDULED | SIMULATED | HISTORICAL | LIVE
    tracked: bool = False           # False = timetable only (no live position)


class TrainStatusOut(BaseModel):
    train_id: int
    train_number: str
    train_name: str
    source: str
    destination: str
    current_station: str | None
    next_station: str | None
    current_lat: float | None
    current_lng: float | None
    delay_minutes: int | None
    scheduled_arrival_dest: str | None
    current_eta: str | None
    status_text: str
    is_live: bool
    last_updated: datetime
    data_source: str = "SCHEDULED"
    tracked: bool = False


class ETAOut(BaseModel):
    train_id: int
    current_eta: str | None
    scheduled_arrival: str | None
    delay_minutes: int
    reason: str
    predictor: str  # which ETA implementation produced this (e.g. "dynamic")
    components: dict  # transparent breakdown of the calculation


class TrainDetailOut(BaseModel):
    train_id: int
    train_number: str
    train_name: str
    source: StationOut
    destination: StationOut
    status: TrainStatusOut
    route: list[RouteStopOut]
    historical: list[HistoricalDelayOut]
    polyline: list[list[float]] = []          # real route geometry [[lat,lng],...]
    intermediate_stops_available: bool = True  # False when only source/dest known
    is_demo: bool = False


class AffectedTrainOut(BaseModel):
    train_number: str
    train_name: str
    added_delay_minutes: int
    new_eta: str | None


class DownstreamImpactOut(BaseModel):
    source_train: str
    source_train_name: str
    reason: str
    affected_count: int
    affected_trains: list[AffectedTrainOut]
    note: str = "SIMULATED IMPACT"


class AlertOut(BaseModel):
    id: int
    type: str
    train_number: str
    train_name: str
    title: str
    reason: str
    impact_minutes: int
    previous_eta: str | None
    new_eta: str | None
    timestamp: datetime


class SimulationStatusOut(BaseModel):
    train_id: int
    state: str
    tick: int
    is_live: bool
