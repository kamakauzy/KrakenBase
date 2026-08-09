"""Heading fusion tests."""

from krakenbase.core.heading import HeadingFusion


def test_config_offset_only():
    h = HeadingFusion(heading_offset_deg=15.0)
    assert abs(h.absolute_bearing(90.0) - 105.0) < 0.01
    snap = h.snapshot()
    assert snap["source"] == "config"
    assert snap["stale"] is True


def test_compass_preferred():
    h = HeadingFusion(heading_offset_deg=0.0, stale_after_s=60)
    h.update_from_doa(gps_heading=10.0, compass_heading=20.0)
    assert abs(h.absolute_bearing(0.0) - 20.0) < 0.01
    assert h.snapshot()["source"] == "compass"


def test_gps_when_no_compass():
    h = HeadingFusion(heading_offset_deg=0.0, stale_after_s=60)
    h.update_from_doa(gps_heading=45.0)
    assert abs(h.absolute_bearing(5.0) - 50.0) < 0.01
