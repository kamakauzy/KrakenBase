"""R3: find a burst and fuse without owning the DF loop."""

from __future__ import annotations

from pathlib import Path

from krakenbase.models import DoaEvent, RffResult
from krakenbase.rff.fuse import fuse, fuse_stub
from krakenbase.rff.gallery import Gallery


def find_burst(burst_dir: str | Path | None, freq_hz: int) -> Path | None:
    if not burst_dir:
        return None
    root = Path(burst_dir)
    if not root.is_dir():
        return None
    needle = str(int(freq_hz))
    hits = [p for p in root.glob("*.sigmf-meta") if needle in p.name]
    if not hits:
        hits = list(root.glob("*.sigmf-meta"))
    if not hits:
        return None
    return max(hits, key=lambda p: p.stat().st_mtime)


def fuse_doa(
    doa: DoaEvent,
    *,
    gallery: Gallery | None,
    burst_dir: str | Path | None,
    sensor_id: str,
    recipe_id: str,
    min_snr_db: float | None = None,
) -> RffResult:
    burst = find_burst(burst_dir, doa.freq_hz)
    if gallery is None or burst is None:
        return fuse_stub(doa, sensor_id=sensor_id, recipe_id=recipe_id)
    return fuse(
        doa, burst_meta=burst, gallery=gallery, sensor_id=sensor_id, recipe_id=recipe_id, min_snr_db=min_snr_db,
    )
