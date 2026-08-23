"""R1 burst capture: synthetic always, rtl_sdr if installed, RSP1B not in R1 runtime."""

from __future__ import annotations

import logging
import math
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from krakenbase.rff.recipe import CaptureRecipe
from krakenbase.rff.sigmf_io import write_sigmf

logger = logging.getLogger(__name__)


@dataclass
class BurstCapture:
    meta_path: Path
    data_path: Path
    recipe_id: str
    sensor_id: str
    freq_hz: int
    sample_count: int
    backend: str


def _synthetic_cf32(recipe: CaptureRecipe, freq_hz: int) -> bytes:
    n = recipe.sample_count
    sr = recipe.sample_rate
    tone = min(sr * 0.1, 5000.0)
    out = bytearray()
    for i in range(n):
        t = i / sr
        nval = ((i * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF - 0.5
        i_s = 0.6 * math.cos(2 * math.pi * tone * t) + 0.02 * nval
        q_s = 0.6 * math.sin(2 * math.pi * tone * t) + 0.02 * nval
        out += struct.pack("<ff", i_s, q_s)
    return bytes(out)


def _synthetic_cu8(recipe: CaptureRecipe, freq_hz: int) -> bytes:
    raw = _synthetic_cf32(recipe, freq_hz)
    out = bytearray()
    for i in range(0, len(raw), 8):
        i_s, q_s = struct.unpack_from("<ff", raw, i)
        iu = max(0, min(255, int((i_s * 0.5 + 0.5) * 255)))
        qu = max(0, min(255, int((q_s * 0.5 + 0.5) * 255)))
        out += bytes((iu, qu))
    return bytes(out)


def _rtl_sdr(recipe: CaptureRecipe, freq_hz: int, dest: Path) -> bytes:
    exe = shutil.which("rtl_sdr")
    if not exe:
        raise FileNotFoundError("rtl_sdr not on PATH")
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = recipe.sample_count
    cmd = [
        exe, "-f", str(int(freq_hz)), "-s", str(int(recipe.sample_rate)),
        "-g", str(recipe.gain_db), "-n", str(n), str(dest),
    ]
    logger.info("rtl_sdr %s", " ".join(cmd[1:]))
    timeout = max(15, int(recipe.duration_ms / 1000) + 20)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"rtl_sdr exit {proc.returncode}")
    return dest.read_bytes()


def capture_burst(
    freq_hz: int,
    recipe: CaptureRecipe,
    out_dir: str | Path,
    *,
    sensor_id: str,
    backend: str = "auto",
    stem: str | None = None,
    description: str = "",
) -> BurstCapture:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = stem or f"{sensor_id}_{freq_hz}_{recipe.recipe_id.replace(':', '_')}"
    stem_path = out_dir / name

    chosen = backend
    if backend == "auto":
        if recipe.sensor_class.startswith("rtl") and shutil.which("rtl_sdr"):
            chosen = "rtl"
        else:
            chosen = "synthetic"

    extra = {
        "krakenbase:recipe_id": recipe.recipe_id,
        "krakenbase:sensor_id": sensor_id,
        "krakenbase:sensor_class": recipe.sensor_class,
        "krakenbase:backend": chosen,
    }

    if chosen == "rtl":
        raw_path = Path(str(stem_path) + ".cu8")
        blob = _rtl_sdr(recipe, freq_hz, raw_path)
        datatype = "cu8"
        hw = recipe.sensor_class
    elif chosen == "synthetic":
        if recipe.datatype == "cu8":
            blob = _synthetic_cu8(recipe, freq_hz)
            datatype = "cu8"
        else:
            blob = _synthetic_cf32(recipe, freq_hz)
            datatype = "cf32_le"
        hw = "synthetic"
        extra["krakenbase:synthetic"] = True
    else:
        raise ValueError(f"unknown backend {chosen}")

    meta = write_sigmf(
        stem_path,
        blob,
        datatype=datatype,
        sample_rate=recipe.sample_rate,
        freq_hz=freq_hz,
        hw=hw,
        description=description or f"R1 burst {recipe.recipe_id}",
        extra_global=extra,
    )
    data = Path(str(stem_path) + ".sigmf-data")
    return BurstCapture(
        meta_path=meta,
        data_path=data,
        recipe_id=recipe.recipe_id,
        sensor_id=sensor_id,
        freq_hz=freq_hz,
        sample_count=recipe.sample_count,
        backend=chosen,
    )
