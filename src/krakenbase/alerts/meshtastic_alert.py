"""Meshtastic alert publisher – serial/TCP, reconnect, CLI fallback."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from collections import defaultdict
from typing import Any

from krakenbase.config import MeshtasticSettings
from krakenbase.models import AlertEvent, DoaEvent, utcnow

logger = logging.getLogger(__name__)


def format_df_message(
    doa: DoaEvent,
    site_id: str | None = None,
    include_site: bool = True,
) -> str:
    """Compact mesh-friendly DF payload."""
    bearing = doa.absolute_bearing_deg if doa.absolute_bearing_deg is not None else doa.bearing_deg
    parts = ["KB"]
    if include_site and site_id:
        parts[0] = f"KB[{site_id[:12]}]"
    parts.append(f"{doa.freq_hz / 1e6:.4f}")
    parts.append(f"{bearing:.0f}\u00b0")
    parts.append(f"c{doa.confidence:.0f}")
    parts.append(f"r{doa.rssi_db:.0f}")
    parts.append(str(doa.event_id)[:4])
    return "|".join(parts)


class MeshtasticAlerter:
    def __init__(self, settings: MeshtasticSettings, site_id: str | None = None):
        self.settings = settings
        self.site_id = site_id
        self._last_sent: dict[int, float] = defaultdict(float)
        self._iface: Any = None
        self._connect_error: str | None = None
        if settings.enabled:
            self._connect()

    def _connect(self) -> bool:
        if not self.settings.enabled:
            return False
        try:
            iface_spec = (self.settings.interface or "").strip()
            if iface_spec.lower().startswith("tcp:"):
                rest = iface_spec[4:]
                host, _, port_s = rest.partition(":")
                port = int(port_s) if port_s else 4403
                from meshtastic.tcp_interface import TCPInterface

                self._iface = TCPInterface(hostname=host, portNumber=port)
                logger.info("Meshtastic TCP interface %s:%s", host, port)
            else:
                from meshtastic.serial_interface import SerialInterface

                self._iface = SerialInterface(iface_spec)
                logger.info("Meshtastic serial interface on %s", iface_spec)
            self._connect_error = None
            return True
        except Exception as exc:
            self._iface = None
            self._connect_error = str(exc)
            logger.warning("Meshtastic connect failed (%s) – CLI/local fallback", exc)
            return False

    def _rate_ok(self, freq_hz: int) -> bool:
        now = time.monotonic()
        last = self._last_sent[freq_hz]
        if now - last < self.settings.rate_limit_s:
            return False
        self._last_sent[freq_hz] = now
        return True

    def _send_via_iface(self, msg: str) -> tuple[bool, str | None]:
        if self._iface is None:
            if not self._connect():
                return False, self._connect_error or "no-interface"
        assert self._iface is not None
        try:
            kwargs: dict[str, Any] = {"channelIndex": self.settings.channel_index}
            dest = self.settings.destination
            if dest and dest not in ("^all", "all", ""):
                kwargs["destinationId"] = dest
            try:
                self._iface.sendText(
                    msg,
                    wantAck=self.settings.want_ack,
                    hopLimit=self.settings.hop_limit,
                    **kwargs,
                )
            except TypeError:
                self._iface.sendText(msg, **{k: v for k, v in kwargs.items() if k != "hopLimit"})
            return True, None
        except Exception as exc:
            logger.error("Meshtastic sendText failed: %s – reconnecting", exc)
            self.close()
            self._connect()
            return False, str(exc)

    def _send_via_cli(self, msg: str) -> tuple[bool, str | None]:
        if not self.settings.cli_fallback:
            return False, "cli-fallback-disabled"
        if not shutil.which("meshtastic"):
            return False, "meshtastic-cli-not-found"
        if self.settings.interface.lower().startswith("tcp:"):
            rest = self.settings.interface[4:]
            host, _, port_s = rest.partition(":")
            cmd = [
                "meshtastic",
                "--host",
                host if not port_s else f"{host}:{port_s}",
                "--ch-index",
                str(self.settings.channel_index),
                "--sendtext",
                msg,
            ]
        else:
            cmd = [
                "meshtastic",
                "--port",
                self.settings.interface,
                "--ch-index",
                str(self.settings.channel_index),
                "--sendtext",
                msg,
            ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
            if proc.returncode == 0:
                return True, None
            err = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
            return False, err[:200]
        except Exception as exc:
            return False, str(exc)

    async def send(self, doa: DoaEvent) -> AlertEvent:
        msg = format_df_message(
            doa, site_id=self.site_id, include_site=self.settings.include_site
        )

        if not self.settings.enabled:
            logger.info("LOCAL ALERT (mesh disabled): %s", msg)
            return AlertEvent(
                timestamp=utcnow(),
                channel="local",
                message=msg,
                related_doa_id=doa.event_id,
                success=True,
                error="mesh-disabled",
            )

        if not self._rate_ok(doa.freq_hz):
            return AlertEvent(
                timestamp=utcnow(),
                channel="meshtastic",
                message=msg,
                related_doa_id=doa.event_id,
                success=False,
                error="rate-limited",
            )

        success = False
        error: str | None = None
        channel = "local"

        ok, err = self._send_via_iface(msg)
        if ok:
            success = True
            channel = "meshtastic"
            logger.info("Meshtastic TX: %s", msg)
        else:
            ok2, err2 = self._send_via_cli(msg)
            if ok2:
                success = True
                channel = "meshtastic-cli"
                logger.info("Meshtastic CLI TX: %s", msg)
            else:
                channel = "local"
                success = True
                error = f"mesh-failed iface:{err or '-'}; cli:{err2 or '-'}"
                logger.info("LOCAL ALERT (mesh failed): %s  (%s)", msg, error)

        return AlertEvent(
            timestamp=utcnow(),
            channel=channel,
            message=msg,
            related_doa_id=doa.event_id,
            success=success,
            error=error,
        )

    def close(self) -> None:
        if self._iface is not None:
            try:
                self._iface.close()
            except Exception:
                pass
            self._iface = None
