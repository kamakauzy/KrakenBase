"""Synthetic client smoke tests."""

import pytest

from krakenbase.client.synthetic import SyntheticKrakenClient


@pytest.mark.asyncio
async def test_fetch_returns_readings():
    client = SyntheticKrakenClient(anomaly_interval_s=1000)
    readings = await client.fetch_doa()
    assert len(readings) >= 1
    assert readings[0].rssi_db < -80


@pytest.mark.asyncio
async def test_task_and_dwell_readings():
    client = SyntheticKrakenClient(
        anomaly_freq_hz=462_712_500,
        anomaly_bearing_deg=142.0,
        min_confidence=80.0,
    )
    ok = await client.task_frequency(462_712_500)
    assert ok is True
    readings = await client.fetch_doa()
    assert len(readings) == 1
    assert readings[0].freq_hz == 462_712_500
    assert readings[0].confidence >= 80.0


@pytest.mark.asyncio
async def test_health_synthetic():
    client = SyntheticKrakenClient()
    await client.fetch_doa()
    h = await client.health()
    assert h["reachable"] is True
    assert h["synthetic"] is True
