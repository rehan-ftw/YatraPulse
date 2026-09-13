#!/usr/bin/env bash
# Start the whole YatraPulse stack for a demo: DB -> seed -> backend -> frontend.
# Ctrl-C stops backend and frontend (the DB keeps running; stop it with
# scripts/db.sh stop).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Database"
if ! "$ROOT/scripts/db.sh" status | grep -q UP; then
  # init on first run (no datadir yet), else just start
  if [ -d "$ROOT/.mysql-data" ] && [ -n "$(ls -A "$ROOT/.mysql-data" 2>/dev/null)" ]; then
    "$ROOT/scripts/db.sh" start
  else
    "$ROOT/scripts/db.sh" init
  fi
fi

echo "==> Backend deps"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env

echo "==> Seeding curated demo data"
.venv/bin/python -m app.seed

echo "==> Importing real train catalogue (DataMeet; cached in data/raw)"
.venv/bin/python -m app.import_catalog

echo "==> Backend (http://127.0.0.1:8000)"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACK_PID=$!

echo "==> Frontend deps"
cd "$ROOT/frontend"
[ -d node_modules ] || npm install

echo "==> Frontend (http://localhost:5173)"
npm run dev &
FRONT_PID=$!

cleanup() { echo; echo "Stopping..."; kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true; }
trap cleanup INT TERM
echo
echo "YatraPulse is starting. Open http://localhost:5173"
echo "(DB stays up after Ctrl-C; run 'scripts/db.sh stop' to stop it.)"
wait
