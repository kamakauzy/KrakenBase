"""Hand-off publisher tests."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from krakenbase.config import HandOffSettings
from krakenbase.handoff.publisher import HandOffPublisher
from krakenbase.models import DoaEvent, DoaReading


def _doa(freq: int = 462_712_500) -> DoaEvent:
    reading = DoaReading(
        timestamp=datetime.now(timezone.utc),
        bearing_deg=142.0,
        confidence=91.0,
        rssi_db=-40.0,
        freq_hz=freq,
    )
    return DoaEvent(
        freq_hz=freq,
        bearing_deg=142.0,
        confidence=91.0,
        rssi_db=-40.0,
        dwell_s=2.0,
        reading=reading,
    )


@pytest.mark.asyncio
async def test_file_handoff(tmp_path: Path):
    settings = HandOffSettings(enabled=True, transport="file")
    pub = HandOffPublisher(settings, tmp_path)
    task = await pub.publish(_doa())
    assert task.freq_hz == 462_712_500
    out = tmp_path / "handoff" / f"{task.task_id}.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["freq_hz"] == 462_712_500
    assert data["confidence"] == 91.0
    feed = tmp_path / "handoff" / "tasks.jsonl"
    assert feed.exists()
    assert str(task.task_id) in feed.read_text()


@pytest.mark.asyncio
async def test_disabled_handoff_still_returns_task(tmp_path: Path):
    settings = HandOffSettings(enabled=False, transport="file")
    pub = HandOffPublisher(settings, tmp_path)
    task = await pub.publish(_doa())
    assert task.freq_hz == 462_712_500
    assert not (tmp_path / "handoff").exists() or not list((tmp_path / "handoff").glob("*.json"))
