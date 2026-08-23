"""Adaptive scan → anomaly → DF → alert → hand-off state machine."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Awaitable

from krakenbase.client.kraken import KrakenClient
from krakenbase.config import Settings
from krakenbase.core.baseline import BaselineEngine
from krakenbase.core.heading import HeadingFusion
from krakenbase.models import AlertEvent, AnomalyEvent, DoaEvent, DoaReading, HandOffTask, SystemState, utcnow
from krakenbase.store.events import EventStore

logger = logging.getLogger(__name__)


class StateMachine:
    def __init__(self, settings: Settings, kraken: KrakenClient, store: EventStore, baseline: BaselineEngine,
                 alert_fn: Callable[[DoaEvent], Awaitable[AlertEvent]] | None = None,
                 handoff_fn: Callable[[DoaEvent], Awaitable[HandOffTask]] | None = None):
        self.settings = settings
        self.kraken = kraken
        self.store = store
        self.baseline = baseline
        self.alert_fn = alert_fn
        self.handoff_fn = handoff_fn
        self.heading = HeadingFusion(
            heading_offset_deg=settings.array.heading_offset_deg,
            nmea_path=getattr(settings.array, "nmea_path", None),
            stale_after_s=getattr(settings.array, "heading_stale_s", 30.0),
        )
        self.state = SystemState.INIT
        self._running = False
        self._current_anomaly: AnomalyEvent | None = None
        self._dwell_readings: list[DoaReading] = []
        self._dwell_start: float | None = None
        self._recover_fails: int = 0

    async def transition(self, new_state: SystemState, reason: str = "") -> None:
        old = self.state
        self.state = new_state
        await self.store.log_state_change(old.value, new_state.value, reason)
        logger.info("STATE %s → %s  (%s)", old.value, new_state.value, reason)

    async def run(self) -> None:
        self._running = True
        await self.transition(SystemState.SCANNING, "startup")
        while self._running:
            try:
                if self.state == SystemState.SCANNING:
                    await self._scan_tick()
                elif self.state == SystemState.TASKING:
                    await self._task_tick()
                elif self.state == SystemState.DWELLING:
                    await self._dwell_tick()
                elif self.state == SystemState.PROCESSING:
                    await self._process_tick()
                elif self.state == SystemState.ALERTING:
                    await self._alert_tick()
                elif self.state == SystemState.HANDING_OFF:
                    await self._handoff_tick()
                elif self.state in (SystemState.DEGRADED, SystemState.FAULT):
                    await self._recover_tick()
                else:
                    await asyncio.sleep(0.5)
            except Exception as exc:
                logger.exception("State machine error in %s: %s", self.state, exc)
                await self.transition(SystemState.DEGRADED, str(exc))
                await asyncio.sleep(2.0)

    def stop(self) -> None:
        self._running = False

    async def _scan_tick(self) -> None:
        readings = await self.kraken.fetch_doa()
        if not readings:
            age = self.kraken.age_s
            if age is not None and age > 10.0:
                await self.transition(SystemState.DEGRADED, f"Kraken silent for {age:.1f}s")
            await asyncio.sleep(self.settings.kraken.poll_interval_s)
            return
        for r in readings:
            anomaly = self.baseline.observe(r.freq_hz, r.rssi_db)
            if anomaly is not None:
                await self.store.log_anomaly(anomaly)
                self._current_anomaly = anomaly
                await self.transition(SystemState.TASKING, f"anomaly at {anomaly.freq_hz}")
                return
        await asyncio.sleep(self.settings.kraken.poll_interval_s)

    async def _task_tick(self) -> None:
        if self._current_anomaly is None:
            await self.transition(SystemState.SCANNING, "no anomaly")
            return
        freq = self._current_anomaly.freq_hz
        ok = await self.kraken.task_frequency(freq)
        if not ok or not await self._confirm_tune(freq):
            await self.transition(SystemState.SCANNING, "task/tune failed")
            self._current_anomaly = None
            return
        self._dwell_readings = []
        self._dwell_start = time.time()
        await self.transition(SystemState.DWELLING, f"dwelling on {freq}")

    async def _dwell_tick(self) -> None:
        assert self._dwell_start is not None
        elapsed = time.time() - self._dwell_start
        max_dwell = min(self.settings.dwell.default_s, self.settings.dwell.max_s)
        readings = await self.kraken.fetch_doa()
        for r in readings:
            if r.confidence >= self.settings.kraken.min_confidence:
                self._dwell_readings.append(r)
        if elapsed >= max_dwell or len(self._dwell_readings) >= self.settings.dwell.max_readings:
            await self.transition(SystemState.PROCESSING, f"collected {len(self._dwell_readings)} readings")
            return
        await asyncio.sleep(self.settings.kraken.poll_interval_s)

    async def _process_tick(self) -> None:
        if not self._dwell_readings:
            self._current_anomaly = None
            await self.transition(SystemState.SCANNING, "no usable DOA")
            return
        best = max(self._dwell_readings, key=lambda r: r.confidence)
        if best.heading_deg is not None:
            self.heading.update_from_doa(compass_heading=best.heading_deg)
        abs_bearing = self.heading.absolute_bearing(best.bearing_deg)
        doa_event = DoaEvent(
            timestamp=utcnow(), freq_hz=best.freq_hz, bearing_deg=best.bearing_deg,
            confidence=best.confidence, rssi_db=best.rssi_db, absolute_bearing_deg=abs_bearing,
            related_anomaly_id=self._current_anomaly.event_id if self._current_anomaly else None,
            dwell_s=time.time() - (self._dwell_start or time.time()), reading=best,
        )
        await self.store.log_doa(doa_event)
        self._last_doa_event = doa_event
        await self.transition(SystemState.ALERTING, f"bearing {best.bearing_deg:.0f} deg conf {best.confidence:.0f}")

    async def _alert_tick(self) -> None:
        doa_event: DoaEvent = getattr(self, "_last_doa_event", None)
        if doa_event is None:
            await self.transition(SystemState.SCANNING, "missing doa event")
            return
        if self.alert_fn:
            try:
                await self.store.log_alert(await self.alert_fn(doa_event))
            except Exception as exc:
                logger.error("Alert failed: %s", exc)
                await self.store.log_alert(AlertEvent(channel="local", message=str(exc), related_doa_id=doa_event.event_id, success=False, error=str(exc)))
        else:
            msg = f"DF {doa_event.freq_hz/1e6:.4f} MHz @ {doa_event.bearing_deg:.0f} deg conf {doa_event.confidence:.0f}"
            await self.store.log_alert(AlertEvent(channel="local", message=msg, related_doa_id=doa_event.event_id, success=True))
        await self.transition(SystemState.HANDING_OFF, "alerts done")

    async def _handoff_tick(self) -> None:
        doa_event: DoaEvent = getattr(self, "_last_doa_event", None)
        if doa_event and self.handoff_fn:
            try:
                await self.store.log_handoff(await self.handoff_fn(doa_event))
            except Exception as exc:
                logger.error("Hand-off failed: %s", exc)
        self._current_anomaly = None
        self._dwell_readings = []
        self._dwell_start = None
        await self.transition(SystemState.SCANNING, "dwell complete – back to scan")

    async def _confirm_tune(self, freq_hz: int) -> bool:
        deadline = time.time() + max(0.2, self.settings.kraken.tune_verify_s)
        tol = max(1, self.settings.kraken.tune_tolerance_hz)
        await asyncio.sleep(self.settings.dwell.settle_s)
        while time.time() < deadline:
            readings = await self.kraken.fetch_doa()
            if any(abs(r.freq_hz - freq_hz) <= tol for r in readings):
                return True
            await asyncio.sleep(self.settings.kraken.poll_interval_s)
        return False

    async def _recover_tick(self) -> None:
        readings = await self.kraken.fetch_doa()
        if readings:
            self._recover_fails = 0
            await self.transition(SystemState.SCANNING, "Kraken recovered")
            return
        self._recover_fails += 1
        if self.state != SystemState.FAULT and self._recover_fails >= max(1, self.settings.kraken.recover_fail_limit):
            await self.transition(SystemState.FAULT, f"Kraken silent {self._recover_fails} recoveries")
            return
        await asyncio.sleep(3.0 if self.state != SystemState.FAULT else 10.0)
