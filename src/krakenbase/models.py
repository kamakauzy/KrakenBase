"""Core Pydantic models for KrakenBase."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemState(str, Enum):
    INIT = "INIT"
    SCANNING = "SCANNING"
    TASKING = "TASKING"
    DWELLING = "DWELLING"
    PROCESSING = "PROCESSING"
    ALERTING = "ALERTING"
    HANDING_OFF = "HANDING_OFF"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"


class DoaReading(BaseModel):
    timestamp: datetime
    bearing_deg: float
    confidence: float
    rssi_db: float
    freq_hz: int
    array_type: str = "UCA"
    latency_ms: float | None = None
    station_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    heading_deg: float | None = None
    raw_spectrum: list[float] | None = None


class AnomalyEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utcnow)
    freq_hz: int
    power_db: float
    baseline_db: float
    margin_db: float
    duration_s: float
    source: str = "baseline_engine"


class DoaEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utcnow)
    freq_hz: int
    bearing_deg: float
    confidence: float
    rssi_db: float
    absolute_bearing_deg: float | None = None
    related_anomaly_id: UUID | None = None
    dwell_s: float
    reading: DoaReading


class AlertEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utcnow)
    channel: str
    message: str
    related_doa_id: UUID
    success: bool
    error: str | None = None


class HandOffTask(BaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    freq_hz: int
    modulation_hint: str | None = None
    priority: int = 5
    max_dwell_min: int = 30
    record_iq: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    source_event_id: UUID


class HealthStatus(BaseModel):
    status: str
    state: SystemState
    kraken_age_s: float | None = None
    last_anomaly: datetime | None = None
    last_doa: datetime | None = None
    roe_version: str = "0.1"
    version: str = "0.1.0-dev"
