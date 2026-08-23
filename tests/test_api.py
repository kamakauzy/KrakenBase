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
from krakenbase.fleet.registry import FleetRegistry
from krakenbase.store.events import EventStore


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings()
    settings.status_api.token = "secret"
    settings.system.site_id = "pb-test"
    settings.site.lat = 34.73
    settings.site.lon = -86.59
    store = EventStore(tmp_path / "e.db")

    async def _open():
        await store.open()

    import asyncio

    asyncio.run(_open())
    kraken = SyntheticKrakenClient()
    baseline = BaselineEngine(settings.baseline)
    sm = StateMachine(settings, kraken, store, baseline)
    fleet = FleetRegistry()
    app = create_app(
        get_state_machine=lambda: sm,
        get_store=lambda: store,
        get_kraken=lambda: kraken,
        get_fleet=lambda: fleet,
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
    mp = client.get("/map/features").json()
    assert mp["site"]["site_id"] == "pb-test"


def test_heartbeat_requires_token(client):
    denied = client.post("/fleet/heartbeat", json={"node_id": "rtl-1"})
    assert denied.status_code == 401
    ok = client.post(
        "/fleet/heartbeat",
        json={"node_id": "rtl-1"},
        headers={"X-API-Token": "secret"},
    )
    assert ok.status_code == 200
    assert ok.json()["node_id"] == "rtl-1"
