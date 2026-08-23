"""R2 gallery + embedder."""

from pathlib import Path

from krakenbase.models import RffDisposition
from krakenbase.rff.capture import capture_burst
from krakenbase.rff.embed import cosine, embed_sigmf
from krakenbase.rff.fuse import fuse
from krakenbase.rff.gallery import Gallery
from krakenbase.rff.recipe import get_recipe


def _burst(tmp: Path, stem: str):
    rec = get_recipe("synthetic:48k:0")
    return capture_burst(462_712_500, rec, tmp, sensor_id="rsp-sim", backend="synthetic", stem=stem)


def test_same_burst_matches(tmp_path: Path):
    a = _burst(tmp_path, "a")
    b = _burst(tmp_path, "b")
    va, _ = embed_sigmf(a.meta_path)
    vb, _ = embed_sigmf(b.meta_path)
    assert cosine(va, vb) > 0.99
    gal = Gallery(tmp_path / "g.db")
    first = gal.ingest_sigmf(a.meta_path)
    assert first.disposition == RffDisposition.NEW
    second = gal.ingest_sigmf(b.meta_path)
    assert second.disposition in (RffDisposition.RFF_MATCH, RffDisposition.REPEAT)
    assert second.emitter_uid == first.emitter_uid
    assert second.score and second.score > 0.92


def test_recipe_mismatch(tmp_path: Path):
    burst = _burst(tmp_path, "c")
    gal = Gallery(tmp_path / "g.db")
    res = gal.ingest_sigmf(burst.meta_path, recipe_id="rtl_v4:2.4e6:30")
    assert res.disposition == RffDisposition.RECIPE_MISMATCH


def test_label_is_operator_only(tmp_path: Path):
    burst = _burst(tmp_path, "d")
    gal = Gallery(tmp_path / "g.db")
    res = gal.ingest_sigmf(burst.meta_path)
    assert res.emitter_uid.startswith("unk_")
    gal.label(res.emitter_uid, "baofeng-site")
    rows = gal.list_emitters()
    assert rows[0]["label"] == "baofeng-site"
    assert rows[0]["labeled"] == 1


def test_fuse_without_burst_is_no_model():
    from datetime import datetime, timezone
    from krakenbase.models import DoaEvent, DoaReading

    doa = DoaEvent(
        freq_hz=1, bearing_deg=0, confidence=1, rssi_db=-40, dwell_s=1,
        reading=DoaReading(timestamp=datetime.now(timezone.utc), bearing_deg=0, confidence=1, rssi_db=-40, freq_hz=1),
    )
    assert fuse(doa).disposition == RffDisposition.NO_MODEL
