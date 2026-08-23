"""FastAPI status surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from krakenbase import __version__
from krakenbase.models import HealthStatus, SystemState

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"


def _token_ok(expected: str | None, header_token: str | None, authorization: str | None) -> bool:
    if not expected:
        return True
    if header_token and header_token == expected:
        return True
    if authorization and authorization.startswith("Bearer ") and authorization[7:] == expected:
        return True
    return False


def create_app(get_state_machine, get_store, get_kraken, get_baseline=None, get_settings=None, roe_version: str = "0.1") -> FastAPI:
    app = FastAPI(title="KrakenBase", version=__version__)
    static_dir = STATIC_DIR / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def _api_token() -> str | None:
        if not get_settings:
            return None
        return get_settings().status_api.token

    @app.middleware("http")
    async def write_guard(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected = _api_token()
            if expected:
                hdr = request.headers.get("x-api-token")
                auth = request.headers.get("authorization")
                if not _token_ok(expected, hdr, auth):
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    async def ui_root() -> HTMLResponse:
        index = STATIC_DIR / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text())
        return HTMLResponse("<h1>KrakenBase</h1><p>Use /health /state /events</p>")

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
        return HealthStatus(status=status, state=sm.state, kraken_age_s=age, roe_version=roe_version, version=__version__).model_dump(mode="json")

    @app.get("/state")
    async def state() -> dict[str, Any]:
        return {"state": get_state_machine().state.value}

    @app.get("/events")
    async def events(limit: int = 50, type: str | None = None) -> list[dict[str, Any]]:
        return await get_store().recent(limit=limit, event_type=type)

    @app.get("/baseline")
    async def baseline_snapshot() -> dict[str, Any]:
        if not get_baseline:
            return {"bins": []}
        eng = get_baseline()
        bins = [{"freq_hz": f, "mean_db": round(s.mean_db, 1), "count": s.count, "ready": s.ready}
                for f, s in sorted(eng._bins.items()) if s.mean_db is not None]
        return {"bins": bins, "count": len(bins), "bands": eng.band_summary()}

    @app.get("/waterfall")
    async def waterfall(max_frames: int = 60) -> dict[str, Any]:
        if not get_baseline:
            return {"frames": []}
        frames = get_baseline().waterfall_history(max_frames=max_frames)
        return {"frames": frames, "count": len(frames)}

    return app
