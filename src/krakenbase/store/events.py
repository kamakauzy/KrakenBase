"""SQLite event store."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import aiosqlite

from krakenbase.models import AlertEvent, AnomalyEvent, DoaEvent, HandOffTask, utcnow

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload TEXT NOT NULL,
    related_id TEXT
);
CREATE TABLE IF NOT EXISTS state_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
"""


class EventStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def _insert(self, event_id: UUID, event_type: str, payload: dict[str, Any], related_id=None) -> None:
        assert self._db is not None
        rel = str(related_id) if related_id else None
        await self._db.execute(
            "INSERT INTO events (id, type, timestamp, payload, related_id) VALUES (?, ?, ?, ?, ?)",
            (str(event_id), event_type, payload.get("timestamp") or utcnow().isoformat(), json.dumps(payload, default=str), rel),
        )
        await self._db.commit()

    async def log_anomaly(self, event: AnomalyEvent, extra: dict[str, Any] | None = None) -> None:
        payload = event.model_dump(mode="json")
        if extra:
            payload.update(extra)
        await self._insert(event.event_id, "anomaly", payload)

    async def log_doa(self, event: DoaEvent) -> None:
        await self._insert(event.event_id, "doa", event.model_dump(mode="json"), related_id=event.related_anomaly_id)

    async def log_alert(self, event: AlertEvent) -> None:
        await self._insert(event.event_id, "alert", event.model_dump(mode="json"), related_id=event.related_doa_id)

    async def log_handoff(self, task: HandOffTask) -> None:
        await self._insert(task.task_id, "handoff", task.model_dump(mode="json"), related_id=task.source_event_id)

    async def log_state_change(self, from_state: str, to_state: str, reason: str = "") -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO state_log (timestamp, from_state, to_state, reason) VALUES (?, ?, ?, ?)",
            (utcnow().isoformat(), from_state, to_state, reason),
        )
        await self._db.commit()

    async def recent(self, limit: int = 50, event_type: str | None = None) -> list[dict[str, Any]]:
        assert self._db is not None
        if event_type:
            cursor = await self._db.execute(
                "SELECT id, type, timestamp, payload, related_id FROM events WHERE type = ? ORDER BY timestamp DESC LIMIT ?",
                (event_type, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT id, type, timestamp, payload, related_id FROM events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [{"id": r[0], "type": r[1], "timestamp": r[2], "payload": json.loads(r[3]), "related_id": r[4]} for r in rows]

    async def purge_older_than(self, days: float) -> int:
        assert self._db is not None
        if days <= 0:
            return 0
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        cur1 = await self._db.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        cur2 = await self._db.execute("DELETE FROM state_log WHERE timestamp < ?", (cutoff,))
        await self._db.commit()
        deleted = (cur1.rowcount or 0) + (cur2.rowcount or 0)
        if deleted:
            logger.info("Retention purge: removed %s rows older than %.1f days", deleted, days)
        return deleted
