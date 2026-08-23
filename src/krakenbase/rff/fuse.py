"""RFF fuse stub. No ONNX, no gallery, no auto-promote."""

from __future__ import annotations

from krakenbase.models import DoaEvent, RffDisposition, RffResult, utcnow


def fuse_stub(doa: DoaEvent, sensor_id: str = "none", recipe_id: str = "none") -> RffResult:
    """Always NO_MODEL until R2 ships a frozen embedding."""
    return RffResult(
        timestamp=utcnow(),
        freq_hz=doa.freq_hz,
        sensor_id=sensor_id,
        recipe_id=recipe_id,
        disposition=RffDisposition.NO_MODEL,
        source_event_id=doa.event_id,
        notes="no onnx / no gallery",
    )
