"""Curated demonstration dataset for YatraPulse.

These are REAL Indian Railways trains and REAL stations with real geographic
coordinates along the New Delhi <-> Mumbai Central (Western Railway) corridor.

The station list, coordinates, train numbers and names are real. The precise
schedule times and the historical-delay figures are a curated, illustrative
subset shaped for a clear 30-60s demo (drawn from the shape of public delay
datasets, not asserted as exact live railway records). This distinction is
surfaced everywhere in the UI: HISTORICAL DATA vs SIMULATED LIVE OPERATIONS.

Full raw datasets (Kaggle / DataMeet) are documented in docs/DATA_SOURCES.md as
future ML-training sources; we deliberately do not bulk-import them here.
"""
from __future__ import annotations

# code -> (name, latitude, longitude)
STATIONS: dict[str, tuple[str, float, float]] = {
    "NDLS": ("New Delhi", 28.6435, 77.2194),
    "MTJ": ("Mathura Junction", 27.4924, 77.6737),
    "AGC": ("Agra Cantt", 27.1578, 77.9760),
    "KOTA": ("Kota Junction", 25.1811, 75.8380),
    "RTM": ("Ratlam Junction", 23.3315, 75.0367),
    "BRC": ("Vadodara Junction", 22.3100, 73.1812),
    "ST": ("Surat", 21.2065, 72.8397),
    "MMCT": ("Mumbai Central", 18.9690, 72.8205),
    "ADI": ("Ahmedabad Junction", 23.0270, 72.6010),
    "BPL": ("Bhopal Junction", 23.2680, 77.4010),
}

# The canonical Delhi -> Mumbai corridor: (station_code, arr, dep, distance_km).
# Times are the baseline schedule for the flagship demo train (12952).
CORRIDOR_STOPS: list[tuple[str, str | None, str | None, float]] = [
    ("NDLS", None, "08:00", 0.0),
    ("MTJ", "09:35", "09:37", 141.0),
    ("AGC", "10:25", "10:27", 195.0),
    ("KOTA", "13:10", "13:15", 465.0),
    ("RTM", "15:35", "15:40", 727.0),
    ("BRC", "17:00", "17:05", 990.0),
    ("ST", "17:55", "17:57", 1120.0),
    ("MMCT", "18:42", None, 1385.0),
]

# Per-station historical delay context for the corridor (illustrative).
# station_code -> (avg_delay_min, punctuality_pct, category)
CORRIDOR_HISTORICAL: dict[str, tuple[float, float, str]] = {
    "NDLS": (0.0, 96.0, "on_time"),
    "MTJ": (2.1, 91.0, "minor"),
    "AGC": (3.4, 89.0, "minor"),
    "KOTA": (4.2, 86.0, "minor"),
    "RTM": (6.4, 82.0, "moderate"),
    "BRC": (5.1, 84.0, "moderate"),
    "ST": (4.0, 87.0, "minor"),
    "MMCT": (5.5, 83.0, "moderate"),
}


def _shift(hhmm: str | None, minutes: int) -> str | None:
    if hhmm is None:
        return None
    h, m = map(int, hhmm.split(":"))
    total = (h * 60 + m + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def corridor_route(offset_min: int = 0):
    """Corridor stops shifted by `offset_min` minutes (for trailing trains)."""
    return [
        (code, _shift(arr, offset_min), _shift(dep, offset_min), dist)
        for code, arr, dep, dist in CORRIDOR_STOPS
    ]


# Real catalogue trains put into a perpetual simulated LIVE journey on startup,
# so the Live Status page shows a fleet of trains being tracked live (labelled
# "Simulated live operations"). These are real train numbers from the imported
# DataMeet catalogue; if any is missing at runtime the fleet is topped up
# automatically from the catalogue.
LIVE_FLEET_NUMBERS: list[str] = [
    "12301",  # Howrah - New Delhi Rajdhani
    "12302",  # New Delhi - Howrah Rajdhani
    "12951",  # Mumbai Central - New Delhi Rajdhani
    "12953",  # Mumbai Central - Nizamuddin August Kranti Rajdhani
    "12425",  # Jammu Rajdhani
    "12431",  # Trivandrum Rajdhani
    "12433",  # Chennai Rajdhani
    "12429",  # Bangalore Rajdhani
    "12439",  # Ranchi Rajdhani
    "22811",  # Bhubaneswar Rajdhani
    "12957",  # Ahmedabad Swarna Jayanti Rajdhani
    "22423",  # Guwahati Rajdhani
]


# Ordered chain of trailing trains impacted when the demo train hits congestion.
# Each is paired with a configurable propagation factor (see .env
# ETA_DOWNSTREAM_FACTORS); added_delay = round(source_impact * factor).
DOWNSTREAM_CHAIN: list[str] = ["12954", "22210", "12264"]


# Trains. `role`:
#   "demo"        -> flagship train the evaluator tracks (starts at Kota)
#   "downstream"  -> trailing corridor trains impacted by congestion
#   "other"       -> extra trains for search/live-status variety
TRAINS: list[dict] = [
    {
        "number": "12952",
        "name": "Mumbai Rajdhani Express",
        "role": "demo",
        "offset_min": 0,
        "route": corridor_route(0),
        # before simulation: sitting at Kota, next stop Ratlam, on time
        "current_code": "KOTA",
        "next_code": "RTM",
        "delay": 0,
        "downstream_rank": None,
    },
    {
        "number": "12954",
        "name": "August Kranti Rajdhani Express",
        "role": "downstream",
        "offset_min": 75,
        "route": corridor_route(75),
        "current_code": "AGC",
        "next_code": "KOTA",
        "delay": 0,
        "downstream_rank": 0,
    },
    {
        "number": "22210",
        "name": "New Delhi Mumbai Central Duronto Express",
        "role": "downstream",
        "offset_min": 130,
        "route": corridor_route(130),
        "current_code": "MTJ",
        "next_code": "AGC",
        "delay": 0,
        "downstream_rank": 1,
    },
    {
        "number": "12264",
        "name": "Nizamuddin Mumbai Central Duronto Express",
        "role": "downstream",
        "offset_min": 190,
        "route": corridor_route(190),
        "current_code": "NDLS",
        "next_code": "MTJ",
        "delay": 0,
        "downstream_rank": 2,
    },
    {
        "number": "12009",
        "name": "Ahmedabad Shatabdi Express",
        "role": "other",
        "offset_min": 0,
        "route": [
            ("MMCT", None, "06:25", 0.0),
            ("ST", "08:10", "08:12", 265.0),
            ("BRC", "09:18", "09:20", 395.0),
            ("ADI", "10:35", None, 493.0),
        ],
        "current_code": "ST",
        "next_code": "BRC",
        "delay": 6,
        "downstream_rank": None,
    },
    {
        "number": "12002",
        "name": "Bhopal Shatabdi Express",
        "role": "other",
        "offset_min": 0,
        "route": [
            ("NDLS", None, "06:00", 0.0),
            ("AGC", "07:55", "07:57", 195.0),
            ("BPL", "11:35", None, 702.0),
        ],
        "current_code": "AGC",
        "next_code": "BPL",
        "delay": 0,
        "downstream_rank": None,
    },
]
