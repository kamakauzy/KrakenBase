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
    mean_db: float = -120.0
    count: int = 0
    last_update: float = field(default_factory=time.time)
    # Simple exponential moving average
    alpha: float = 0.05

    def update(self, power_db: float) -> None:
        if self.count == 0:
            self.mean_db = power_db
        else:
            self.mean_db = (1 - self.alpha) * self.mean_db + self.alpha * power_db
        self.count += 1
        self.last_update = time.time()


class BaselineEngine:
    """
    Maintains per-frequency power baselines and raises AnomalyEvents
    when a signal exceeds the baseline by the configured margin for
    long enough.
    """

    def __init__(self, settings: BaselineSettings):
        self.settings = settings
        self._bins: dict[int, BinStats] = defaultdict(BinStats)
        # Track ongoing anomalies so we only fire once per excursion
        self._active: dict[int, float] = {}  # freq_hz -> first_seen_ts

    def observe(self, freq_hz: int, power_db: float) -> AnomalyEvent | None:
        """
        Feed a power observation. Returns an AnomalyEvent if a new
        sustained anomaly is detected, otherwise None.
        """
        if not self.settings.enabled:
            return None

        # Quantise to nearest bin for stability
        bin_hz = 12500  # default; could be derived from band config
        quantised = int(round(freq_hz / bin_hz) * bin_hz)

        stats = self._bins[quantised]
        margin = power_db - stats.mean_db
        now = time.time()

        if margin >= self.settings.anomaly_margin_db:
            if quantised not in self._active:
                self._active[quantised] = now
            duration = now - self._active[quantised]
            if duration >= self.settings.min_anomaly_duration_s:
                # Fire once, then keep it marked active so we don't spam
                if duration < self.settings.min_anomaly_duration_s + 1.0:
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
        else:
            # Back to normal – clear active flag and update baseline
            self._active.pop(quantised, None)
            stats.update(power_db)

        # Always slowly update baseline even during mild elevations
        if margin < self.settings.anomaly_margin_db * 0.5:
            stats.update(power_db)

        return None

    def inject_synthetic(self, freq_hz: int, power_db: float) -> AnomalyEvent | None:
        """Convenience for testing without a real scanner."""
        return self.observe(freq_hz, power_db)
