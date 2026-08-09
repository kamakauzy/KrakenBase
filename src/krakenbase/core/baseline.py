"""Simple power baseline and anomaly detector."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from krakenbase.config import BaselineSettings
from krakenbase.models import AnomalyEvent, utcnow

logger = logging.getLogger(__name__)


@dataclass
class BinStats:
    mean_db: float | None = None
    count: int = 0
    last_update: float = field(default_factory=time.time)
    alpha: float = 0.05
    min_samples: int = 8

    def update(self, power_db: float) -> None:
        if self.mean_db is None:
            self.mean_db = power_db
        else:
            self.mean_db = (1 - self.alpha) * self.mean_db + self.alpha * power_db
        self.count += 1
        self.last_update = time.time()

    @property
    def ready(self) -> bool:
        return self.mean_db is not None and self.count >= self.min_samples


class BaselineEngine:
    """
    Maintains per-frequency power baselines and raises AnomalyEvents
    when a signal exceeds the baseline by the configured margin for
    long enough. Fires once per excursion.
    """

    def __init__(self, settings: BaselineSettings):
        self.settings = settings
        self._bins: dict[int, BinStats] = defaultdict(BinStats)
        self._active: dict[int, float] = {}
        self._fired: set[int] = set()

    def observe(self, freq_hz: int, power_db: float) -> AnomalyEvent | None:
        if not self.settings.enabled:
            return None

        bin_hz = 12500
        quantised = int(round(freq_hz / bin_hz) * bin_hz)
        stats = self._bins[quantised]
        now = time.time()

        if not stats.ready:
            stats.update(power_db)
            return None

        assert stats.mean_db is not None
        margin = power_db - stats.mean_db

        if margin >= self.settings.anomaly_margin_db:
            if quantised not in self._active:
                self._active[quantised] = now
            duration = now - self._active[quantised]

            if (
                duration >= self.settings.min_anomaly_duration_s
                and quantised not in self._fired
            ):
                self._fired.add(quantised)
                event = AnomalyEvent(
                    timestamp=utcnow(),
                    freq_hz=freq_hz,
                    power_db=power_db,
                    baseline_db=stats.mean_db,
                    margin_db=margin,
                    duration_s=duration,
                )
                logger.info(
                    "Anomaly %.3f MHz  power=%.1f  baseline=%.1f  margin=%.1f  dur=%.1fs",
                    freq_hz / 1e6,
                    power_db,
                    stats.mean_db,
                    margin,
                    duration,
                )
                return event
            return None

        self._active.pop(quantised, None)
        self._fired.discard(quantised)
        stats.update(power_db)
        return None

    def inject_synthetic(self, freq_hz: int, power_db: float) -> AnomalyEvent | None:
        return self.observe(freq_hz, power_db)
