"""Meshtastic alerter tests (no radio required)."""

import asyncio
from uuid import uuid4

from krakenbase.alerts.meshtastic_alert import MeshtasticAlerter, format_df_message
from krakenbase.config import MeshtasticSettings
from krakenbase.models import DoaEvent, DoaReading, utcnow


def _doa(**kwargs) -> DoaEvent:
    reading = DoaReading(
        timestamp=utcnow(),
        bearing_deg=kwargs.get("bearing_deg", 142.0),
        confidence=kwargs.get("confidence", 88.0),
        rssi_db=kwargs.get("rssi_db", -42.0),
        freq_hz=kwargs.get("freq_hz", 462_712_500),
    )
    return DoaEvent(
        event_id=kwargs.get("event_id", uuid4()),
        timestamp=utcnow(),
        freq_hz=reading.freq_hz,
        bearing_deg=reading.bearing_deg,
        confidence=reading.confidence,
        rssi_db=reading.rssi_db,
        absolute_bearing_deg=kwargs.get("absolute_bearing_deg", 150.0),
        dwell_s=2.0,
        reading=reading,
    )


def test_format_message_compact():
    doa = _doa()
    msg = format_df_message(doa, site_id="pb-01")
    assert msg.startswith("KB[pb-01]|")
    assert "462.7125" in msg
    assert "150" in msg
    assert "c88" in msg


def test_local_fallback_when_disabled():
    alerter = MeshtasticAlerter(MeshtasticSettings(enabled=False), site_id="test")
    evt = asyncio.run(alerter.send(_doa()))
    assert evt.channel == "local"
    assert evt.success is True


def test_rate_limit():
    alerter = MeshtasticAlerter(
        MeshtasticSettings(enabled=True, rate_limit_s=999, interface="/dev/null"),
        site_id="test",
    )
    alerter._iface = None
    alerter._connect = lambda: False  # type: ignore
    doa = _doa(freq_hz=100_000_000)
    asyncio.run(alerter.send(doa))
    e2 = asyncio.run(alerter.send(doa))
    assert e2.success is False
    assert e2.error == "rate-limited"


def test_mock_iface_send():
    class FakeIface:
        def __init__(self):
            self.sent = []

        def sendText(self, msg, **kwargs):
            self.sent.append((msg, kwargs))

        def close(self):
            pass

    alerter = MeshtasticAlerter(
        MeshtasticSettings(enabled=True, rate_limit_s=0, cli_fallback=False),
        site_id="pb",
    )
    fake = FakeIface()
    alerter._iface = fake
    evt = asyncio.run(alerter.send(_doa()))
    assert evt.success is True
    assert evt.channel == "meshtastic"
    assert len(fake.sent) == 1
