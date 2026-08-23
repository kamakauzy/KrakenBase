"""Minimal SigMF writer/reader. No extra deps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SIGMF_VERSION = "1.0.0"


def write_sigmf(
    dest_stem: str | Path,
    samples: bytes,
    *,
    datatype: str,
    sample_rate: float,
    freq_hz: int,
    hw: str,
    description: str = "",
    extra_global: dict[str, Any] | None = None,
    captured_at: datetime | None = None,
) -> Path:
    stem = Path(dest_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    data_path = Path(str(stem) + ".sigmf-data")
    meta_path = Path(str(stem) + ".sigmf-meta")
    data_path.write_bytes(samples)
    ts = (captured_at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    global_block: dict[str, Any] = {
        "core:datatype": datatype,
        "core:sample_rate": float(sample_rate),
        "core:version": SIGMF_VERSION,
        "core:hw": hw,
        "core:description": description,
        "core:num_channels": 1,
    }
    if extra_global:
        global_block.update(extra_global)
    meta = {
        "global": global_block,
        "captures": [
            {
                "core:sample_start": 0,
                "core:frequency": int(freq_hz),
                "core:datetime": ts,
            }
        ],
        "annotations": [],
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta_path


def read_sigmf(meta_path: str | Path) -> tuple[dict[str, Any], bytes]:
    meta_path = Path(meta_path)
    meta = json.loads(meta_path.read_text())
    data_path = Path(str(meta_path).replace(".sigmf-meta", ".sigmf-data"))
    return meta, data_path.read_bytes()


def validate_pair(meta_path: str | Path) -> None:
    meta, blob = read_sigmf(meta_path)
    g = meta["global"]
    assert g["core:datatype"] in ("cu8", "cf32_le", "ci16_le")
    assert g["core:sample_rate"] > 0
    assert meta["captures"]
    assert len(blob) > 0
