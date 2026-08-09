# KrakenBase – Architecture

## 1. High-Level View

```
┌─────────────────────────────────────────────────────────────┐
│                     Laptop (Ubuntu)                         │
│  ┌──────────────────┐    ┌─────────────────────────────┐  │
│  │  Heimdall DAQ    │◀──▶│  krakensdr_doa (DSP + UI)    │  │
│  │  (5ch coherent)  │    │  ports 8080 / 8081 / 8042    │  │
│  └──────────────────┘    └───────────────┬──────────────┘  │
│                                         │ localhost         │
│  ┌─────────────────────────────────────▼───────────────┐  │
│  │                 KrakenBase Brain                     │  │
│  │  • Baseline engine                                   │  │
│  │  • Adaptive state machine                            │  │
│  │  • Kraken client (poll + task)                       │  │
│  │  • Event store (SQLite)                              │  │
│  │  • Alert publisher (Meshtastic)                      │  │
│  │  • Hand-off publisher                                │  │
│  │  • Status API (FastAPI)                              │  │
│  └────────────────────────────────────────────────────┘  │
│           │                              │                  │
└────────────┴───────────────────────────────┴──────────────────┘
            │ USB/serial                   │ network / mesh
            ▼                              ▼
     Meshtastic radio              Secondary RTL-SDR nodes
                                   (optional monitors)
```

## 2. Component Responsibilities

### 2.1 Kraken Stack (upstream, unmodified)
- Heimdall: coherent IQ acquisition and calibration.
- krakensdr_doa: MUSIC/Capon/etc., web UI, `DOA_value.html` CSV output, `settings.json` control plane.

KrakenBase treats this stack as a black-box sensor + actuator.

### 2.2 Kraken Client
- Polls `http://127.0.0.1:8081/DOA_value.html` (or JSON equivalents).
- Parses the CSV into a normalized `DoaReading` model.
- Tasks the array by writing / uploading `settings.json` (or middleware POST to :8042).
- Reports health (last successful poll age, calibration state if available).

### 2.3 Baseline Engine
- Maintains power statistics per monitored band or channel.
- Can be fed by:
  - Periodic `rtl_power`-style sweeps on a spare RTL-SDR, or
  - Spectrum data derived from Kraken when available, or
  - Simple energy detection on the current VFO.
- Emits `AnomalyEvent` when thresholds are crossed.

### 2.4 Adaptive State Machine
Central orchestrator. States:

- `INIT`
- `SCANNING`
- `TASKING`
- `DWELLING`
- `PROCESSING_RESULT`
- `ALERTING`
- `HANDING_OFF`
- `FAULT` / `DEGRADED`

Transitions are driven by timers, anomaly events, and DOA results. Every transition is logged.

### 2.5 Event Store
SQLite (aiosqlite). Stores:
- Anomaly detections
- DOA results
- Alerts sent
- Hand-off tasks
- Health snapshots

### 2.6 Alert & Hand-off Publishers
- Meshtastic: short text or structured packets.
- Local hand-off: MQTT, simple HTTP, or UDP JSON to secondary nodes.
- Both are fire-and-forget in v1 with local audit log.

### 2.7 Status API
Minimal FastAPI surface:
- `GET /health`
- `GET /state`
- `GET /last_events`
- `POST /config/reload` (optional)

## 3. Data Flow (Happy Path)

1. Baseline engine reports anomaly at frequency F.
2. State machine enters TASKING → writes new center frequency / VFO settings to Kraken.
3. After short settle time, enters DWELLING and collects N DOA readings.
4. Selects best reading (highest confidence above threshold).
5. Creates `DoaEvent`, stores it, emits Meshtastic alert.
6. Publishes hand-off task for frequency F.
7. Releases VFO / returns to previous scan settings.
8. Returns to SCANNING.

## 4. Failure Modes

| Failure                    | Behavior                                      |
|----------------------------|-----------------------------------------------|
| Kraken unreachable         | Enter DEGRADED, keep trying, surface in /health |
| Low confidence DOA         | Log, do not alert, return to scan             |
| Meshtastic down            | Log alert as failed, continue                |
| Secondary nodes offline    | Hand-off still recorded locally               |
| Config invalid             | Refuse to start or stay in INIT with error    |

## 5. Deployment Notes

- Prefer running Heimdall + krakensdr_doa under their normal start scripts.
- KrakenBase runs as a separate systemd user service or Docker container.
- All communication with Kraken is localhost-only by default.
- Array geometry (UCA radius, element order, heading offset) is configuration, not code.
