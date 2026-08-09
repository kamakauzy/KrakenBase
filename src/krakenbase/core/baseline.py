"""Multi-band power baseline and anomaly detector."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from krakenbase.config import BaselineSettings, BandConfig
from krakenbase.models import AnomalyEvent, utcnow

logger = logging.getLogger(__name__)


@dataclass
class BinStats:
    mean_db: float | None = None
    count: int = 0
    last_update: float = field(default_factory=time.time)
    alpha: float = 0.05
    min_samples: int = 8
    band_name: str | None = None

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
    """Per-frequency baselines with multi-band awareness and waterfall history."""

    def __init__(self, settings: BaselineSettings):
        self.settings = settings
        self._bins: dict[int, BinStats] = defaultdict(BinStats)
        self._active: dict[int, float] = {}
        self._fired: set[int] = set()
        self._band_hits: dict[str, int] = defaultdict(int)
        self._history: list[dict] = []
        self._history_max = 120
        self._last_frame_t = 0.0

    def _band_for(self, freq_hz: int) -> BandConfig | None:
        for b in self.settings.bands:
            if b.start_hz <= freq_hz <= b.stop_hz:
                return b
        return None

    def in_scope(self, freq_hz: int) -> bool:
        if not self.settings.bands:
            return True
        return self._band_for(freq_hz) is not None

    def observe(self, freq_hz: int, power_db: float) -> AnomalyEvent | None:
        if not self.settings.enabled:
            return None
        if not self.in_scope(freq_hz):
            return None

        band = self._band_for(freq_hz)
        bin_hz = band.bin_hz if band else 12500
        quantised = int(round(freq_hz / bin_hz) * bin_hz)
        stats = self._bins[quantised]
        if band and stats.band_name is None:
            stats.band_name = band.name
        now = time.time()

        if not stats.ready:
            stats.update(power_db)
            self._maybe_record_frame()
            return None

        assert stats.mean_db is not None
        margin = power_db - stats.mean_db

        if margin >= self.settings.anomaly_margin_db:
            if quantised not in self._active:
                self._active[quantised] = now
            duration = now - self._active[quantised]
            if duration >= self.settings.min_anomaly_duration_s and quantised not in self._fired:
                self._fired.add(quantised)
                if band:
                    self._band_hits[band.name] += 1
                event = AnomalyEvent(
                    timestamp=utcnow(),
                    freq_hz=freq_hz,
                    power_db=power_db,
                    baseline_db=stats.mean_db,
                    margin_db=margin,
                    duration_s=duration,
                )
                logger.info(
                    "Anomaly %.3f MHz [%s] power=%.1f baseline=%.1f margin=%.1f dur=%.1fs",
                    freq_hz / 1e6,
                    band.name if band else "?",
                    power_db,
                    stats.mean_db,
                    margin,
                    duration,
                )
                self._maybe_record_frame()
                return event
            return None

        self._active.pop(quantised, None)
        self._fired.discard(quantised)
        stats.update(power_db)
        self._maybe_record_frame()
        return None

    def band_summary(self) -> list[dict]:
        out = []
        for b in self.settings.bands:
            bins_in = [s for f, s in self._bins.items() if b.start_hz <= f <= b.stop_hz]
            ready = sum(1 for s in bins_in if s.ready)
            out.append(
                {
                    "name": b.name,
                    "start_hz": b.start_hz,
                    "stop_hz": b.stop_hz,
                    "bin_hz": b.bin_hz,
                    "bins": len(bins_in),
                    "ready_bins": ready,
                    "anomaly_hits": self._band_hits.get(b.name, 0),
                }
            )
        return out

    def _maybe_record_frame(self) -> None:
        now = time.time()
        if now - self._last_frame_t < 0.5:
            return
        self._last_frame_t = now
        bins = []
        for freq, stats in self._bins.items():
            if stats.mean_db is None:
                continue
            bins.append({"freq_hz": freq, "power_db": round(stats.mean_db, 1)})
        if not bins:
            return
        bins.sort(key=lambda b: b["freq_hz"])
        self._history.append({"t": now, "bins": bins})
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max :]

    def waterfall_history(self, max_frames: int = 60) -> list[dict]:
        self._maybe_record_frame()
        return self._history[-max_frames:]

    def inject_synthetic(self, freq_hz: int, power_db: float) -> AnomalyEvent | None:
        return self.observe(freq_hz, power_db)
