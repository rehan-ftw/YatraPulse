#!/usr/bin/env bash
# Manage an isolated, project-local MySQL instance for YatraPulse.
#
# This does NOT touch any system MySQL. It runs a dedicated mysqld with its own
# data directory (./.mysql-data) on port 3307 with no root password. This is a
# LOCAL DEVELOPMENT / DEMO convenience only — never use these settings in prod.
#
# Usage:
#   scripts/db.sh init     # first-time: create datadir + database + app user
#   scripts/db.sh start     # start the server (idempotent)
#   scripts/db.sh stop      # stop the server
#   scripts/db.sh status    # is it up?
#   scripts/db.sh reset      # wipe datadir and re-init (destroys all data)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATADIR="$ROOT/.mysql-data"
PORT=3307
SOCK="/tmp/yp_mysql.sock"
PIDFILE="/tmp/yp_mysqld.pid"
LOG="$ROOT/.mysql-data.log"

DB_NAME="yatrapulse"
DB_USER="yatra"
DB_PASS="yatra_dev_pw"

is_up() { mysql -uroot -h127.0.0.1 -P"$PORT" -e "SELECT 1;" >/dev/null 2>&1; }

wait_up() {
  for _ in $(seq 1 30); do is_up && return 0; sleep 1; done
  echo "MySQL did not come up. See $LOG" >&2; tail -10 "$LOG" >&2 || true; return 1
}

do_init() {
  if [ -d "$DATADIR" ] && [ -n "$(ls -A "$DATADIR" 2>/dev/null)" ]; then
    echo "Datadir already initialized. Use 'reset' to wipe."; else
    echo "Initializing MySQL datadir..."
    mkdir -p "$DATADIR"
    mysqld --initialize-insecure --datadir="$DATADIR" > "$LOG" 2>&1
    # Workaround for a MySQL 9.x macOS bug: remove undo tablespaces so InnoDB
    # recreates them cleanly on first start.
    rm -f "$DATADIR/undo_001" "$DATADIR/undo_002"
  fi
  do_start
  echo "Creating database and app user..."
  mysql -uroot -h127.0.0.1 -P"$PORT" <<SQL
CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_USER'@'%' IDENTIFIED BY '$DB_PASS';
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'%';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
SQL
  echo "Done. Database '$DB_NAME' ready on port $PORT."
}

do_start() {
  if is_up; then echo "MySQL already running on port $PORT."; return 0; fi
  echo "Starting MySQL on port $PORT..."
  nohup mysqld --datadir="$DATADIR" --port="$PORT" --socket="$SOCK" \
    --mysqlx=0 --pid-file="$PIDFILE" > "$LOG" 2>&1 &
  disown || true
  wait_up
  echo "MySQL up (port $PORT, socket $SOCK)."
}

do_stop() {
  if [ -f "$PIDFILE" ]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
  fi
  pkill -f "$DATADIR" 2>/dev/null || true
  echo "Stopped."
}

do_status() {
  if is_up; then echo "UP (port $PORT)"; else echo "DOWN"; fi
}

do_reset() {
  do_stop; sleep 1
  rm -rf "$DATADIR"
  echo "Datadir wiped."
  do_init
}

case "${1:-}" in
  init) do_init ;;
  start) do_start ;;
  stop) do_stop ;;
  status) do_status ;;
  reset) do_reset ;;
  *) echo "Usage: $0 {init|start|stop|status|reset}"; exit 1 ;;
esac
