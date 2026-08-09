"""Baseline engine unit tests."""

import time

from krakenbase.config import BaselineSettings
from krakenbase.core.baseline import BaselineEngine


def _warm(eng: BaselineEngine, freq: int = 462_712_500, power: float = -95.0, n: int = 12):
    for _ in range(n):
        eng.observe(freq, power)


def test_no_anomaly_on_noise():
    eng = BaselineEngine(
        BaselineSettings(anomaly_margin_db=10.0, min_anomaly_duration_s=0.5)
    )
    for _ in range(20):
        assert eng.observe(462_712_500, -95.0) is None


def test_anomaly_fires_after_duration():
    eng = BaselineEngine(
        BaselineSettings(anomaly_margin_db=10.0, min_anomaly_duration_s=0.25)
    )
    _warm(eng)

    assert eng.observe(462_712_500, -30.0) is None
    time.sleep(0.3)
    event = eng.observe(462_712_500, -30.0)
    assert event is not None
    assert event.freq_hz == 462_712_500
    assert event.margin_db >= 10.0

    time.sleep(0.1)
    assert eng.observe(462_712_500, -30.0) is None
    assert eng.observe(462_712_500, -28.0) is None


def test_anomaly_clears_and_can_refire():
    eng = BaselineEngine(
        BaselineSettings(anomaly_margin_db=10.0, min_anomaly_duration_s=0.2)
    )
    _warm(eng)

    assert eng.observe(462_712_500, -30.0) is None
    time.sleep(0.25)
    assert eng.observe(462_712_500, -30.0) is not None

    for _ in range(5):
        assert eng.observe(462_712_500, -95.0) is None

    assert eng.observe(462_712_500, -30.0) is None
    time.sleep(0.25)
    assert eng.observe(462_712_500, -30.0) is not None


def test_disabled_baseline():
    eng = BaselineEngine(BaselineSettings(enabled=False))
    assert eng.observe(100_000_000, 0.0) is None
