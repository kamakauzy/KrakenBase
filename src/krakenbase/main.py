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
from krakenbase.core.state_machine import StateMachine
from krakenbase.handoff.publisher import HandOffPublisher
from krakenbase.store.events import EventStore

logger = logging.getLogger("krakenbase")


async def amain(config_path: str | None, synthetic: bool = False) -> None:
    settings = load_config(config_path)
    logging.basicConfig(
        level=getattr(logging, settings.system.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    )

    use_synth = synthetic or settings.baseline.power_source == "synthetic"
    logger.info(
        "KrakenBase starting  site=%s  mode=%s",
        settings.system.site_id,
        "SYNTHETIC" if use_synth else "LIVE",
    )

    Path(settings.system.data_dir).mkdir(parents=True, exist_ok=True)

    store = EventStore(settings.system.audit_db)
    await store.open()

    if use_synth:
        kraken = SyntheticKrakenClient(
            anomaly_freq_hz=462_712_500,
            anomaly_bearing_deg=142.0,
            anomaly_rssi_db=-35.0,
            anomaly_interval_s=20.0,
            anomaly_duration_s=10.0,
        )
        settings.alert.meshtastic.enabled = False
    else:
        kraken = KrakenClient(settings.kraken)

    baseline = BaselineEngine(settings.baseline)
    alerter = MeshtasticAlerter(settings.alert.meshtastic)
    publisher = HandOffPublisher(settings.handoff, settings.system.data_dir)

    async def alert_fn(doa):
        return await alerter.send(doa)

    async def handoff_fn(doa):
        return await publisher.publish(doa)

    sm = StateMachine(
        settings=settings,
        kraken=kraken,
        store=store,
        baseline=baseline,
        alert_fn=alert_fn,
        handoff_fn=handoff_fn if settings.handoff.enabled else None,
    )

    app = create_app(
        get_state_machine=lambda: sm,
        get_store=lambda: store,
        get_kraken=lambda: kraken,
        roe_version=settings.roe.version,
    )

    config = uvicorn.Config(
        app,
        host=settings.status_api.host,
        port=settings.status_api.port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

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
                days = settings.system.retention_days
                if days > 0:
                    await store.purge_older_than(days)
            except Exception as exc:
                logger.warning("Retention purge failed: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3600.0)
            except asyncio.TimeoutError:
                pass

    retention_task = asyncio.create_task(retention_loop())

    await stop_event.wait()
    sm.stop()
    server.should_exit = True
    retention_task.cancel()
    await asyncio.gather(sm_task, api_task, retention_task, return_exceptions=True)
    await kraken.close()
    await store.close()
    logger.info("KrakenBase stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="KrakenBase fixed-site SIGINT node")
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to config.yaml (default: look for ./config.yaml)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Force synthetic Kraken (no hardware). Also enabled when baseline.power_source=synthetic",
    )
    args = parser.parse_args()

    config_path = args.config
    if config_path is None:
        candidates = [
            "config.yaml",
            "config/config.yaml",
        ]
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
