"""U3: ingest pole events at the shop. No auto-TX. Cue is opt-in."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from krakenbase.config import BandConfig
from krakenbase.interop.atak import write_cot
from krakenbase.interop.recon_raven import kb_event_to_rr
from krakenbase.models import UgsEvent

logger = logging.getLogger(__name__)


def in_monitored_band(freq_hz: int | None, bands: list[BandConfig]) -> bool:
    if freq_hz is None:
        return False
    return any(b.start_hz <= freq_hz <= b.stop_hz for b in bands)


def should_cue(event: UgsEvent, bands: list[BandConfig], cue_dwell: bool) -> bool:
    return bool(cue_dwell and in_monitored_band(event.freq_hz, bands))


def load_ugs_file(path: str | Path) -> UgsEvent:
    return UgsEvent.model_validate(json.loads(Path(path).read_text()))


def scan_ugs_dir(watch: str | Path, seen: set[str]) -> list[UgsEvent]:
    watch = Path(watch)
    if not watch.exists():
        return []
    out: list[UgsEvent] = []
    for path in watch.glob("*.ugs.json"):
        key = path.name
        if key in seen:
            continue
        try:
            ev = load_ugs_file(path)
        except Exception as exc:
            logger.warning("bad ugs file %s: %s", path.name, exc)
            continue
        seen.add(key)
        out.append(ev)
    feed = watch / "ugs.jsonl"
    if feed.exists():
        for i, line in enumerate(feed.read_text().splitlines()):
            key = f"jsonl:{i}:{line[:40]}"
            if key in seen or not line.strip():
                continue
            try:
                ev = UgsEvent.model_validate(json.loads(line))
            except Exception:
                continue
            seen.add(key)
            out.append(ev)
    return out


def export_ugs(event: UgsEvent, *, site_id: str, lat: float | None, lon: float | None, atak_dir: str | None, rr_path: str | None) -> None:
    row = {
        "id": str(event.event_id),
        "type": "ugs",
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "payload": event.model_dump(mode="json"),
    }
    if rr_path:
        p = Path(rr_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(kb_event_to_rr(row, site_id=site_id), default=str) + "\n")
    if atak_dir:
        mhz = f"{event.freq_hz/1e6:.3f}" if event.freq_hz else "?"
        write_cot(
            atak_dir,
            uid=f"KB-UGS-{event.node_id}-{str(event.event_id)[:8]}",
            callsign=f"{event.node_id} {mhz}",
            lat=event.lat if event.lat is not None else lat,
            lon=event.lon if event.lon is not None else lon,
            remarks=f"ugs {event.trigger.value} {mhz} MHz {event.recipe_id}",
            when=event.timestamp,
        )
