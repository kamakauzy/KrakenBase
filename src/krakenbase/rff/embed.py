"""Frozen builtin embedder v0. Not the BAE paper net. Offline, no torch."""

from __future__ import annotations

import math
import struct
from pathlib import Path

from krakenbase.rff.sigmf_io import read_sigmf

EMBEDDER_ID = "builtin_v0"
DIM = 32
MAX_SAMPLES = 512


def _iq_from_blob(datatype: str, blob: bytes) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    if datatype == "cu8":
        for i in range(0, len(blob) - 1, 2):
            out.append(((blob[i] - 127.5) / 127.5, (blob[i + 1] - 127.5) / 127.5))
    elif datatype == "cf32_le":
        for i in range(0, len(blob) - 7, 8):
            out.append(struct.unpack_from("<ff", blob, i))
    else:
        raise ValueError(f"unsupported datatype {datatype}")
    if len(out) > MAX_SAMPLES:
        step = len(out) / MAX_SAMPLES
        out = [out[int(i * step)] for i in range(MAX_SAMPLES)]
    return out


def _l2(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def embed_iq(iq: list[tuple[float, float]]) -> list[float]:
    if not iq:
        return [0.0] * DIM
    n = len(iq)
    mi = sum(p[0] for p in iq) / n
    mq = sum(p[1] for p in iq) / n
    vi = math.sqrt(sum((p[0] - mi) ** 2 for p in iq) / n)
    vq = math.sqrt(sum((p[1] - mq) ** 2 for p in iq) / n)
    powers = [p[0] * p[0] + p[1] * p[1] for p in iq]
    mean_p = sum(powers) / n
    max_p = max(powers)
    papr = max_p / mean_p if mean_p else 0.0
    mag_mean = math.sqrt(mi * mi + mq * mq)
    bins = [0.0] * 8
    for k in range(8):
        re = im = 0.0
        for i, (ii, qq) in enumerate(iq):
            ang = 2 * math.pi * k * i / n
            c, s = math.cos(ang), math.sin(ang)
            re += ii * c + qq * s
            im += qq * c - ii * s
        bins[k] = math.sqrt(re * re + im * im) / n
    hist = [0.0] * 8
    for pwr in powers:
        a = math.sqrt(pwr)
        idx = min(7, int(a * 8))
        hist[idx] += 1.0
    hist = [h / n for h in hist]
    dpow = 0.0
    zc = 0
    prev = iq[0][0]
    for i in range(1, n):
        dpow += (powers[i] - powers[i - 1]) ** 2
        if prev * iq[i][0] < 0:
            zc += 1
        prev = iq[i][0]
    vec = [mi, mq, vi, vq, mean_p, max_p, papr, mag_mean] + bins + hist + [
        dpow / n,
        zc / n,
        min(1.0, n / MAX_SAMPLES),
        mean_p - vi,
    ]
    while len(vec) < DIM:
        vec.append(0.0)
    return _l2(vec[:DIM])


def embed_sigmf(meta_path: str | Path) -> tuple[list[float], dict]:
    meta, blob = read_sigmf(meta_path)
    g = meta["global"]
    iq = _iq_from_blob(g["core:datatype"], blob)
    vec = embed_iq(iq)
    info = {
        "embedder_id": EMBEDDER_ID,
        "dim": DIM,
        "recipe_id": g.get("krakenbase:recipe_id"),
        "sensor_id": g.get("krakenbase:sensor_id"),
        "sensor_class": g.get("krakenbase:sensor_class"),
        "freq_hz": meta["captures"][0]["core:frequency"] if meta.get("captures") else None,
        "hw": g.get("core:hw"),
    }
    return vec, info


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
