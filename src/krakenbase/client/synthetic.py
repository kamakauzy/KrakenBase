"""Synthetic Kraken client – full loop without hardware."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from typing import Any

from krakenbase.models import DoaReading

logger = logging.getLogger(__name__)


class SyntheticKrakenClient:
    """
    Drop-in stand-in for KrakenClient.

    Emits quiet noise-floor readings most of the time, then injects a
    sustained strong signal so the baseline engine fires an anomaly.
    After task_frequency(), returns high-confidence bearings on the
    tasked frequency for the dwell window.
    """

    def __init__(
        self,
        anomaly_freq_hz: int = 462_712_500,
        anomaly_bearing_deg: float = 142.0,
        anomaly_rssi_db: float = -35.0,
        noise_rssi_db: float = -95.0,
        anomaly_interval_s: float = 25.0,
        anomaly_duration_s: float = 8.0,
        min_confidence: float = 85.0,
    ):
        self.anomaly_freq_hz = anomaly_freq_hz
        self.anomaly_bearing_deg = anomaly_bearing_deg
        self.anomaly_rssi_db = anomaly_rssi_db
        self.noise_rssi_db = noise_rssi_db
        self.anomaly_interval_s = anomaly_interval_s
        self.anomaly_duration_s = anomaly_duration_s
        self.min_confidence = min_confidence

        self._last_success = datetime.now(timezone.utc)
        self._start = time.monotonic()
        self._tasked_freq: int | None = None
        self._tasked_at: float | None = None
        self._cycle = 0

    @property
    def age_s(self) -> float:
        return (datetime.now(timezone.utc) - self._last_success).total_seconds()

    async def close(self) -> None:
        return

    def _noise_reading(self, freq_hz: int | None = None) -> DoaReading:
        freq = freq_hz or random.choice(
            [146_520_000, 446_000_000, 433_000_000, 462_562_500]
        )
        return DoaReading(
            timestamp=datetime.now(timezone.utc),
            bearing_deg=random.uniform(0, 359),
            confidence=random.uniform(5, 25),
            rssi_db=self.noise_rssi_db + random.uniform(-3, 3),
            freq_hz=freq,
            array_type="UCA",
            latency_ms=random.uniform(8, 20),
            station_id="SYNTH",
        )

    def _anomaly_reading(self) -> DoaReading:
        bearing = (self.anomaly_bearing_deg + random.uniform(-4, 4)) % 360
        conf = min(99.0, self.min_confidence + random.uniform(0, 12))
        return DoaReading(
            timestamp=datetime.now(timezone.utc),
            bearing_deg=bearing,
            confidence=conf,
            rssi_db=self.anomaly_rssi_db + random.uniform(-2, 2),
            freq_hz=self.anomaly_freq_hz,
            array_type="UCA",
            latency_ms=random.uniform(10, 18),
            station_id="SYNTH",
        )

    def _in_anomaly_window(self) -> bool:
        elapsed = time.monotonic() - self._start
        period = self.anomaly_interval_s + self.anomaly_duration_s
        phase = elapsed % period
        return phase >= self.anomaly_interval_s

    async def fetch_doa(self) -> list[DoaReading]:
        self._last_success = datetime.now(timezone.utc)
        self._cycle += 1

        if self._tasked_freq is not None and self._tasked_at is not None:
            age = time.monotonic() - self._tasked_at
            if age < 12.0:
                r = self._anomaly_reading()
                r.freq_hz = self._tasked_freq
                r.confidence = min(99.0, r.confidence + 3)
                return [r]
            self._tasked_freq = None
            self._tasked_at = None

        if self._in_anomaly_window():
            return [self._anomaly_reading()]

        readings = [self._noise_reading(self.anomaly_freq_hz)]
        if random.random() < 0.4:
            readings.append(self._noise_reading())
        return readings

    async def get_settings(self) -> dict[str, Any]:
        return {
            "center_freq": (self._tasked_freq or 446_000_000) / 1e6,
            "uniform_gain": 30.0,
            "ext_upd_flag": False,
            "synthetic": True,
        }

    async def task_frequency(self, freq_hz: int, gain: float | None = None) -> bool:
        logger.info("SYNTH tasked to %.4f MHz", freq_hz / 1e6)
        self._tasked_freq = freq_hz
        self._tasked_at = time.monotonic()
        return True

    async def health(self) -> dict[str, Any]:
        return {
            "reachable": True,
            "age_s": self.age_s,
            "last_success": self._last_success.isoformat(),
            "synthetic": True,
            "tasked_freq": self._tasked_freq,
            "in_anomaly_window": self._in_anomaly_window(),
        }
