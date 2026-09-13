"""Train-state provider abstraction.

Every source of train state — the timetable (SCHEDULED), the simulation engine
(SIMULATED), and a future real feed (LIVE) — produces the SAME normalized
`TrainState`. The API builds all passenger responses from this, so the frontend
never needs to know where the data came from; it only reads `source` to label it.

Adding a real live feed later means implementing one `LiveProvider.get_state`
and registering it in `resolve()` — no API or UI changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.models import Train, TrainStatus


@dataclass
class TrainState:
    train_number: str
    train_name: str
    source: str  # SCHEDULED | SIMULATED | HISTORICAL | LIVE
    is_live: bool
    status_text: str
    # tracked position (None when not tracked, e.g. SCHEDULED timetable-only)
    current_station: str | None
    next_station: str | None
    latitude: float | None
    longitude: float | None
    delay_minutes: int | None
    current_eta: str | None
    scheduled_arrival: str | None
    updated_at: datetime | None
    tracked: bool  # True when we have a real/simulated position; False = timetable only


class TrainStateProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_state(self, train: Train, status: TrainStatus) -> TrainState: ...


class SimulationProvider(TrainStateProvider):
    """State produced by the simulation engine (clearly SIMULATED, not real)."""

    name = "simulation"

    def get_state(self, train: Train, status: TrainStatus) -> TrainState:
        return TrainState(
            train_number=train.train_number,
            train_name=train.train_name,
            source="SIMULATED",
            is_live=bool(status.is_live),
            status_text=status.status_text,
            current_station=status.current_station.station_name if status.current_station else None,
            next_station=status.next_station.station_name if status.next_station else None,
            latitude=status.current_lat,
            longitude=status.current_lng,
            delay_minutes=status.delay_minutes,
            current_eta=status.current_eta,
            scheduled_arrival=status.scheduled_arrival_dest,
            updated_at=status.last_updated,
            tracked=True,
        )


class ScheduleProvider(TrainStateProvider):
    """Timetable-only state. We do NOT invent a live position or delay."""

    name = "schedule"

    def get_state(self, train: Train, status: TrainStatus) -> TrainState:
        return TrainState(
            train_number=train.train_number,
            train_name=train.train_name,
            source="SCHEDULED",
            is_live=False,
            status_text="SCHEDULED",
            current_station=None,
            next_station=None,
            latitude=None,
            longitude=None,
            delay_minutes=None,  # unknown — not tracked
            current_eta=status.scheduled_arrival_dest,
            scheduled_arrival=status.scheduled_arrival_dest,
            updated_at=status.last_updated,
            tracked=False,
        )


class LiveProvider(TrainStateProvider):
    """Placeholder for a real, unofficial live feed. Not enabled (no API key).

    When enabled, implement get_state() to map the feed into TrainState with
    source="LIVE" and tracked=True. Nothing else in the app needs to change.
    """

    name = "live"
    enabled = False

    def get_state(self, train: Train, status: TrainStatus) -> TrainState:  # pragma: no cover
        raise NotImplementedError("No live provider configured for this prototype")


_simulation = SimulationProvider()
_schedule = ScheduleProvider()


def resolve(train: Train, status: TrainStatus) -> TrainState:
    """Pick the provider for a train's current state.

    A train that is being simulated (is_live) or is a curated demo train whose
    state was prepared by the simulation is SIMULATED; everything else is
    timetable-only (SCHEDULED). A future LiveProvider would take precedence here
    when a real feed is connected for the train.
    """
    if status is None:
        return _schedule.get_state(train, status)  # type: ignore[arg-type]
    if status.is_live or status.source == "SIMULATED":
        return _simulation.get_state(train, status)
    return _schedule.get_state(train, status)
