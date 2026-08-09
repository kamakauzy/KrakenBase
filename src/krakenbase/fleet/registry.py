"""Persistent fleet registry for secondary monitor nodes (SQLite-backed)."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from krakenbase.models import SecondaryNode, SecondaryNodeStatus, utcnow

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    last_seen TEXT NOT NULL,
    status TEXT NOT NULL,
    capabilities TEXT,
    current_freq_hz INTEGER,
    last_task_id TEXT,
    site TEXT,
    notes TEXT
);
"""


class FleetRegistry:
    """Track secondary nodes by heartbeat. Survives process restart."""

    def __init__(self, offline_after_s: float = 90.0, db_path: str | Path | None = None):
        self.offline_after_s = offline_after_s
        self.db_path = Path(db_path) if db_path else None
        self._nodes: dict[str, SecondaryNode] = {}
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.db_path))
            self._db.execute(SCHEMA)
            self._db.commit()
            self._load()
        else:
            self._db = None

    def _load(self) -> None:
        if not self._db:
            return
        cur = self._db.execute(
            "SELECT node_id, last_seen, status, capabilities, current_freq_hz, last_task_id, site, notes FROM nodes"
        )
        for row in cur.fetchall():
            try:
                caps = json.loads(row[3]) if row[3] else ["rtl_sdr"]
            except Exception:
                caps = ["rtl_sdr"]
            try:
                status = SecondaryNodeStatus(row[2])
            except ValueError:
                status = SecondaryNodeStatus.UNKNOWN
            try:
                last_seen = datetime.fromisoformat(row[1])
            except Exception:
                last_seen = utcnow()
            self._nodes[row[0]] = SecondaryNode(
                node_id=row[0],
                last_seen=last_seen,
                status=status,
                capabilities=caps,
                current_freq_hz=row[4],
                last_task_id=row[5],
                site=row[6],
                notes=row[7],
            )
        logger.info("Fleet loaded %d nodes from %s", len(self._nodes), self.db_path)

    def _persist(self, node: SecondaryNode) -> None:
        if not self._db:
            return
        self._db.execute(
            "INSERT OR REPLACE INTO nodes (node_id, last_seen, status, capabilities, current_freq_hz, last_task_id, site, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                node.node_id,
                node.last_seen.isoformat(),
                node.status.value,
                json.dumps(node.capabilities),
                node.current_freq_hz,
                node.last_task_id,
                node.site,
                node.notes,
            ),
        )
        self._db.commit()

    def heartbeat(
        self,
        node_id: str,
        status: SecondaryNodeStatus | str = SecondaryNodeStatus.ONLINE,
        capabilities: list[str] | None = None,
        current_freq_hz: int | None = None,
        last_task_id: str | None = None,
        site: str | None = None,
        notes: str | None = None,
    ) -> SecondaryNode:
        if isinstance(status, str):
            try:
                status = SecondaryNodeStatus(status)
            except ValueError:
                status = SecondaryNodeStatus.UNKNOWN
        existing = self._nodes.get(node_id)
        node = SecondaryNode(
            node_id=node_id,
            last_seen=utcnow(),
            status=status,
            capabilities=capabilities or (existing.capabilities if existing else ["rtl_sdr"]),
            current_freq_hz=current_freq_hz if current_freq_hz is not None else (existing.current_freq_hz if existing else None),
            last_task_id=last_task_id or (existing.last_task_id if existing else None),
            site=site or (existing.site if existing else None),
            notes=notes or (existing.notes if existing else None),
        )
        self._nodes[node_id] = node
        self._persist(node)
        return node

    def mark_busy(self, node_id: str, freq_hz: int, task_id: str | None = None) -> SecondaryNode | None:
        node = self._nodes.get(node_id)
        if not node:
            return self.heartbeat(node_id, status=SecondaryNodeStatus.BUSY, current_freq_hz=freq_hz, last_task_id=task_id)
        return self.heartbeat(
            node_id,
            status=SecondaryNodeStatus.BUSY,
            current_freq_hz=freq_hz,
            last_task_id=task_id,
            capabilities=node.capabilities,
            site=node.site,
        )

    def list_nodes(self, refresh_offline: bool = True) -> list[SecondaryNode]:
        if refresh_offline:
            self._refresh_offline()
        return sorted(self._nodes.values(), key=lambda n: n.node_id)

    def online_nodes(self) -> list[SecondaryNode]:
        self._refresh_offline()
        return [n for n in self._nodes.values() if n.status in (SecondaryNodeStatus.ONLINE, SecondaryNodeStatus.BUSY)]

    def pick_idle(self) -> SecondaryNode | None:
        self._refresh_offline()
        for n in sorted(self._nodes.values(), key=lambda x: x.node_id):
            if n.status == SecondaryNodeStatus.ONLINE:
                return n
        return None

    def _refresh_offline(self) -> None:
        cutoff = utcnow() - timedelta(seconds=self.offline_after_s)
        for nid, node in list(self._nodes.items()):
            if node.last_seen < cutoff and node.status != SecondaryNodeStatus.OFFLINE:
                updated = node.model_copy(update={"status": SecondaryNodeStatus.OFFLINE})
                self._nodes[nid] = updated
                self._persist(updated)
