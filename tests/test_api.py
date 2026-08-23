"""Status API smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from krakenbase.api.app import create_app
from krakenbase.client.synthetic import SyntheticKrakenClient
from krakenbase.config import Settings
from krakenbase.core.baseline import BaselineEngine
from krakenbase.core.state_machine import StateMachine
from krakenbase.store.events import EventStore


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings()
    settings.status_api.token = "secret"
    settings.system.site_id = "pb-test"
    store = EventStore(tmp_path / "e.db")
    import asyncio
    asyncio.run(store.open())
    kraken = SyntheticKrakenClient()
    baseline = BaselineEngine(settings.baseline)
    sm = StateMachine(settings, kraken, store, baseline)
    app = create_app(
        get_state_machine=lambda: sm,
        get_store=lambda: store,
        get_kraken=lambda: kraken,
        get_baseline=lambda: baseline,
        get_settings=lambda: settings,
        roe_version="0.1",
    )
    with TestClient(app) as c:
        yield c
    asyncio.run(store.close())


def test_health_and_waterfall(client):
    h = client.get("/health").json()
    assert "status" in h
    assert "roe_version" in h
    wf = client.get("/waterfall").json()
    assert "frames" in wf
