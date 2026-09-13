"""Import a large real train catalogue from the DataMeet Indian Railways
timetable (public GitHub, no API key required) into the existing MySQL schema.

This is ADDITIVE: it preserves the curated flagship demo trains (12952 etc.)
and their simulation/downstream/historical setup, and appends thousands of real
trains + stations for a broad, searchable catalogue.

Honesty: imported trains are stored as SCHEDULED (timetable) data only. We do
NOT fabricate a live location/delay/ETA for them — current/next station are left
empty and the ETA shown is the scheduled arrival, clearly labelled. A passenger
can still start a simulated journey on any of them (that becomes SIMULATED data).

Data source: https://github.com/datameet/railways
  stations.json  - 8,990 stations (GeoJSON points, real coordinates)
  trains.json    - ~5,200 trains (GeoJSON, number/name/from/to/times + route)

Run (after `python -m app.seed`):
    python -m app.import_catalog            # import all
    python -m app.import_catalog --limit 800
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from sqlalchemy import insert, select

from app.db import SessionLocal, engine
from app.data import seed_data as sd
from app.models import (
    RouteStation,
    SimulationState,
    Station,
    Train,
    TrainRoute,
    TrainStatus,
)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
BASE = "https://raw.githubusercontent.com/datameet/railways/master"


def _ensure(name: str) -> Path:
    path = RAW_DIR / name
    if not path.exists() or path.stat().st_size == 0:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {name} ...")
        urllib.request.urlretrieve(f"{BASE}/{name}", path)
    return path


def _hhmm(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) < 2:
        return None
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def import_catalog(limit: int | None = None) -> None:
    stations_path = _ensure("stations.json")
    trains_path = _ensure("trains.json")

    stations_geo = json.loads(stations_path.read_text())["features"]
    trains_geo = json.loads(trains_path.read_text())["features"]

    db = SessionLocal()
    try:
        # --- existing state (preserve curated + avoid duplicates) ---
        existing_codes = {c for (c,) in db.execute(select(Station.station_code))}
        existing_numbers = {n for (n,) in db.execute(select(Train.train_number))}

        # --- stations: bulk insert any new codes with coordinates ---
        new_stations = []
        seen = set(existing_codes)
        for f in stations_geo:
            p = f.get("properties", {})
            code = (p.get("code") or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
            lng, lat = coords[0], coords[1]
            new_stations.append(
                {"station_code": code, "station_name": p.get("name") or code,
                 "latitude": lat, "longitude": lng}
            )
        if new_stations:
            db.execute(insert(Station), new_stations)
            db.commit()
        print(f"Stations: +{len(new_stations)} (total now {len(seen)})")

        # refresh code -> id map
        code_to_id = {c: i for (c, i) in db.execute(select(Station.station_code, Station.id))}

        # --- trains: prepare rows, skipping curated + duplicates ---
        train_rows = []
        payloads = []  # keep per-train derived data aligned by train_number
        seen_numbers = set(existing_numbers)
        for f in trains_geo:
            p = f.get("properties", {})
            number = (p.get("number") or "").strip()
            src = (p.get("from_station_code") or "").strip()
            dst = (p.get("to_station_code") or "").strip()
            if not number or number in seen_numbers:
                continue
            if src not in code_to_id or dst not in code_to_id:
                continue
            seen_numbers.add(number)
            arr = _hhmm(p.get("arrival"))
            dep = _hhmm(p.get("departure"))
            coords = (f.get("geometry") or {}).get("coordinates") or []
            polyline = [[c[1], c[0]] for c in coords if len(c) >= 2]  # [lat,lng]
            train_rows.append(
                {"train_number": number, "train_name": (p.get("name") or number)[:160],
                 "source_station_id": code_to_id[src],
                 "destination_station_id": code_to_id[dst], "is_demo": False}
            )
            payloads.append(
                {"number": number, "src": src, "dst": dst, "arr": arr, "dep": dep,
                 "distance": float(p.get("distance") or 0), "polyline": polyline}
            )
            if limit and len(train_rows) >= limit:
                break

        if train_rows:
            db.execute(insert(Train), train_rows)
            db.commit()
        print(f"Trains: +{len(train_rows)}")

        number_to_id = {n: i for (n, i) in db.execute(select(Train.train_number, Train.id))}

        # --- dependent rows (routes, polylines, honest scheduled status) ---
        route_rows, poly_rows, status_rows, sim_rows = [], [], [], []
        for pl in payloads:
            tid = number_to_id[pl["number"]]
            route_rows.append(
                {"train_id": tid, "station_id": code_to_id[pl["src"]], "sequence_number": 0,
                 "scheduled_arrival": None, "scheduled_departure": pl["dep"],
                 "distance_from_origin": 0.0}
            )
            route_rows.append(
                {"train_id": tid, "station_id": code_to_id[pl["dst"]], "sequence_number": 1,
                 "scheduled_arrival": pl["arr"], "scheduled_departure": None,
                 "distance_from_origin": pl["distance"]}
            )
            poly_rows.append(
                {"train_id": tid, "polyline": json.dumps(pl["polyline"]),
                 "distance_km": pl["distance"]}
            )
            # honest scheduled state: not tracked live, no invented position/delay
            status_rows.append(
                {"train_id": tid, "current_station_id": None, "next_station_id": None,
                 "current_lat": None, "current_lng": None, "segment_index": 0,
                 "segment_progress": 0.0, "delay_minutes": 0,
                 "scheduled_arrival_dest": pl["arr"], "current_eta": pl["arr"],
                 "status_text": "SCHEDULED", "is_live": False, "source": "SCHEDULED"}
            )
            sim_rows.append({"train_id": tid, "state": "idle", "tick": 0})

        for rows, model in (
            (route_rows, RouteStation),
            (poly_rows, TrainRoute),
            (status_rows, TrainStatus),
            (sim_rows, SimulationState),
        ):
            # chunk to keep statements reasonable
            for i in range(0, len(rows), 1000):
                db.execute(insert(model), rows[i : i + 1000])
            db.commit()

        total = db.scalar(select(Train.id).limit(1)) is not None
        n_trains = len(number_to_id)
        print(f"Done. Catalogue now has {n_trains} trains, {len(seen)} stations.")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="max trains to import")
    args = ap.parse_args()
    import_catalog(args.limit)
