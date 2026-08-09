"""Minimal FastAPI status surface."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from krakenbase import __version__
from krakenbase.models import HealthStatus, SystemState


def create_app(get_state_machine, get_store, get_kraken, roe_version: str = "0.1") -> FastAPI:
    app = FastAPI(title="KrakenBase", version=__version__)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        sm = get_state_machine()
        kraken = get_kraken()
        khealth = await kraken.health()
        age = khealth.get("age_s")
        status = "ok"
        if sm.state in (SystemState.DEGRADED, SystemState.FAULT):
            status = "degraded" if sm.state == SystemState.DEGRADED else "fault"
        elif age is None or age > 5.0:
            status = "degraded"

        return HealthStatus(
            status=status,
            state=sm.state,
            kraken_age_s=age,
            roe_version=roe_version,
            version=__version__,
        ).model_dump()

    @app.get("/state")
    async def state() -> dict[str, Any]:
        sm = get_state_machine()
        return {
            "state": sm.state.value,
            "has_anomaly": sm._current_anomaly is not None,
            "dwell_readings": len(getattr(sm, "_dwell_readings", [])),
        }

    @app.get("/events")
    async def events(limit: int = 50, type: str | None = None) -> list[dict[str, Any]]:
        store = get_store()
        return await store.recent(limit=limit, event_type=type)

    return app
