# YatraPulse — Demo Guide (60 seconds)

This is the exact sequence to run in front of an evaluator. The whole ETA update
happens **without a page refresh**.

## Launch

Three terminals (or run `scripts/run.sh` which does all three):

```bash
# 1) database (isolated, project-local MySQL on port 3307)
scripts/db.sh start          # (first time ever: scripts/db.sh init)

# 2) backend
cd backend && source .venv/bin/activate
python -m app.seed           # curated demo data (first time / to reset)
python -m app.import_catalog # ~5,200 real trains + 8,990 stations (first time)
uvicorn app.main:app --reload

# 3) frontend
cd frontend && npm run dev
```

Open **http://localhost:5173**.

## The script

0. (Optional, shows the broad catalogue) Search **`Rajdhani`** or a city like
   **`Chennai`** — dozens of real trains appear, labelled *Scheduled / Not
   currently tracked*. The curated demo trains show at the top as live/tracked.
1. **Home** → in the search box type **`12952`** → **Search train**.
2. In results, click **Track train** on *12952 Mumbai Rajdhani Express*.
3. **Train Details** opens — the train is **already LIVE and moving** (the
   flagship demo train runs a perpetual simulated live journey; no need to press
   Start). Point out:
   - **● LIVE · Live tracking · updated Ns ago** (ticking) and the marker moving
     along the route.
   - Big status: **RUNNING ON TIME**, **EXPECTED ARRIVAL 18:42** (dominant).
   - Current location / next station, the **route map**, the **route timeline**,
     and the **historical delay context** (e.g. Ratlam averages +6.4 min, 82%
     punctuality) — labelled *historical data*.
4. (Optional, for the crispest story) Click **↺ Reset** — the train jumps back to
   the clean **ON TIME at Kota → Ratlam** start and stays live.
5. While the train is between Kota and Ratlam, click **⚠ Simulate congestion**.
6. Watch, with **no refresh**:
   - A **passenger alert** slides in: *"YOUR ETA HAS CHANGED"* — 18:42 → 18:50.
   - The **ETA card** animates **18:42 → 18:50**, shows **▲ +8 min**, previous
     ETA struck through, and the reason: *"Heavy congestion detected near
     Ratlam Junction"*.
   - Big status becomes **RUNNING 8 MIN LATE**.
   - **DOWNSTREAM IMPACT** fills in — **3 trains affected**:
     - 12952 Mumbai Rajdhani **+8 min** (source)
     - 12954 August Kranti Rajdhani **+5 min**
     - 22210 NDLS–MMCT Duronto **+3 min**
     - 12264 Nizamuddin–MMCT Duronto **+2 min**
     (marked **SIMULATED IMPACT**)
7. Open **Alerts** in the nav to show the same update recorded as a passenger
   alert with train, time, reason and impact.
8. Controls: **Pause / Resume** hold and continue the journey, **■ Stop** halts
   movement (the train stays where it is, no longer live), and **↺ Reset**
   restores the clean starting state (ETA 18:42 at Kota, downstream cleared) —
   and for the demo train it **stays live**, so you can immediately run the
   scenario again.

You can also **search any other train** (e.g. `12951`, `Chennai`), open it, and
**Start live simulation** — the marker follows that train's real route and the
same dynamic-ETA/congestion flow works, clearly labelled SIMULATED.

## Talking points

- **Why it changed** is always on screen (reason + "How this ETA is calculated"
  breakdown) — the ETA is transparent, not a black box.
- **Historical vs simulated** is labelled throughout; simulated events are never
  claimed to be real live railway data.
- The ETA engine sits behind a **model-agnostic interface**, so a future ML model
  can replace it without touching the passenger UI.

## If something looks off

- **ETA didn't change / no downstream:** make sure you clicked **Start live
  simulation** before **Inject congestion** (congestion is disabled until the
  journey is running).
- **Marker not moving:** confirm the backend is running and the **● LIVE** dot in
  the top-right of the app bar is active (WebSocket connected).
- **Want the event to say "near Ratlam":** inject congestion soon after starting,
  while the next station is still Ratlam. Inject later and it will name whatever
  the next station is then — the location is genuinely dynamic.
- **Reset for a clean run:** click **Stop & reset**, or re-run `python -m app.seed`.
