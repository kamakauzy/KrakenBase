"""SQLite event store."""

from __future__ import annotations

import json
import logging
from datetime import datetime
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
        logger.info("Event store opened at %s", self.db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def _insert(self, event_id: UUID, event_type: str, payload: dict[str, Any], related_id: UUID | None = None) -> None:
        assert self._db is not None
        ts = payload.get("timestamp") or utcnow().isoformat()
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        await self._db.execute(
            "INSERT OR REPLACE INTO events (id, type, timestamp, payload, related_id) VALUES (?, ?, ?, ?, ?)",
            (
                str(event_id),
                event_type,
                ts,
                json.dumps(payload, default=str),
                str(related_id) if related_id else None,
            ),
        )
        await self._db.commit()

    async def log_anomaly(self, event: AnomalyEvent) -> None:
        await self._insert(event.event_id, "anomaly", event.model_dump(mode="json"))

    async def log_doa(self, event: DoaEvent) -> None:
        await self._insert(
            event.event_id,
            "doa",
            event.model_dump(mode="json"),
            related_id=event.related_anomaly_id,
        )

    async def log_alert(self, event: AlertEvent) -> None:
        await self._insert(
            event.event_id,
            "alert",
            event.model_dump(mode="json"),
            related_id=event.related_doa_id,
        )

    async def log_handoff(self, task: HandOffTask) -> None:
        await self._insert(
            task.task_id,
            "handoff",
            task.model_dump(mode="json"),
            related_id=task.source_event_id,
        )

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
        results = []
        for row in rows:
            results.append(
                {
                    "id": row[0],
                    "type": row[1],
                    "timestamp": row[2],
                    "payload": json.loads(row[3]),
                    "related_id": row[4],
                }
            )
        return results
