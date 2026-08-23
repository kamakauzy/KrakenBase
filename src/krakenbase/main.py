"""KrakenBase entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from pathlib import Path

import uvicorn

from krakenbase.alerts.meshtastic_alert import MeshtasticAlerter
from krakenbase.api.app import create_app
from krakenbase.client.kraken import KrakenClient
from krakenbase.client.synthetic import SyntheticKrakenClient
from krakenbase.config import load_config
from krakenbase.core.baseline import BaselineEngine
from krakenbase.core.classifier import EmitterClassifier
from krakenbase.core.state_machine import StateMachine
from krakenbase.fleet.registry import FleetRegistry
from krakenbase.handoff.publisher import HandOffPublisher
from krakenbase.models import UgsEvent
from krakenbase.rff.gallery import Gallery
from krakenbase.store.events import EventStore
from krakenbase.ugs.bridge import export_ugs, scan_ugs_dir, should_cue

logger = logging.getLogger("krakenbase")


async def amain(config_path: str | None, synthetic: bool = False) -> None:
    settings = load_config(config_path)
    logging.basicConfig(
        level=getattr(logging, settings.system.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    )
    use_synth = synthetic or settings.baseline.power_source == "synthetic"
    logger.info("KrakenBase starting  site=%s  mode=%s", settings.system.site_id, "SYNTHETIC" if use_synth else "LIVE")
    if settings.roe.allow_tx:
        raise SystemExit("ROE v1 forbids roe.allow_tx=true – refuse to start")
    Path(settings.system.data_dir).mkdir(parents=True, exist_ok=True)
    store = EventStore(settings.system.audit_db)
    await store.open()
    if use_synth:
        kraken = SyntheticKrakenClient(
            anomaly_freq_hz=462_712_500, anomaly_bearing_deg=142.0, anomaly_rssi_db=-35.0,
            anomaly_interval_s=20.0, anomaly_duration_s=10.0,
        )
        settings.alert.meshtastic.enabled = False
    else:
        kraken = KrakenClient(settings.kraken)
    baseline = BaselineEngine(settings.baseline)
    alerter = MeshtasticAlerter(settings.alert.meshtastic, site_id=settings.system.site_id)
    publisher = HandOffPublisher(settings.handoff, settings.system.data_dir)
    fleet = FleetRegistry(db_path=Path(settings.system.data_dir) / "fleet.db")
    known = Path(settings.system.data_dir) / "known_emitters.yaml"
    if not known.exists():
        known = Path("config/known_emitters.example.yaml")
    classifier = EmitterClassifier(settings.baseline, known_path=known if known.exists() else None)
    gallery = Gallery(settings.rff.gallery_path) if settings.rff.enabled and settings.rff.gallery_path else None

    async def alert_fn(doa):
        return await alerter.send(doa)

    async def handoff_fn(doa):
        return await publisher.publish(doa)

    sm = StateMachine(settings, kraken, store, baseline, alert_fn, handoff_fn if settings.handoff.enabled else None, classifier, gallery)
    ugs_seen: set[str] = set()

    async def ingest_ugs_body(body: dict):
        ev = UgsEvent.model_validate(body)
        await store.log_ugs(ev)
        if settings.ugs.enabled:
            export_ugs(ev, site_id=settings.system.site_id, lat=settings.site.lat, lon=settings.site.lon,
                       atak_dir=settings.ugs.atak_dir, rr_path=settings.ugs.rr_path)
            if ev.freq_hz and should_cue(ev, settings.baseline.bands, settings.ugs.cue_dwell):
                sm.cue_freq(ev.freq_hz)
        return ev.model_dump(mode="json")

    app = create_app(
        get_state_machine=lambda: sm, get_store=lambda: store, get_kraken=lambda: kraken,
        get_fleet=lambda: fleet, get_baseline=lambda: baseline, get_classifier=lambda: classifier,
        get_settings=lambda: settings, get_gallery=lambda: gallery, ingest_ugs=ingest_ugs_body,
        roe_version=settings.roe.version,
    )
    server = uvicorn.Server(uvicorn.Config(app, host=settings.status_api.host, port=settings.status_api.port, log_level="warning"))
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown(*_):
        logger.info("Shutdown requested")
        sm.stop()
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)
    sm_task = asyncio.create_task(sm.run())
    api_task = asyncio.create_task(server.serve())

    async def retention_loop():
        while not stop_event.is_set():
            try:
                if settings.system.retention_days > 0:
                    await store.purge_older_than(settings.system.retention_days)
            except Exception as exc:
                logger.warning("Retention purge failed: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3600.0)
            except asyncio.TimeoutError:
                pass

    async def ugs_loop():
        while not stop_event.is_set():
            try:
                if settings.ugs.enabled and settings.ugs.watch_dir:
                    for ev in scan_ugs_dir(settings.ugs.watch_dir, ugs_seen):
                        await ingest_ugs_body(ev.model_dump(mode="json"))
            except Exception as exc:
                logger.warning("UGS ingest failed: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

    retention_task = asyncio.create_task(retention_loop())
    ugs_task = asyncio.create_task(ugs_loop())
    await stop_event.wait()
    sm.stop()
    server.should_exit = True
    retention_task.cancel()
    ugs_task.cancel()
    await asyncio.gather(sm_task, api_task, retention_task, ugs_task, return_exceptions=True)
    await kraken.close()
    await store.close()
    logger.info("KrakenBase stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="KrakenBase fixed-site SIGINT node")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    config_path = args.config
    if config_path is None:
        candidates = ["config.yaml", "config/config.yaml"]
        if args.synthetic:
            candidates.append("config/config.synthetic.yaml")
        candidates.append("config/config.example.yaml")
        for candidate in candidates:
            if Path(candidate).exists():
                config_path = candidate
                break
    try:
        asyncio.run(amain(config_path, synthetic=args.synthetic))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
