"""Create tables and load the curated demonstration dataset.

Run from the backend directory:
    python -m app.seed
"""
from __future__ import annotations

import json

from sqlalchemy import delete

from app.db import Base, SessionLocal, engine
from app.data import seed_data as sd
from app.models import (
    HistoricalDelay,
    OperationalEvent,
    RouteStation,
    SimulationState,
    Station,
    Train,
    TrainRoute,
    TrainStatus,
)
from app.services.eta import status_text_for
from app.services.geo import hhmm_to_min, min_to_hhmm


def reset_tables() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed() -> None:
    reset_tables()
    db = SessionLocal()
    try:
        # Stations
        code_to_station: dict[str, Station] = {}
        for code, (name, lat, lng) in sd.STATIONS.items():
            s = Station(station_code=code, station_name=name, latitude=lat, longitude=lng)
            db.add(s)
            code_to_station[code] = s
        db.flush()

        for t in sd.TRAINS:
            route = t["route"]
            src_code = route[0][0]
            dst_code = route[-1][0]
            train = Train(
                train_number=t["number"],
                train_name=t["name"],
                source_station_id=code_to_station[src_code].id,
                destination_station_id=code_to_station[dst_code].id,
                is_demo=True,
            )
            db.add(train)
            db.flush()

            # route stations
            for seq, (code, arr, dep, dist) in enumerate(route):
                db.add(
                    RouteStation(
                        train_id=train.id,
                        station_id=code_to_station[code].id,
                        sequence_number=seq,
                        scheduled_arrival=arr,
                        scheduled_departure=dep,
                        distance_from_origin=dist,
                    )
                )

            # route polyline (station coords) for the map + simulated movement
            polyline = [
                [code_to_station[code].latitude, code_to_station[code].longitude]
                for code, _, _, _ in route
            ]
            db.add(
                TrainRoute(
                    train_id=train.id,
                    polyline=json.dumps(polyline),
                    distance_km=route[-1][3],
                )
            )

            # historical delays (corridor context where available)
            for code, arr, dep, dist in route:
                if code in sd.CORRIDOR_HISTORICAL:
                    avg, punc, cat = sd.CORRIDOR_HISTORICAL[code]
                else:
                    avg, punc, cat = 3.0, 88.0, "minor"
                db.add(
                    HistoricalDelay(
                        train_id=train.id,
                        station_id=code_to_station[code].id,
                        average_delay_minutes=avg,
                        punctuality_percent=punc,
                        delay_category=cat,
                    )
                )

            # current (simulated) status
            cur = code_to_station[t["current_code"]]
            nxt = code_to_station.get(t["next_code"]) if t.get("next_code") else None
            route_codes = [r[0] for r in route]
            seg_index = route_codes.index(t["current_code"])
            sched_dest = route[-1][1] or route[-1][2]
            delay = int(t["delay"])
            eta = min_to_hhmm((hhmm_to_min(sched_dest) or 0) + delay) if sched_dest else None

            db.add(
                TrainStatus(
                    train_id=train.id,
                    current_station_id=cur.id,
                    next_station_id=nxt.id if nxt else None,
                    current_lat=cur.latitude,
                    current_lng=cur.longitude,
                    segment_index=seg_index,
                    segment_progress=0.0,
                    delay_minutes=delay,
                    scheduled_arrival_dest=sched_dest,
                    current_eta=eta,
                    status_text=status_text_for(delay),
                    is_live=False,
                    source="SIMULATED",
                )
            )
            db.add(SimulationState(train_id=train.id, state="idle", tick=0))

        db.commit()
        n_trains = db.query(Train).count()
        n_stations = db.query(Station).count()
        n_route = db.query(RouteStation).count()
        print(
            f"Seed complete: {n_stations} stations, {n_trains} trains, "
            f"{n_route} route stops."
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
