"""RFF fuse. Stub if no burst/gallery; else builtin embedder + gallery."""

from __future__ import annotations

from pathlib import Path

from krakenbase.models import DoaEvent, RffDisposition, RffResult, utcnow
from krakenbase.rff.gallery import Gallery


def fuse_stub(doa: DoaEvent, sensor_id: str = "none", recipe_id: str = "none") -> RffResult:
    return RffResult(
        timestamp=utcnow(),
        freq_hz=doa.freq_hz,
        sensor_id=sensor_id,
        recipe_id=recipe_id,
        disposition=RffDisposition.NO_MODEL,
        source_event_id=doa.event_id,
        notes="no burst / no gallery",
    )


def fuse(
    doa: DoaEvent | None = None,
    *,
    burst_meta: str | Path | None = None,
    gallery: Gallery | None = None,
    gallery_path: str | Path | None = None,
    sensor_id: str = "none",
    recipe_id: str = "none",
) -> RffResult:
    if burst_meta is None or (gallery is None and gallery_path is None):
        if doa is None:
            return RffResult(
                freq_hz=0,
                sensor_id=sensor_id,
                recipe_id=recipe_id,
                disposition=RffDisposition.NO_MODEL,
                notes="no burst / no gallery",
            )
        return fuse_stub(doa, sensor_id, recipe_id)
    gal = gallery or Gallery(gallery_path)
    owned = gallery is None
    try:
        src = doa.event_id if doa else None
        freq = doa.freq_hz if doa else None
        return gal.ingest_sigmf(
            burst_meta,
            sensor_id=sensor_id,
            recipe_id=recipe_id,
            source_event_id=src,
            freq_hz=freq,
        )
    finally:
        if owned:
            gal.close()
