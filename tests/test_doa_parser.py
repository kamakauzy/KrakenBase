"""Unit tests for Kraken DOA CSV parsing."""

from datetime import timezone

import pytest

from krakenbase.client.kraken import KrakenClient
from krakenbase.config import KrakenSettings


@pytest.fixture
def client():
    return KrakenClient(KrakenSettings())


def test_parse_basic_line(client):
    # Minimal realistic CSV line (no spectrum)
    line = "1723221000123,142.3,87.4,-42.1,462712500,UCA,12,Station1,34.73,-86.58,15.0,,GPS"
    reading = client._parse_csv_line(line)
    assert reading is not None
    assert reading.bearing_deg == pytest.approx(142.3)
    assert reading.confidence == pytest.approx(87.4 * 100 / 99, rel=1e-2)
    assert reading.rssi_db == pytest.approx(-42.1)
    assert reading.freq_hz == 462712500
    assert reading.array_type == "UCA"
    assert reading.lat == pytest.approx(34.73)
    assert reading.timestamp.tzinfo == timezone.utc


def test_parse_short_line_rejected(client):
    assert client._parse_csv_line("1,2,3") is None


def test_parse_seconds_timestamp(client):
    # Some older outputs may use seconds
    line = "1723221000,90,50,-30,433000000,UCA"
    reading = client._parse_csv_line(line)
    assert reading is not None
    # Should have been multiplied to ms
    assert reading.timestamp.year >= 2024
