"""KrakenBase entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn

from krakenbase.alerts.meshtastic_alert import MeshtasticAlerter
from krakenbase.api.app import create_app
from krakenbase.client.kraken import KrakenClient
from krakenbase.config import load_config
from krakenbase.core.baseline import BaselineEngine
from krakenbase.core.state_machine import StateMachine
from krakenbase.store.events import EventStore

logger = logging.getLogger("krakenbase")


async def amain(config_path: str | None) -> None:
    settings = load_config(config_path)
    logging.basicConfig(
        level=getattr(logging, settings.system.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    )
    logger.info("KrakenBase starting  site=%s", settings.system.site_id)

    # Ensure data dir exists
    Path(settings.system.data_dir).mkdir(parents=True, exist_ok=True)

    store = EventStore(settings.system.audit_db)
    await store.open()

    kraken = KrakenClient(settings.kraken)
    baseline = BaselineEngine(settings.baseline)
    alerter = MeshtasticAlerter(settings.alert.meshtastic)

    async def alert_fn(doa):
        return await alerter.send(doa)

    sm = StateMachine(
        settings=settings,
        kraken=kraken,
        store=store,
        baseline=baseline,
        alert_fn=alert_fn,
    )

    app = create_app(
        get_state_machine=lambda: sm,
        get_store=lambda: store,
        get_kraken=lambda: kraken,
        roe_version=settings.roe.version,
    )

    # Run state machine and API concurrently
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

    await stop_event.wait()
    sm.stop()
    server.should_exit = True
    await asyncio.gather(sm_task, api_task, return_exceptions=True)
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
    args = parser.parse_args()

    config_path = args.config
    if config_path is None:
        for candidate in ("config.yaml", "config/config.yaml", "config/config.example.yaml"):
            if Path(candidate).exists():
                config_path = candidate
                break

    try:
        asyncio.run(amain(config_path))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
