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
    """Normalized reading from Kraken DOA_value.html CSV."""

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


class RffDisposition(str, Enum):
    NO_MODEL = "NO_MODEL"
    LOW_SNR = "LOW_SNR"
    RECIPE_MISMATCH = "RECIPE_MISMATCH"
    RFF_MATCH = "RFF_MATCH"
    NEW = "NEW"
    REPEAT = "REPEAT"


class RffResult(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utcnow)
    freq_hz: int
    sensor_id: str = "none"
    recipe_id: str = "none"
    disposition: RffDisposition = RffDisposition.NO_MODEL
    emitter_uid: str | None = None
    score: float | None = None
    source_event_id: UUID | None = None
    notes: str | None = None


class UgsTrigger(str, Enum):
    HANDOFF = "handoff"
    CAMERA = "camera"
    PIR = "pir"
    SEISMIC = "seismic"
    MAG = "mag"
    ENERGY = "energy"
    SCHEDULE = "schedule"
    MANUAL = "manual"


class UgsEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    node_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    trigger: UgsTrigger
    freq_hz: int | None = None
    bandwidth_hz: int | None = None
    rssi_db: float | None = None
    snr_db: float | None = None
    duration_ms: int = 0
    sensor_id: str
    recipe_id: str = "none"
    burst_path: str | None = None
    source_task_id: UUID | None = None
    camera_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    notes: str | None = None


CAP_RTL_SDR = "rtl_sdr"
CAP_UGS_RTL_V4 = "ugs_rtl_v4"
CAP_UGS_RTL_V3 = "ugs_rtl_v3"
CAP_UGS_RSP1B = "ugs_rsp1b"
CAP_UGS_CAMERA = "ugs_camera"
CAP_RFF_EMBED = "rff_embed"


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
    rff: RffResult | None = None


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
    target_node_id: str | None = None


class HealthStatus(BaseModel):
    status: str
    state: SystemState
    kraken_age_s: float | None = None
    last_anomaly: datetime | None = None
    last_doa: datetime | None = None
    roe_version: str = "0.1"
    version: str = "0.1.0-dev"


class ClassificationLabel(str, Enum):
    UNKNOWN = "unknown"
    NOISE = "noise"
    NARROWBAND = "narrowband"
    WIDEBAND = "wideband"
    PERSISTENT = "persistent"
    TRANSIENT = "transient"
    KNOWN = "known"
    TACTICAL_VOICE = "tactical_voice"
    DATA_BURST = "data_burst"


class ClassificationResult(BaseModel):
    labels: list[ClassificationLabel] = Field(default_factory=list)
    band_name: str | None = None
    confidence: float = 0.0
    known_name: str | None = None
    notes: str | None = None
    features: dict[str, float] = Field(default_factory=dict)


class SecondaryNodeStatus(str, Enum):
    ONLINE = "online"
    BUSY = "busy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class SecondaryNode(BaseModel):
    node_id: str
    last_seen: datetime = Field(default_factory=utcnow)
    status: SecondaryNodeStatus = SecondaryNodeStatus.UNKNOWN
    capabilities: list[str] = Field(default_factory=lambda: ["rtl_sdr"])
    current_freq_hz: int | None = None
    last_task_id: str | None = None
    site: str | None = None
    notes: str | None = None
