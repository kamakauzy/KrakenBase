"""R4 SNR/label gates + U4 RSP1B-only pole embed."""

from pathlib import Path

from krakenbase.models import RffDisposition
from krakenbase.rff.capture import capture_burst
from krakenbase.rff.gallery import Gallery
from krakenbase.rff.recipe import get_recipe
from krakenbase.rff.sigmf_io import write_sigmf
from krakenbase.ugs.node import UgsNode


def test_low_snr_does_not_gallery(tmp_path: Path):
    meta = write_sigmf(
        tmp_path / "quiet", b"\x00" * 256, datatype="cf32_le", sample_rate=48000,
        freq_hz=462_712_500, hw="synthetic",
        extra_global={"krakenbase:recipe_id": "synthetic:48k:0", "krakenbase:sensor_id": "s0"},
    )
    gal = Gallery(tmp_path / "g.db")
    res = gal.ingest_sigmf(meta, min_snr_db=8.0)
    assert res.disposition == RffDisposition.LOW_SNR
    assert gal.list_emitters() == []


def test_operator_label(tmp_path: Path):
    rec = get_recipe("synthetic:48k:0")
    burst = capture_burst(462_712_500, rec, tmp_path, sensor_id="s0", backend="synthetic")
    gal = Gallery(tmp_path / "g.db")
    first = gal.ingest_sigmf(burst.meta_path)
    assert gal.label(first.emitter_uid, "baofeng-red")
    assert not gal.label("nope", "x")
    assert gal.list_emitters()[0]["label"] == "baofeng-red"


def test_u4_refuses_non_rsp1b(tmp_path: Path):
    gal = Gallery(tmp_path / "g.db")
    node = UgsNode(
        node_id="ugs-west", out_dir=tmp_path / "ugs", recipe=get_recipe("rtl_v4:2.4e6:30"),
        sensor_id="s0", backend="synthetic", embed=True, gallery=gal, rate_limit_s=0.0,
    )
    ev = node.synthetic_trigger(462_712_500)
    assert ev is not None
    assert "embed=refused" in (ev.notes or "")


def test_u4_rsp1b_embeds(tmp_path: Path):
    gal = Gallery(tmp_path / "g.db")
    node = UgsNode(
        node_id="ugs-rsp", out_dir=tmp_path / "ugs", recipe=get_recipe("rsp1b:2e6:20"),
        sensor_id="rsp0", backend="synthetic", embed=True, gallery=gal, rate_limit_s=0.0, min_snr_db=0.0,
    )
    ev = node.synthetic_trigger(462_712_500)
    assert ev is not None
    assert "rff=" in (ev.notes or "")
    assert gal.list_emitters()
