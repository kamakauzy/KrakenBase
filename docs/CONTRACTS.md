# KrakenBase – Interface Contracts

## 1. KrakenSDR DOA Data Contract (Inbound)

**Endpoint (default):** `http://127.0.0.1:8081/DOA_value.html`  
**Format:** CSV (Kraken App mode)  
**Update rate:** every DOA processing cycle (typically several times per second)

### CSV Fields (positional)

| Index | Name                  | Type / Notes                                      |
|-------|-----------------------|---------------------------------------------------|
| 0     | timestamp_unix_ms     | 13-digit epoch ms                                 |
| 1     | bearing_deg           | Compass convention 0–359 (0 = North, 90 = East)   |
| 2     | confidence            | 0–99 (float)                                      |
| 3     | rssi_db               | relative, 0 dB ≈ max                              |
| 4     | freq_hz               | channel frequency                                 |
| 5     | array_type            | "UCA" / "ULA" / "Custom"                          |
| 6     | latency_ms            | processing latency                                |
| 7     | station_id            | string                                            |
| 8     | latitude              | optional                                          |
| 9     | longitude             | optional                                          |
| 10    | gps_heading           | optional                                          |
| 11    | compass_heading       | optional                                          |
| 12    | heading_source        | "GPS" / "Compass"                                 |
| 13-16 | reserved              |                                                   |
| 17-376| doa_spectrum[360]     | unit-circle convention power vector (optional use)|

Multiple VFOs produce multiple newline-separated CSV rows.

### Normalized Internal Model

```python
class DoaReading(BaseModel):
    timestamp: datetime
    bearing_deg: float          # compass convention
    confidence: float           # 0-100
    rssi_db: float
    freq_hz: int
    array_type: str
    latency_ms: float | None
    station_id: str | None
    lat: float | None
    lon: float | None
    heading_deg: float | None   # fused or raw
    raw_spectrum: list[float] | None
```

## 2. Kraken Control Contract (Outbound)

Primary methods (in order of preference):

1. **settings.json upload**  
   - GET `http://127.0.0.1:8081/settings.json`  
   - Modify relevant fields (center_freq, gain, VFO parameters, etc.)  
   - POST / upload back via the documented upload endpoint or by writing the shared file when running co-located.

2. **Middleware API** (if enabled)  
   - `http://127.0.0.1:8042/settings`  
   - GET current, POST new JSON.

**Important:** Changing center frequency triggers a calibration cycle. Keep tasking infrequent and short.

KrakenBase must never leave the array in a permanent tuned state after a dwell.

## 3. Internal Event Contracts

### AnomalyEvent
```json
{
  "event_id": "uuid",
  "type": "anomaly",
  "timestamp": "ISO-8601",
  "freq_hz": 462712500,
  "power_db": -38.2,
  "baseline_db": -51.0,
  "margin_db": 12.8,
  "duration_s": 3.1,
  "source": "baseline_engine"
}
```

### DoaEvent
```json
{
  "event_id": "uuid",
  "type": "doa_result",
  "timestamp": "ISO-8601",
  "freq_hz": 462712500,
  "bearing_deg": 142.3,
  "confidence": 87.4,
  "rssi_db": -42.1,
  "absolute_bearing_deg": 157.3,
  "related_anomaly_id": "uuid",
  "dwell_s": 2.5
}
```

### AlertEvent
```json
{
  "event_id": "uuid",
  "type": "alert",
  "timestamp": "ISO-8601",
  "channel": "meshtastic",
  "message": "DF 462.7125 MHz @ 142° conf 87",
  "related_doa_id": "uuid",
  "success": true
}
```

### HandOffTask
```json
{
  "task_id": "uuid",
  "freq_hz": 462712500,
  "modulation_hint": "NFM",
  "priority": 5,
  "max_dwell_min": 30,
  "record_iq": false,
  "created_at": "ISO-8601",
  "source_event_id": "uuid"
}
```

## 4. Meshtastic Alert Format (v1)

Keep under ~200 characters. Example:

```
KB|462.7125|142°|87|A1B2
```

or slightly more readable:

```
KrakenBase DF: 462.7125 MHz bearing 142° conf 87
```

Structured JSON over Meshtastic is optional later; start with plain text.

## 5. Status API (FastAPI)

```
GET /health
→ { "status": "ok"|"degraded"|"fault", "kraken_age_s": 1.2, "state": "SCANNING", ... }

GET /state
→ current state machine state + key timers

GET /events?limit=50
→ recent events (anomaly, doa, alert)
```

All responses are JSON. No authentication in v0.1 (localhost or trusted network only).

## 6. Configuration Contract

See `config/config.example.yaml`. All thresholds, dwell times, band lists, Meshtastic destination, and array heading offset must be configurable. No magic numbers in code.
