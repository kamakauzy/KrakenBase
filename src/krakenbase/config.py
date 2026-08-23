"""Configuration loading for KrakenBase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class KrakenSettings(BaseModel):
    host: str = "127.0.0.1"
    doa_port: int = 8081
    settings_port: int = 8081
    poll_interval_s: float = 0.5
    min_confidence: float = 70.0
    request_timeout_s: float = 2.0
    control_method: str = "settings_json"
    tune_verify_s: float = 2.0
    tune_tolerance_hz: int = 50000
    recover_fail_limit: int = 5


class ArraySettings(BaseModel):
    type: str = "UCA"
    radius_m: float = 0.15
    heading_offset_deg: float = 0.0
    element_order: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    nmea_path: str | None = None
    heading_stale_s: float = 30.0


class SiteSettings(BaseModel):
    """Optional site origin for single-LOB projection (not a cross-fix)."""

    lat: float | None = None
    lon: float | None = None
    default_range_m: float = 500.0
    min_range_m: float = 25.0
    max_range_m: float = 5000.0
    use_rssi_range: bool = False
    rssi_ref_db: float = -40.0
    rssi_ref_range_m: float = 100.0
    path_loss_n: float = 2.5


class BandConfig(BaseModel):
    name: str
    start_hz: int
    stop_hz: int
    bin_hz: int = 25000


class BaselineSettings(BaseModel):
    enabled: bool = True
    bands: list[BandConfig] = Field(default_factory=list)
    update_interval_s: float = 30.0
    anomaly_margin_db: float = 10.0
    min_anomaly_duration_s: float = 2.0
    rearm_s: float = 300.0
    power_source: str = "kraken"


class DwellSettings(BaseModel):
    default_s: float = 2.5
    max_s: float = 5.0
    settle_s: float = 1.0
    max_readings: int = 5


class MeshtasticSettings(BaseModel):
    enabled: bool = True
    interface: str = "/dev/ttyUSB0"
    channel_index: int = 0
    rate_limit_s: float = 60.0
    include_site: bool = True
    destination: str | None = None
    want_ack: bool = False
    hop_limit: int = 3
    cli_fallback: bool = True


class AlertSettings(BaseModel):
    meshtastic: MeshtasticSettings = Field(default_factory=MeshtasticSettings)
    local: dict[str, Any] = Field(default_factory=lambda: {"enabled": True})


class HandOffDefaults(BaseModel):
    priority: int = 5
    max_dwell_min: int = 30
    record_iq: bool = False


class MqttSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 1883
    topic: str = "krakenbase/handoff"


class HandOffSettings(BaseModel):
    enabled: bool = True
    transport: str = "file"
    mqtt: MqttSettings = Field(default_factory=MqttSettings)
    defaults: HandOffDefaults = Field(default_factory=HandOffDefaults)


class StatusApiSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8090
    token: str | None = None


class RoeSettings(BaseModel):
    version: str = "0.1"
    require_audit: bool = True
    allow_tx: bool = False


class SystemSettings(BaseModel):
    name: str = "KrakenBase-Primary"
    site_id: str = "patrol-base-01"
    log_level: str = "INFO"
    data_dir: str = "/var/lib/krakenbase"
    audit_db: str = "/var/lib/krakenbase/events.db"
    retention_days: float = 30.0


class Settings(BaseSettings):
    system: SystemSettings = Field(default_factory=SystemSettings)
    kraken: KrakenSettings = Field(default_factory=KrakenSettings)
    array: ArraySettings = Field(default_factory=ArraySettings)
    baseline: BaselineSettings = Field(default_factory=BaselineSettings)
    dwell: DwellSettings = Field(default_factory=DwellSettings)
    alert: AlertSettings = Field(default_factory=AlertSettings)
    handoff: HandOffSettings = Field(default_factory=HandOffSettings)
    status_api: StatusApiSettings = Field(default_factory=StatusApiSettings)
    roe: RoeSettings = Field(default_factory=RoeSettings)
    site: SiteSettings = Field(default_factory=SiteSettings)

    model_config = {"env_prefix": "KB_", "env_nested_delimiter": "__"}


def load_config(path: str | Path | None = None) -> Settings:
    data: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if p.exists():
            with p.open() as f:
                data = yaml.safe_load(f) or {}
    return Settings(**data)
