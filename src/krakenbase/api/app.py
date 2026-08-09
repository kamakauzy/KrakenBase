"""FastAPI status surface + fleet + UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from krakenbase import __version__
from krakenbase.models import HealthStatus, SystemState

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"


def create_app(
    get_state_machine,
    get_store,
    get_kraken,
    get_fleet=None,
    get_baseline=None,
    get_classifier=None,
    roe_version: str = "0.1",
) -> FastAPI:
    app = FastAPI(title="KrakenBase", version=__version__)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def ui_root() -> HTMLResponse:
        index = STATIC_DIR / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text())
        return HTMLResponse("<h1>KrakenBase</h1><p>UI not installed. Use /health /state /events</p>")

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

    @app.get("/baseline")
    async def baseline_snapshot() -> dict[str, Any]:
        if not get_baseline:
            return {"bins": []}
        eng = get_baseline()
        bins = []
        for freq, stats in sorted(eng._bins.items()):
            if stats.mean_db is None:
                continue
            bins.append(
                {
                    "freq_hz": freq,
                    "mean_db": round(stats.mean_db, 1),
                    "count": stats.count,
                    "ready": stats.ready,
                }
            )
        return {"bins": bins, "count": len(bins)}

    @app.get("/fleet")
    async def fleet_list() -> list[dict[str, Any]]:
        if not get_fleet:
            return []
        return [n.model_dump(mode="json") for n in get_fleet().list_nodes()]

    @app.post("/fleet/heartbeat")
    async def fleet_heartbeat(body: dict[str, Any]) -> dict[str, Any]:
        if not get_fleet:
            return JSONResponse({"error": "fleet disabled"}, status_code=503)
        node_id = body.get("node_id")
        if not node_id:
            return JSONResponse({"error": "node_id required"}, status_code=400)
        node = get_fleet().heartbeat(
            node_id=str(node_id),
            status=body.get("status", "online"),
            capabilities=body.get("capabilities"),
            current_freq_hz=body.get("current_freq_hz"),
            last_task_id=body.get("last_task_id"),
            site=body.get("site"),
            notes=body.get("notes"),
        )
        return node.model_dump(mode="json")

    @app.get("/fleet/pick")
    async def fleet_pick() -> dict[str, Any]:
        if not get_fleet:
            return {"node": None}
        n = get_fleet().pick_idle()
        return {"node": n.model_dump(mode="json") if n else None}

    return app
