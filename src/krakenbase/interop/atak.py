"""Minimal CoT file drop. Not a TAK server."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def write_cot(
    out_dir: str | Path,
    *,
    uid: str,
    callsign: str,
    lat: float | None,
    lon: float | None,
    remarks: str,
    when: datetime | None = None,
    stale_min: int = 30,
) -> Path | None:
    if lat is None or lon is None:
        return None
    when = when or datetime.now(timezone.utc)
    stale = when + timedelta(minutes=stale_min)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{uid}.cot"
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<event version="2.0" uid="{escape(uid)}" type="a-u-G" how="m-g" '
        f'time="{_iso(when)}" start="{_iso(when)}" stale="{_iso(stale)}">\n'
        f'  <point lat="{lat:.6f}" lon="{lon:.6f}" hae="0" ce="9999999" le="9999999"/>\n'
        f'  <detail>\n'
        f'    <contact callsign="{escape(callsign[:32])}"/>\n'
        f'    <remarks>{escape(remarks[:200])}</remarks>\n'
        f'  </detail>\n'
        f'</event>\n'
    )
    path.write_text(xml)
    return path
