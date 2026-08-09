"""KrakenSDR client – poll DOA output and task the array."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from krakenbase.config import KrakenSettings
from krakenbase.models import DoaReading

logger = logging.getLogger(__name__)


class KrakenClient:
    """Talks to a co-located or remote krakensdr_doa instance."""

    def __init__(self, settings: KrakenSettings):
        self.settings = settings
        self._last_success: datetime | None = None
        self._client = httpx.AsyncClient(timeout=settings.request_timeout_s)

    @property
    def doa_url(self) -> str:
        return f"http://{self.settings.host}:{self.settings.doa_port}/DOA_value.html"

    @property
    def settings_url(self) -> str:
        # settings.json is served from the same port as DOA data in standard setups
        return f"http://{self.settings.host}:{self.settings.settings_port}/settings.json"

    @property
    def age_s(self) -> float | None:
        if self._last_success is None:
            return None
        return (datetime.now(timezone.utc) - self._last_success).total_seconds()

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_doa(self) -> list[DoaReading]:
        """
        Poll DOA_value.html and return zero or more normalized readings.
        Multiple VFOs produce multiple newline-separated CSV rows.
        """
        try:
            resp = await self._client.get(self.doa_url)
            resp.raise_for_status()
            text = resp.text.strip()
            if not text:
                return []
            readings = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                reading = self._parse_csv_line(line)
                if reading is not None:
                    readings.append(reading)
            self._last_success = datetime.now(timezone.utc)
            return readings
        except Exception as exc:
            logger.warning("Failed to fetch DOA data: %s", exc)
            return []

    def _parse_csv_line(self, line: str) -> DoaReading | None:
        """
        Parse one CSV row from Kraken App DOA format.

        Fields (positional):
          0  timestamp_unix_ms (13 digit)
          1  bearing_deg (compass 0-359)
          2  confidence (0-99)
          3  rssi_db
          4  freq_hz
          5  array_type
          6  latency_ms
          7  station_id
          8  lat
          9  lon
          10 gps_heading
          11 compass_heading
          12 heading_source
          13-16 reserved
          17-376 doa_spectrum[360] (optional)
        """
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            logger.debug("CSV line too short: %s", line[:80])
            return None
        try:
            ts_ms = int(float(parts[0]))
            # Kraken sometimes emits seconds; normalise to ms
            if ts_ms < 1_000_000_000_000:
                ts_ms *= 1000
            timestamp = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)

            bearing = float(parts[1]) % 360.0
            confidence = float(parts[2])
            # Normalise 0-99 → 0-100 for internal consistency
            if confidence <= 99.0:
                confidence = confidence * (100.0 / 99.0)
            rssi = float(parts[3])
            freq_hz = int(float(parts[4]))

            array_type = parts[5] if len(parts) > 5 else "UCA"
            latency_ms = float(parts[6]) if len(parts) > 6 and parts[6] else None
            station_id = parts[7] if len(parts) > 7 and parts[7] else None

            lat = self._opt_float(parts, 8)
            lon = self._opt_float(parts, 9)
            gps_heading = self._opt_float(parts, 10)
            compass_heading = self._opt_float(parts, 11)
            heading = compass_heading if compass_heading is not None else gps_heading

            spectrum: list[float] | None = None
            if len(parts) >= 377:
                try:
                    spectrum = [float(x) for x in parts[17:377]]
                except ValueError:
                    spectrum = None

            return DoaReading(
                timestamp=timestamp,
                bearing_deg=bearing,
                confidence=confidence,
                rssi_db=rssi,
                freq_hz=freq_hz,
                array_type=array_type,
                latency_ms=latency_ms,
                station_id=station_id,
                lat=lat,
                lon=lon,
                heading_deg=heading,
                raw_spectrum=spectrum,
            )
        except (ValueError, IndexError) as exc:
            logger.debug("Failed to parse DOA CSV line: %s (%s)", line[:100], exc)
            return None

    @staticmethod
    def _opt_float(parts: list[str], idx: int) -> float | None:
        if len(parts) <= idx or not parts[idx]:
            return None
        try:
            return float(parts[idx])
        except ValueError:
            return None

    async def get_settings(self) -> dict[str, Any]:
        """Fetch current settings.json."""
        resp = await self._client.get(self.settings_url)
        resp.raise_for_status()
        return resp.json()

    async def task_frequency(self, freq_hz: int, gain: float | None = None) -> bool:
        """
        Retune the array to the given frequency.
        This triggers a calibration cycle on the Kraken side – use sparingly.
        Returns True on success.
        """
        try:
            current = await self.get_settings()
            # Kraken settings use MHz for center_freq in most versions
            current["center_freq"] = freq_hz / 1_000_000.0
            if gain is not None:
                current["uniform_gain"] = gain
            # Force the DSP to notice the change
            current["ext_upd_flag"] = True

            # Upload via multipart form (documented Kraken remote-control method)
            upload_url = f"http://{self.settings.host}:{self.settings.settings_port}/upload?path=/"
            files = {"path": ("settings.json", str(current).replace("'", '"'), "application/json")}
            # Prefer raw JSON body if the middleware is present; fall back to file write semantics
            try:
                # Middleware style (port 8042 style)
                mw_url = f"http://{self.settings.host}:8042/settings"
                resp = await self._client.post(mw_url, json=current)
                if resp.status_code < 400:
                    logger.info("Tasked Kraken to %.3f MHz via middleware", freq_hz / 1e6)
                    return True
            except Exception:
                pass

            # Fallback: attempt settings.json upload
            resp = await self._client.post(upload_url, files=files)
            if resp.status_code < 400:
                logger.info("Tasked Kraken to %.3f MHz via settings upload", freq_hz / 1e6)
                return True

            logger.warning("Failed to task frequency %s – status %s", freq_hz, resp.status_code)
            return False
        except Exception as exc:
            logger.error("task_frequency failed: %s", exc)
            return False

    async def health(self) -> dict[str, Any]:
        age = self.age_s
        ok = age is not None and age < 5.0
        return {
            "reachable": ok,
            "age_s": age,
            "last_success": self._last_success.isoformat() if self._last_success else None,
        }
