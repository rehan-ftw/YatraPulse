"""WebSocket connection manager and the structured live-update message model."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import WebSocket


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Message builders (structured message model) ---------------------------

def eta_updated(train_id, train_number, previous_eta, new_eta, delay, reason):
    return {
        "type": "ETA_UPDATED",
        "train_id": train_id,
        "train_number": train_number,
        "previous_eta": previous_eta,
        "new_eta": new_eta,
        "delay_minutes": delay,
        "reason": reason,
        "timestamp": _now_iso(),
    }


def train_movement_updated(train_id, train_number, lat, lng, current_station, next_station):
    return {
        "type": "TRAIN_MOVEMENT_UPDATED",
        "train_id": train_id,
        "train_number": train_number,
        "latitude": lat,
        "longitude": lng,
        "current_station": current_station,
        "next_station": next_station,
        "timestamp": _now_iso(),
    }


def operational_event(event_type, train_id, train_number, location, impact_minutes, reason):
    return {
        "type": "OPERATIONAL_EVENT",
        "event_type": event_type,
        "train_id": train_id,
        "train_number": train_number,
        "location": location,
        "impact_minutes": impact_minutes,
        "reason": reason,
        "timestamp": _now_iso(),
    }


def downstream_impact_updated(source_train, source_train_name, reason, affected):
    return {
        "type": "DOWNSTREAM_IMPACT_UPDATED",
        "source_train": source_train,
        "source_train_name": source_train_name,
        "reason": reason,
        "affected_count": len(affected),
        "affected_trains": affected,
        "note": "SIMULATED IMPACT",
        "timestamp": _now_iso(),
    }


def simulation_state_changed(train_id, train_number, state):
    return {
        "type": "SIMULATION_STATE_CHANGED",
        "train_id": train_id,
        "train_number": train_number,
        "state": state,
        "timestamp": _now_iso(),
    }


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)


manager = ConnectionManager()
