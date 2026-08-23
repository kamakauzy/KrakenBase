"""R3 live fuse tags + U3 ingest / cue / ATAK / RR."""

from datetime import datetime, timezone
from pathlib import Path

from krakenbase.config import BandConfig, HandOffSettings
from krakenbase.handoff.publisher import HandOffPublisher
from krakenbase.interop.atak import write_cot
from krakenbase.interop.recon_raven import kb_event_to_rr
from krakenbase.models import DoaEvent, DoaReading, RffDisposition, RffResult, UgsEvent, UgsTrigger
from krakenbase.rff.capture import capture_burst
from krakenbase.rff.gallery import Gallery
from krakenbase.rff.live import find_burst, fuse_doa
from krakenbase.rff.recipe import get_recipe
from krakenbase.ugs.bridge import in_monitored_band, scan_ugs_dir, should_cue


def _doa(freq=462_712_500) -> DoaEvent:
    r = DoaReading(timestamp=datetime.now(timezone.utc), bearing_deg=10, confidence=90, rssi_db=-40, freq_hz=freq)
    return DoaEvent(freq_hz=freq, bearing_deg=10, confidence=90, rssi_db=-40, dwell_s=1, reading=r)


def test_find_and_fuse_live(tmp_path: Path):
    rec = get_recipe("synthetic:48k:0")
    burst = capture_burst(462_712_500, rec, tmp_path, sensor_id="s0", backend="synthetic", stem="x_462712500")
    assert find_burst(tmp_path, 462_712_500) == burst.meta_path
    gal = Gallery(tmp_path / "g.db")
    first = fuse_doa(_doa(), gallery=gal, burst_dir=tmp_path, sensor_id="s0", recipe_id=rec.recipe_id)
    assert first.disposition == RffDisposition.NEW
    second = fuse_doa(_doa(), gallery=gal, burst_dir=tmp_path, sensor_id="s0", recipe_id=rec.recipe_id)
    assert second.disposition in (RffDisposition.RFF_MATCH, RffDisposition.REPEAT)


def test_handoff_raises_on_new(tmp_path: Path):
    import asyncio
    doa = _doa()
    doa.rff = RffResult(freq_hz=doa.freq_hz, disposition=RffDisposition.NEW, emitter_uid="unk_abc")
    pub = HandOffPublisher(HandOffSettings(enabled=True, transport="file"), tmp_path)
    task = asyncio.run(pub.publish(doa))
    assert task.record_iq is True
    assert task.priority <= 3


def test_rr_ugs_tags():
    row = {"id": "1", "type": "ugs", "timestamp": "t", "payload": {"freq_hz": 1, "trigger": "camera", "node_id": "ugs-west-gate", "rff_disposition": "NEW", "emitter_uid": "unk_x"}}
    rr = kb_event_to_rr(row)
    assert "ugs:camera" in rr["tags"] or any("ugs" in t for t in rr["tags"])


def test_ugs_cue_and_scan(tmp_path: Path):
    bands = [BandConfig(name="GMRS", start_hz=462_500_000, stop_hz=467_700_000, bin_hz=12500)]
    ev = UgsEvent(node_id="ugs-west-gate", trigger=UgsTrigger.CAMERA, freq_hz=462_712_500, sensor_id="s0", lat=34.7, lon=-86.6)
    assert should_cue(ev, bands, True)
    assert not should_cue(ev, bands, False)
    assert in_monitored_band(146_520_000, bands) is False
    (tmp_path / f"{ev.event_id}.ugs.json").write_text(ev.model_dump_json())
    assert len(scan_ugs_dir(tmp_path, set())) == 1
    cot = write_cot(tmp_path / "atak", uid="u1", callsign="ugs", lat=34.7, lon=-86.6, remarks="hi")
    assert cot and "34.7" in cot.read_text()
