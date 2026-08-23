"""End-to-end synthetic state-machine cycle."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from krakenbase.client.synthetic import SyntheticKrakenClient
from krakenbase.config import Settings
from krakenbase.core.baseline import BaselineEngine
from krakenbase.core.state_machine import StateMachine
from krakenbase.models import SystemState
from krakenbase.store.events import EventStore


@pytest.mark.asyncio
async def test_full_synthetic_cycle(tmp_path: Path):
    settings = Settings()
    settings.system.data_dir = str(tmp_path)
    settings.system.audit_db = str(tmp_path / "events.db")
    settings.kraken.poll_interval_s = 0.02
    settings.kraken.min_confidence = 70.0
    settings.kraken.tune_verify_s = 0.4
    settings.dwell.default_s = 0.25
    settings.dwell.max_s = 0.4
    settings.dwell.settle_s = 0.02
    settings.dwell.max_readings = 2
    settings.baseline.min_anomaly_duration_s = 0.15
    settings.baseline.anomaly_margin_db = 10.0
    settings.baseline.rearm_s = 30.0
    settings.handoff.enabled = False

    store = EventStore(settings.system.audit_db)
    await store.open()
    kraken = SyntheticKrakenClient(
        anomaly_freq_hz=462_712_500,
        anomaly_bearing_deg=142.0,
        anomaly_rssi_db=-30.0,
        noise_rssi_db=-95.0,
        anomaly_interval_s=0.4,
        anomaly_duration_s=8.0,
        min_confidence=85.0,
    )
    sm = StateMachine(
        settings=settings,
        kraken=kraken,
        store=store,
        baseline=BaselineEngine(settings.baseline),
    )

    task = asyncio.create_task(sm.run())
    saw_doa = False
    for _ in range(400):
        await asyncio.sleep(0.05)
        events = await store.recent(limit=50)
        types = {e["type"] for e in events}
        if "doa" in types and "alert" in types:
            saw_doa = True
            break
        if sm.state == SystemState.FAULT:
            break
    sm.stop()
    await asyncio.wait_for(task, timeout=2.0)
    await store.close()

    events = await _reopen_recent(tmp_path / "events.db")
    types = {e["type"] for e in events}
    assert saw_doa, f"never completed DF cycle, last state={sm.state} types={types}"
    assert "anomaly" in types
    assert "doa" in types
    assert "alert" in types


async def _reopen_recent(path: Path):
    store = EventStore(path)
    await store.open()
    rows = await store.recent(limit=100)
    await store.close()
    return rows
