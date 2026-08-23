"""FastAPI status surface + fleet + UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from krakenbase import __version__
from krakenbase.core.geolocate import project_emitter
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


def create_app(
    get_state_machine,
    get_store,
    get_kraken,
    get_fleet=None,
    get_baseline=None,
    get_classifier=None,
    get_settings=None,
    get_gallery=None,
    ingest_ugs=None,
    roe_version: str = "0.1",
) -> FastAPI:
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
            status=status, state=sm.state, kraken_age_s=age, roe_version=roe_version, version=__version__
        ).model_dump(mode="json")

    @app.get("/state")
    async def state() -> dict[str, Any]:
        sm = get_state_machine()
        return {"state": sm.state.value}

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

    @app.get("/map/features")
    async def map_features(limit: int = 50) -> dict[str, Any]:
        settings = get_settings() if get_settings else None
        site = {
            "site_id": settings.system.site_id if settings else None,
            "lat": settings.site.lat if settings else None,
            "lon": settings.site.lon if settings else None,
            "default_range_m": settings.site.default_range_m if settings else 500.0,
        }
        events = await get_store().recent(limit=limit, event_type="doa")
        features = []
        for ev in events:
            p = ev.get("payload") or {}
            bearing = p.get("absolute_bearing_deg", p.get("bearing_deg"))
            est = project_emitter(float(bearing), settings.site, rssi_db=p.get("rssi_db")) if settings is not None and bearing is not None else None
            features.append({
                "id": ev.get("id"), "timestamp": ev.get("timestamp") or p.get("timestamp"),
                "freq_hz": p.get("freq_hz"), "bearing_deg": bearing, "confidence": p.get("confidence"),
                "rssi_db": p.get("rssi_db"), "est_lat": est.lat if est else None, "est_lon": est.lon if est else None,
                "est_range_m": est.range_m if est else None, "est_method": est.method if est else None,
            })
        return {"site": site, "features": features}

    @app.get("/fleet")
    async def fleet_list() -> list[dict[str, Any]]:
        return [n.model_dump(mode="json") for n in get_fleet().list_nodes()] if get_fleet else []

    @app.post("/fleet/heartbeat")
    async def fleet_heartbeat(body: dict[str, Any]) -> dict[str, Any]:
        if not get_fleet:
            return JSONResponse({"error": "fleet disabled"}, status_code=503)
        node_id = body.get("node_id")
        if not node_id:
            return JSONResponse({"error": "node_id required"}, status_code=400)
        node = get_fleet().heartbeat(
            node_id=str(node_id), status=body.get("status", "online"),
            capabilities=body.get("capabilities"), current_freq_hz=body.get("current_freq_hz"),
            last_task_id=body.get("last_task_id"), site=body.get("site"), notes=body.get("notes"),
        )
        return node.model_dump(mode="json")

    @app.get("/fleet/pick")
    async def fleet_pick() -> dict[str, Any]:
        if not get_fleet:
            return {"node": None}
        n = get_fleet().pick_idle()
        return {"node": n.model_dump(mode="json") if n else None}

    @app.post("/ugs/event")
    async def ugs_event(body: dict[str, Any]) -> dict[str, Any]:
        if not ingest_ugs:
            return JSONResponse({"error": "ugs ingest disabled"}, status_code=503)
        return await ingest_ugs(body)

    @app.get("/rff/gallery")
    async def rff_gallery() -> dict[str, Any]:
        if not get_gallery:
            return {"emitters": []}
        gal = get_gallery()
        return {"emitters": [] if gal is None else gal.list_emitters()}

    return app
