"""R0 / U0 contract tests."""

from datetime import datetime, timezone
from uuid import uuid4

from krakenbase.config import Settings
from krakenbase.models import (
    CAP_UGS_RTL_V4,
    DoaEvent,
    DoaReading,
    HandOffTask,
    RffDisposition,
    UgsEvent,
    UgsTrigger,
)
from krakenbase.rff.fuse import fuse_stub
from krakenbase.ugs import accepts_handoff


def _doa() -> DoaEvent:
    reading = DoaReading(
        timestamp=datetime.now(timezone.utc),
        bearing_deg=142.0,
        confidence=88.0,
        rssi_db=-40.0,
        freq_hz=462_712_500,
    )
    return DoaEvent(
        freq_hz=reading.freq_hz,
        bearing_deg=reading.bearing_deg,
        confidence=reading.confidence,
        rssi_db=reading.rssi_db,
        dwell_s=2.0,
        reading=reading,
    )


def test_fuse_stub_is_no_model():
    result = fuse_stub(_doa())
    assert result.disposition == RffDisposition.NO_MODEL
    assert result.emitter_uid is None
    dumped = result.model_dump(mode="json")
    assert dumped["disposition"] == "NO_MODEL"


def test_ugs_event_round_trip():
    ev = UgsEvent(
        node_id="ugs-west-gate",
        trigger=UgsTrigger.ENERGY,
        freq_hz=462_712_500,
        duration_ms=40,
        sensor_id="rtl-v4-0",
        recipe_id="rtl_v4:2.4e6:30",
    )
    data = ev.model_dump(mode="json")
    again = UgsEvent.model_validate(data)
    assert again.node_id == "ugs-west-gate"
    assert again.trigger == UgsTrigger.ENERGY


def test_handoff_target_node():
    task = HandOffTask(
        freq_hz=462_712_500,
        source_event_id=uuid4(),
        target_node_id="ugs-west-gate",
    )
    assert accepts_handoff("ugs-west-gate", task) is True
    assert accepts_handoff("ugs-east", task) is False
    open_task = HandOffTask(freq_hz=100, source_event_id=uuid4())
    assert accepts_handoff("ugs-east", open_task) is True


def test_rff_disabled_by_default():
    s = Settings()
    assert s.rff.enabled is False
    assert CAP_UGS_RTL_V4 == "ugs_rtl_v4"
