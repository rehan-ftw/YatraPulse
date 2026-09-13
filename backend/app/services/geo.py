"""Small geo/time helpers. Deliberately simple — a convincing route
visualization does not need full GIS."""
from __future__ import annotations


def hhmm_to_min(value: str | None) -> int | None:
    if not value:
        return None
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(total: int | None) -> str | None:
    if total is None:
        return None
    total %= 24 * 60  # wrap within a day
    return f"{total // 60:02d}:{total % 60:02d}"


def interpolate(lat1: float, lng1: float, lat2: float, lng2: float, frac: float):
    """Linear interpolation between two coordinates. Good enough for a moving
    train marker along a route polyline."""
    frac = max(0.0, min(1.0, frac))
    return (lat1 + (lat2 - lat1) * frac, lng1 + (lng2 - lng1) * frac)
