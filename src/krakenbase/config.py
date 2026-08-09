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
    control_method: str = "settings_json"  # settings_json | middleware


class ArraySettings(BaseModel):
    type: str = "UCA"
    radius_m: float = 0.15
    heading_offset_deg: float = 0.0
    element_order: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


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
    power_source: str = "kraken"  # kraken | rtl_power | synthetic


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
    transport: str = "mqtt"  # mqtt | http | udp | file
    mqtt: MqttSettings = Field(default_factory=MqttSettings)
    defaults: HandOffDefaults = Field(default_factory=HandOffDefaults)


class StatusApiSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8090


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


class Settings(BaseSettings):
    """Top-level settings. Load from YAML then apply env overrides."""

    system: SystemSettings = Field(default_factory=SystemSettings)
    kraken: KrakenSettings = Field(default_factory=KrakenSettings)
    array: ArraySettings = Field(default_factory=ArraySettings)
    baseline: BaselineSettings = Field(default_factory=BaselineSettings)
    dwell: DwellSettings = Field(default_factory=DwellSettings)
    alert: AlertSettings = Field(default_factory=AlertSettings)
    handoff: HandOffSettings = Field(default_factory=HandOffSettings)
    status_api: StatusApiSettings = Field(default_factory=StatusApiSettings)
    roe: RoeSettings = Field(default_factory=RoeSettings)

    model_config = {"env_prefix": "KB_", "env_nested_delimiter": "__"}


def load_config(path: str | Path | None = None) -> Settings:
    """Load settings from YAML file, then overlay environment variables."""
    data: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if p.exists():
            with p.open() as f:
                data = yaml.safe_load(f) or {}
    return Settings(**data)
