"""Recon-Raven interop – export/import bridge events."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

logger = logging.getLogger(__name__)


def kb_event_to_rr(row: dict[str, Any], site_id: str = "krakenbase") -> dict[str, Any]:
    payload = row.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    kind = row.get("type") or payload.get("type") or "event"
    ts = row.get("timestamp") or payload.get("timestamp")
    if isinstance(ts, datetime):
        ts = ts.isoformat()

    tags: list[str] = []
    clf = payload.get("classification") or {}
    if isinstance(clf, dict):
        for lab in clf.get("labels") or []:
            tags.append(str(lab))
        if clf.get("known_name"):
            tags.append(f"known:{clf['known_name']}")
        if clf.get("band_name"):
            tags.append(f"band:{clf['band_name']}")

    return {
        "id": str(row.get("id") or payload.get("event_id") or uuid4()),
        "ts": ts,
        "kind": kind,
        "site": site_id,
        "freq_hz": payload.get("freq_hz"),
        "bearing_deg": payload.get("bearing_deg") or payload.get("absolute_bearing_deg"),
        "confidence": payload.get("confidence") or (clf.get("confidence") if isinstance(clf, dict) else None),
        "power_db": payload.get("power_db") or payload.get("rssi_db"),
        "margin_db": payload.get("margin_db"),
        "tags": tags,
        "source": "krakenbase",
        "raw": {"related_id": row.get("related_id"), "kb_type": kind},
    }


def export_events_jsonl(
    rows: Iterable[dict[str, Any]],
    out_path: str | Path,
    site_id: str = "krakenbase",
) -> int:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w") as f:
        for row in rows:
            evt = kb_event_to_rr(row, site_id=site_id)
            f.write(json.dumps(evt, default=str) + "\n")
            n += 1
    logger.info("Exported %d events to %s", n, path)
    return n


def import_rr_jsonl(path: str | Path) -> list[dict[str, Any]]:
    events = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
