"""Meshtastic alert publisher (stub that works without hardware)."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from krakenbase.config import MeshtasticSettings
from krakenbase.models import AlertEvent, DoaEvent, utcnow

logger = logging.getLogger(__name__)


class MeshtasticAlerter:
    """
    Sends short DF alerts over Meshtastic.
    If the meshtastic library or radio is unavailable, falls back to logging.
    """

    def __init__(self, settings: MeshtasticSettings):
        self.settings = settings
        self._last_sent: dict[int, float] = defaultdict(float)  # freq → monotonic ts
        self._iface = None

        if settings.enabled:
            try:
                from meshtastic.serial_interface import SerialInterface

                self._iface = SerialInterface(settings.interface)
                logger.info("Meshtastic interface opened on %s", settings.interface)
            except Exception as exc:
                logger.warning("Meshtastic unavailable (%s) – alerts will be local-only", exc)
                self._iface = None

    def _rate_ok(self, freq_hz: int) -> bool:
        now = time.monotonic()
        last = self._last_sent[freq_hz]
        if now - last < self.settings.rate_limit_s:
            return False
        self._last_sent[freq_hz] = now
        return True

    async def send(self, doa: DoaEvent) -> AlertEvent:
        msg = (
            f"KB|{doa.freq_hz/1e6:.4f}|{doa.bearing_deg:.0f}°|"
            f"{doa.confidence:.0f}|{str(doa.event_id)[:4]}"
        )

        if not self._rate_ok(doa.freq_hz):
            return AlertEvent(
                channel="meshtastic",
                message=msg,
                related_doa_id=doa.event_id,
                success=False,
                error="rate-limited",
            )

        success = False
        error = None
        if self._iface is not None:
            try:
                self._iface.sendText(msg, channelIndex=self.settings.channel_index)
                success = True
                logger.info("Meshtastic TX: %s", msg)
            except Exception as exc:
                error = str(exc)
                logger.error("Meshtastic send failed: %s", exc)
        else:
            # Local fallback – still counts as an alert for the audit log
            logger.info("LOCAL ALERT (no mesh): %s", msg)
            success = True
            error = "no-radio-fallback"

        return AlertEvent(
            timestamp=utcnow(),
            channel="meshtastic" if self._iface else "local",
            message=msg,
            related_doa_id=doa.event_id,
            success=success,
            error=error,
        )
