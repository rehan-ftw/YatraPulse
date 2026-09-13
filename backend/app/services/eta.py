"""Dynamic ETA engine.

This is intentionally a transparent, rule-based calculation — NOT machine
learning. It exposes a model-agnostic `ETAPredictor` interface so an
`MLPredictor` can be dropped in later without changing the API or the
passenger UI.

Conceptual model (coefficients are configurable via .env):

    Dynamic ETA = Scheduled Arrival
                + Current Delay              (delay already accrued)
                + Operational Impact         (active disruptions e.g. congestion)

    Historical Delay Component is surfaced transparently for context/believability
    but is treated as already priced into the published schedule, so a healthy
    train legitimately starts at 0 min delay.

There is no fake scientific precision here; the point is to demonstrate
dynamic recalculation that a passenger can understand.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.services.geo import hhmm_to_min, min_to_hhmm


@dataclass
class ETAContext:
    scheduled_arrival: str | None          # "HH:MM" scheduled arrival at destination
    current_delay: int = 0                 # minutes already accrued
    operational_impact: int = 0            # minutes from active operational events
    historical_avg_delay: float = 0.0      # avg historical delay at the next station
    historical_weight: float = 0.5
    next_station: str | None = None
    reason: str = "Running to schedule"


@dataclass
class ETAResult:
    current_eta: str | None
    scheduled_arrival: str | None
    delay_minutes: int
    reason: str
    predictor: str
    components: dict = field(default_factory=dict)


class ETAPredictor(ABC):
    """Model-agnostic ETA interface. Implementations must not leak into the API."""

    name: str = "base"

    @abstractmethod
    def predict(self, ctx: ETAContext) -> ETAResult: ...


class DynamicETAPredictor(ETAPredictor):
    """Transparent rule-based predictor used for the prototype."""

    name = "dynamic"

    def predict(self, ctx: ETAContext) -> ETAResult:
        sched_min = hhmm_to_min(ctx.scheduled_arrival)
        applied_delay = int(ctx.current_delay) + int(ctx.operational_impact)

        eta_min = None if sched_min is None else sched_min + applied_delay

        historical_component = round(ctx.historical_avg_delay * ctx.historical_weight, 1)

        components = {
            "scheduled_arrival": ctx.scheduled_arrival,
            "current_delay": int(ctx.current_delay),
            "operational_impact": int(ctx.operational_impact),
            "historical_avg_delay": round(ctx.historical_avg_delay, 1),
            "historical_weight": ctx.historical_weight,
            # informational only — see module docstring
            "historical_delay_component": historical_component,
            "applied_delay": applied_delay,
        }

        return ETAResult(
            current_eta=min_to_hhmm(eta_min),
            scheduled_arrival=ctx.scheduled_arrival,
            delay_minutes=applied_delay,
            reason=ctx.reason,
            predictor=self.name,
            components=components,
        )


# The single active predictor. Swap this line to change the engine app-wide;
# nothing else (API, UI) needs to change.
active_predictor: ETAPredictor = DynamicETAPredictor()


def status_text_for(delay: int) -> str:
    if delay <= 0:
        return "ON TIME"
    return f"{delay} MIN LATE"
