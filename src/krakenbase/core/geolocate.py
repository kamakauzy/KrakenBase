"""Single-site LOB → estimated lat/lon projection."""

from __future__ import annotations

import math
from dataclasses import dataclass

from krakenbase.config import SiteSettings

_R = 6_371_000.0


@dataclass
class GeoEstimate:
    lat: float
    lon: float
    range_m: float
    bearing_deg: float
    method: str
    site_lat: float
    site_lon: float
    note: str = "single-site LOB projection – not a cross-fix fix"


def destination_point(lat: float, lon: float, bearing_deg: float, range_m: float) -> tuple[float, float]:
    δ = range_m / _R
    θ = math.radians(bearing_deg % 360.0)
    φ1 = math.radians(lat)
    λ1 = math.radians(lon)
    sinφ1, cosφ1 = math.sin(φ1), math.cos(φ1)
    sinδ, cosδ = math.sin(δ), math.cos(δ)
    sinφ2 = sinφ1 * cosδ + cosφ1 * sinδ * math.cos(θ)
    φ2 = math.asin(max(-1.0, min(1.0, sinφ2)))
    y = math.sin(θ) * sinδ * cosφ1
    x = cosδ - sinφ1 * sinφ2
    λ2 = λ1 + math.atan2(y, x)
    return math.degrees(φ2), (math.degrees(λ2) + 540.0) % 360.0 - 180.0


def estimate_range_m(rssi_db: float, settings: SiteSettings) -> tuple[float, str]:
    if not settings.use_rssi_range:
        return settings.default_range_m, "default_range"
    n = max(1.5, settings.path_loss_n)
    exponent = (settings.rssi_ref_db - rssi_db) / (10.0 * n)
    r = settings.rssi_ref_range_m * (10.0 ** exponent)
    r = max(settings.min_range_m, min(settings.max_range_m, r))
    return r, "rssi"


def project_emitter(
    bearing_deg: float,
    settings: SiteSettings,
    rssi_db: float | None = None,
    range_m: float | None = None,
) -> GeoEstimate | None:
    if settings.lat is None or settings.lon is None:
        return None
    if range_m is not None:
        r, method = float(range_m), "fixed_range"
    elif rssi_db is not None:
        r, method = estimate_range_m(rssi_db, settings)
    else:
        r, method = settings.default_range_m, "default_range"
    r = max(settings.min_range_m, min(settings.max_range_m, r))
    lat2, lon2 = destination_point(settings.lat, settings.lon, bearing_deg, r)
    return GeoEstimate(
        lat=lat2,
        lon=lon2,
        range_m=r,
        bearing_deg=bearing_deg % 360.0,
        method=method,
        site_lat=settings.lat,
        site_lon=settings.lon,
    )
