# Data Sources & Strategy

YatraPulse cleanly separates **historical railway data** from **simulated live
operations**. This document records what is used now and what is reserved for
future ML work.

## What the prototype uses today

Two layers, loaded in order:

**1. Curated flagship corridor** (`app.seed`) — New Delhi ⇄ Mumbai Central:
- **Real** station codes, names and coordinates (NDLS, MTJ, AGC, KOTA, RTM, BRC,
  ST, MMCT, ADI, BPL).
- **Real** train numbers/names (12952 Mumbai Rajdhani, 12954 August Kranti
  Rajdhani, 22210 NDLS–MMCT Duronto, 12264 Nizamuddin–MMCT Duronto).
- **Illustrative** schedule times + per-station historical delay/punctuality,
  shaped from the pattern of public delay datasets — labelled historical context,
  not asserted as exact live records. Lives in
  [`backend/app/data/seed_data.py`](../backend/app/data/seed_data.py).

**2. Large real catalogue** (`app.import_catalog`) — the public DataMeet
timetable, imported into the same MySQL schema:
- `stations.json` → **~8,990 real stations** with coordinates.
- `trains.json` → **~5,200 real trains** with number, name, source, destination,
  scheduled departure/arrival, distance and a **real route polyline** (drawn on
  the map). Downloaded once to `data/raw/` (git-ignored), imported in a few
  seconds with bulk inserts.

Imported trains are stored as **SCHEDULED (timetable) data only** — we never
fabricate a live position/delay/ETA for them. `schedules.json` (per-stop lists,
82 MB) is deliberately **not** imported, so imported trains show origin +
destination stops (plus the true route line) and label detailed intermediate
stops as unavailable. A passenger can still start a *simulated* journey on any
catalogue train, which then becomes clearly-labelled SIMULATED data.

## Primary sources (shape / reference)

- **Indian Railways Train Delays Dataset 2025** — Kaggle
  <https://www.kaggle.com/datasets/naijilaji/indian-railways-passenger-train-delays-dataset/data>
  — train/station delay, average delay, punctuality, delay severity, historical
  patterns.
- **DataMeet Indian Railways** — GitHub <https://github.com/datameet/railways>
  — train/station master, schedules, routes, station coordinates.
- **Indian Railway Express Train Delay Dataset** — GitHub
  <https://github.com/ankitaanand28/DA323_IndianRailwayTrainDelayDatasets>
  — route-level and station-level delay patterns.

## Live-provider candidates (future, not integrated)

- **railpull** — GitHub <https://github.com/shwetankg07/railpull> — an unofficial
  live train-status puller. Evaluated as a possible `LiveProvider` source. It is
  **not** wired in: the prototype must not depend on external/unofficial live
  access, and per the brief we stop pursuing live integration the moment it risks
  becoming a blocker. The `LiveProvider` seam in `app/providers` is where such a
  feed would plug in later (emitting `source="LIVE"`), with no API/UI changes.

## Future ML / statistical sources (not required today)

- **Large Indian Railways Train Delay Dataset** — Kaggle competition
  <https://www.kaggle.com/competitions/indian-railways-predict-train-delay/data>
- **Railway Delay Dataset (~312K rows)** — Kaggle
  <https://www.kaggle.com/datasets/anuragraturi/railway-delay-dataset>

## How future data slots in

```
Historical Data → Feature Engineering → ML ETA Model → ETA Service (MLPredictor)
```

The ETA is produced behind the `ETAPredictor` interface in
[`backend/app/services/eta.py`](../backend/app/services/eta.py). Today's
`DynamicETAPredictor` can be replaced by an `MLPredictor` trained on the datasets
above **without any change to the API or the passenger UI**. Raw/processed data
belongs under `data/raw/` and `data/processed/` (git-ignored).
