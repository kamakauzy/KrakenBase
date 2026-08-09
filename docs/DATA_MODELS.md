# KrakenBase – Data Models

## 1. Core Pydantic Models (Python)

```python
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

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
    timestamp: datetime
    freq_hz: int
    power_db: float
    baseline_db: float
    margin_db: float
    duration_s: float
    source: str = "baseline_engine"

class DoaEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
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
    timestamp: datetime
    channel: str                  # "meshtastic" | "local" | ...
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
    created_at: datetime
    source_event_id: UUID
```

## 2. SQLite Schema (sketch)

```sql
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,          -- anomaly | doa | alert | handoff | health
    timestamp TEXT NOT NULL,
    payload JSON NOT NULL,
    related_id TEXT
);

CREATE TABLE baselines (
    band_id TEXT,
    freq_hz INTEGER,
    mean_db REAL,
    std_db REAL,
    updated_at TEXT,
    PRIMARY KEY (band_id, freq_hz)
);

CREATE TABLE state_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    reason TEXT
);
```

## 3. Baseline Representation

Simple per-bin or per-channel statistics are sufficient for v1:

- `mean_db`
- `std_db` or percentile
- `last_updated`
- optional `hit_count`

Anomaly rule example:

```
if current_power > mean + (k * std)  for  duration > T_min
   → raise AnomalyEvent
```

## 4. Configuration Model (high level)

See `config/config.example.yaml` for the full structure. Key sections:

- `kraken`: host, ports, poll interval, min confidence
- `array`: type, radius_m, heading_offset_deg
- `baseline`: bands, update interval, anomaly margin_db, min_duration_s
- `dwell`: default_s, max_s, settle_s
- `alert`: meshtastic enabled, destination, rate_limit
- `handoff`: enabled, transport, defaults
- `logging`: level, audit path
