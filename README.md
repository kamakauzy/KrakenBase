# KrakenBase

**Fixed-site / patrol-base coherent SIGINT node**

KrakenBase turns a KrakenSDR 5-channel array + laptop into an adaptive search → detect → DF → alert → hand-off system for permanent or semi-permanent installations.

It is deliberately simpler and more operational than the portable Recon-Raven platform.  
Design goals: fewer moving parts, battery-capable laptop host, clear ROE, clean hand-off of frequencies to secondary RTL-SDR monitors.

## Core Loop

1. Continuously scan / maintain spectrum baseline across tactical bands  
2. Detect anomaly (power, new emitter, persistent signal)  
3. Task KrakenSDR for short coherent DOA dwell  
4. Produce bearing + confidence + frequency  
5. Emit mesh (Meshtastic) and/or local alert  
6. Hand frequency to secondary monitor nodes for long-duration recording / transcription  
7. Return array to scan mode

## Key Design Decisions

- **Laptop-first** (Ubuntu). Kraken software runs natively on x86.  
- Single primary box preferred (fewer moving parts). Secondary RTL-SDR boxes optional.  
- Purely passive by default. No transmit capability in v1.  
- Borrows proven collectors and adaptive logic from `sigint-field-kit` and Recon-Raven, but does not carry their mobile/backpack complexity.  
- Strict ROE and audit logging from day one.

## Hardware Baseline

| Component              | Role                                      | Notes                          |
|------------------------|-------------------------------------------|--------------------------------|
| KrakenSDR              | 5-channel coherent array                  | UCA preferred                  |
| Laptop (Ubuntu 22.04+) | Heimdall + DOA DSP + KrakenBase brain     | 16 GB+ RAM recommended         |
| GPS (optional)         | Absolute positioning / heading            | USB or built-in                |
| Meshtastic radio       | Outbound alerts                           | USB/serial                     |
| Secondary RTL-SDR nodes| Long-dwell monitoring & transcription     | Optional, taskable             |

## Quick Status

This is a green-field project. The documentation set below is the starting point for AI-assisted implementation.

## Documentation Map

| File                    | Purpose                                      |
|-------------------------|----------------------------------------------|
| `agent.md`              | Primary instructions for AI coding agents    |
| `docs/SPEC.md`          | Functional & non-functional requirements     |
| `docs/ARCHITECTURE.md`  | System design, components, data flow         |
| `docs/CONTRACTS.md`     | APIs, message schemas, Kraken interfaces     |
| `docs/ROE.md`           | Rules of Engagement, legal, safety           |
| `docs/DATA_MODELS.md`   | Internal events, DB schema, baselines        |
| `docs/ROADMAP.md`       | Phased implementation plan                   |
| `config/config.example.yaml` | Configuration template                  |

## Legal

See `docs/ROE.md`. This system is for authorized training, research, and defensive spectrum monitoring only. Passive features are disabled by design in v1.
