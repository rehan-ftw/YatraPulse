# YatraPulse - Dynamic Forecast of Expected Time of Arrival (ETA)

**Smart India Hackathon 2026 · Problem Statement SIH26028**
Theme: Smart Automation · Category: Software

> Traditional railway schedules tell you when a train is *scheduled* to arrive.
> They don't continuously reflect congestion, delays, dwell, signal holds or
> disruptions. **YatraPulse** is a passenger-first prototype that recalculates a
> train's ETA live as operational conditions change — and shows how one train's
> disruption ripples to trains behind it.

```
TRAIN ON TIME → JOURNEY SIMULATED → DISRUPTION → ETA RECALCULATED
   → DOWNSTREAM IMPACT → PASSENGER AUTOMATICALLY INFORMED
```

---

## What problem does it solve?

A passenger tracking a train sees a static scheduled arrival. When congestion
hits the section ahead, that number is silently wrong. YatraPulse makes the ETA
*dynamic*: it recalculates the moment conditions change, explains **why** it
changed, pushes the update to the passenger with no page refresh, and shows the
knock-on impact on following trains.

## How dynamic ETA works

The ETA is produced by a **transparent, rule-based engine** — *not* machine
learning (ML is a documented future enhancement). Conceptually:

```
Dynamic ETA = Scheduled Arrival
            + Current Delay          (delay already accrued)
            + Operational Impact     (active disruptions, e.g. congestion)
```

A **Historical Delay Component** (e.g. Ratlam averages +6.4 min, 82% punctuality)
is surfaced for context and believability, but is treated as already priced into
the published schedule — so a healthy train legitimately starts at 0 min delay.

Coefficients (historical weight, congestion dwell, downstream propagation
factors) are configurable in `backend/.env`. See
[`backend/app/services/eta.py`](backend/app/services/eta.py).

### Model-agnostic by design

The ETA is produced behind an `ETAPredictor` interface. Today the active
implementation is `DynamicETAPredictor`. Tomorrow an `MLPredictor` can be dropped
in **without changing the API or the passenger UI**.

## Train catalogue

The searchable catalogue is a **large set of real Indian Railways trains** —
~5,200 trains and ~8,990 stations imported from the public DataMeet timetable
(`app.import_catalog`, no API key). Search works by full/partial train number,
train name, source or destination. Curated flagship demo trains (12952 etc.)
float to the top.

## Data provenance (labelled everywhere)

Every train's state is produced behind a single **provider abstraction**
(`app/providers`) that yields the same normalized `TrainState` regardless of
origin, so the frontend only reads a `source` label:

- **SCHEDULED** — timetable-only catalogue trains. We do **not** invent a live
  position or delay; current/next station show as *Not tracked* and the ETA is
  the scheduled arrival.
- **SIMULATED** — the curated demo trains and any train you start a simulated
  journey on: the moving marker, congestion, recalculated ETA, downstream impact.
  Clearly labelled; never presented as real live data. The flagship demo train
  **auto-runs a perpetual live journey on server startup**, so the app always
  shows a train being tracked live (● LIVE, moving marker, "updated Ns ago") the
  moment you open it — no button press and no external feed/API key.
- **HISTORICAL** — per-station average delay / punctuality context.
- **LIVE** — reserved for a future real feed. A `LiveProvider` stub exists; wiring
  a real (unofficial) feed later needs only that one class — no API/UI changes.
  The app is **not** dependent on any external key.

See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) for dataset provenance and the
future ML-training sources.

## Tech stack

| Layer      | Choice                                             |
| ---------- | -------------------------------------------------- |
| Frontend   | React + Vite + TypeScript, Leaflet + OpenStreetMap |
| Backend    | Python + FastAPI, WebSockets                       |
| Database   | MySQL via SQLAlchemy 2.0                            |
| Realtime   | WebSocket (`/ws/live-updates`)                     |

---

## Getting started

### Prerequisites

- Python 3.11+ and Node 18+
- MySQL 8/9 (the repo ships a script that runs an **isolated, project-local**
  MySQL instance so nothing touches your system MySQL).

### 1. Database

The provided script runs a dedicated `mysqld` on **port 3307** with its own data
directory (`./.mysql-data`, git-ignored) and no root password — local dev only.

```bash
scripts/db.sh init      # first time: create datadir + database + app user
# later:
scripts/db.sh start     # start it
scripts/db.sh status    # UP / DOWN
scripts/db.sh stop      # stop it
scripts/db.sh reset     # wipe + re-init (destroys data)
```

> Already have your own MySQL? Just point `backend/.env` at it (host/port/user/
> password/db) and skip the script.

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # adjust if needed
python -m app.seed              # create tables + load curated demo data
python -m app.import_catalog    # import ~5,200 real trains + 8,990 stations
                                # (DataMeet timetable; downloaded once to data/raw)
uvicorn app.main:app --reload   # http://127.0.0.1:8000  (docs at /docs)
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The Vite dev server proxies `/api` and `/ws` to the backend, so open
**http://localhost:5173** and everything just works.

### One-shot (all of the above)

```bash
scripts/run.sh                  # db + seed + backend + frontend
```

---

## Running the demo

See [`docs/demo-guide.md`](docs/demo-guide.md) for the exact 60-second script.
In short: search **12952** → open it → **Start live simulation** → **Inject
congestion** → watch ETA change **18:42 → 18:50**, the reason appear, the
passenger alert pop, and **3 downstream trains** update — all with no refresh.

## API reference

```
GET  /api/health
GET  /api/trains                      demo + currently-live trains (Home/Live)
GET  /api/trains/search?q=&limit=     search by number (full/partial), name, source or destination
GET  /api/trains/{id}                 full detail (status, route, historical)
GET  /api/trains/{id}/status          current live status
GET  /api/trains/{id}/eta             dynamic ETA + transparent breakdown
GET  /api/trains/{id}/route           ordered route stops
GET  /api/trains/{id}/impact          simulated downstream impact
GET  /api/alerts                      passenger alerts
POST /api/simulation/start            {train_id}
POST /api/simulation/pause            {train_id}
POST /api/simulation/resume           {train_id}
POST /api/simulation/stop             {train_id}   (halt movement, keep position)
POST /api/simulation/reset            {train_id}   (restore pristine start for replay)
POST /api/simulation/congestion       {train_id, event_type}  (congestion/signal_hold/station_delay)
GET  /api/simulation/status?train_id=
WS   /ws/live-updates                 ETA_UPDATED / TRAIN_MOVEMENT_UPDATED /
                                      OPERATIONAL_EVENT / DOWNSTREAM_IMPACT_UPDATED /
                                      SIMULATION_STATE_CHANGED
```

## Project structure

```
backend/app
  api/          FastAPI routers (trains, alerts, simulation)
  models/       SQLAlchemy ORM (normalized railway model)
  schemas/      Pydantic API contract
  services/     eta (predictor interface + dynamic engine), impact, status, geo
  providers/    TrainState provider abstraction (SCHEDULED/SIMULATED/LIVE seam)
  simulation/   movement engine + WebSocket manager
  data/         curated demo dataset
  seed.py       create tables + load curated demo data
  import_catalog.py  import the large real DataMeet catalogue
frontend/src
  components/   ETACard, RouteTimeline, MapView, SimulationPanel, DownstreamImpact…
  pages/        Home, SearchResults, TrainDetails, LiveStatus, Alerts
  services/     api client
  hooks/        useLiveUpdates (WebSocket)
scripts/        db.sh, run.sh
docs/           demo-guide.md, DATA_SOURCES.md
```

## Future work (ML)

The dataset layout and the `ETAPredictor` seam are designed so that the larger
Kaggle / 312K-row delay datasets can later train an `MLPredictor` that slots in
behind the same API. See `docs/DATA_SOURCES.md`.

---

*YatraPulse is a hackathon prototype. Simulated operational events are for
demonstration only and are not real Indian Railways data.*
