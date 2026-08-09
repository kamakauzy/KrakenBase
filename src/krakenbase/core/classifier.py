"""Richer emitter classification from power / duration / band context."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from krakenbase.config import BaselineSettings
from krakenbase.models import (
    AnomalyEvent,
    ClassificationLabel,
    ClassificationResult,
    DoaEvent,
)

logger = logging.getLogger(__name__)


class EmitterClassifier:
    """Heuristic classifier – no ML required for v1."""

    def __init__(
        self,
        baseline: BaselineSettings | None = None,
        known_path: str | Path | None = None,
    ):
        self.baseline = baseline
        self.known: list[dict[str, Any]] = []
        if known_path and Path(known_path).exists():
            try:
                data = yaml.safe_load(Path(known_path).read_text()) or {}
                self.known = list(data.get("emitters") or [])
                logger.info("Loaded %d known emitters from %s", len(self.known), known_path)
            except Exception as exc:
                logger.warning("Failed to load known emitters: %s", exc)

    def _band_name(self, freq_hz: int) -> str | None:
        if not self.baseline:
            return None
        for b in self.baseline.bands:
            if b.start_hz <= freq_hz <= b.stop_hz:
                return b.name
        return None

    def _match_known(self, freq_hz: int) -> dict[str, Any] | None:
        for e in self.known:
            center = int(e.get("freq_hz") or 0)
            tol = int(e.get("tolerance_hz") or 12500)
            if center and abs(freq_hz - center) <= tol:
                return e
        return None

    def classify_anomaly(self, event: AnomalyEvent) -> ClassificationResult:
        labels: list[ClassificationLabel] = []
        features: dict[str, float] = {
            "margin_db": event.margin_db,
            "duration_s": event.duration_s,
            "power_db": event.power_db,
        }
        conf = 0.4

        if event.duration_s >= 8.0:
            labels.append(ClassificationLabel.PERSISTENT)
            conf += 0.15
        elif event.duration_s <= 2.5:
            labels.append(ClassificationLabel.TRANSIENT)
        else:
            labels.append(ClassificationLabel.NARROWBAND)

        if event.margin_db >= 25:
            conf += 0.15
        if event.margin_db < 12:
            labels.append(ClassificationLabel.NOISE)
            conf -= 0.1

        band = self._band_name(event.freq_hz)
        if band and band.upper() in ("GMRS", "VHF", "UHF", "HAM_2M", "HAM_70CM"):
            labels.append(ClassificationLabel.TACTICAL_VOICE)
            conf += 0.1

        known = self._match_known(event.freq_hz)
        known_name = None
        if known:
            labels.append(ClassificationLabel.KNOWN)
            known_name = known.get("name")
            conf = max(conf, 0.85)

        if not labels:
            labels.append(ClassificationLabel.UNKNOWN)

        conf = max(0.0, min(1.0, conf))
        return ClassificationResult(
            labels=labels,
            band_name=band,
            confidence=conf,
            known_name=known_name,
            notes=None,
            features=features,
        )

    def classify_doa(self, doa: DoaEvent, anomaly: AnomalyEvent | None = None) -> ClassificationResult:
        if anomaly is not None:
            result = self.classify_anomaly(anomaly)
        else:
            result = ClassificationResult(
                labels=[ClassificationLabel.UNKNOWN],
                band_name=self._band_name(doa.freq_hz),
                confidence=0.3,
            )
        result.features["df_confidence"] = doa.confidence
        result.features["rssi_db"] = doa.rssi_db
        if doa.confidence >= 85:
            result.confidence = min(1.0, result.confidence + 0.1)
        if doa.confidence < 60:
            result.confidence = max(0.0, result.confidence - 0.15)
        return result
