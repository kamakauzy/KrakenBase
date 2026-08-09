"""Emitter classifier tests."""

from krakenbase.config import BaselineSettings, BandConfig
from krakenbase.core.classifier import EmitterClassifier
from krakenbase.models import AnomalyEvent, ClassificationLabel


def test_classify_persistent_tactical():
    clf = EmitterClassifier(
        BaselineSettings(
            bands=[BandConfig(name="GMRS", start_hz=462500000, stop_hz=467700000)]
        )
    )
    event = AnomalyEvent(
        freq_hz=462_712_500,
        power_db=-30,
        baseline_db=-95,
        margin_db=65,
        duration_s=12.0,
    )
    result = clf.classify_anomaly(event)
    assert ClassificationLabel.PERSISTENT in result.labels
    assert ClassificationLabel.TACTICAL_VOICE in result.labels
    assert result.band_name == "GMRS"
    assert result.confidence > 0.5


def test_classify_transient():
    clf = EmitterClassifier()
    event = AnomalyEvent(
        freq_hz=433_000_000,
        power_db=-40,
        baseline_db=-90,
        margin_db=50,
        duration_s=1.0,
    )
    result = clf.classify_anomaly(event)
    assert ClassificationLabel.TRANSIENT in result.labels
