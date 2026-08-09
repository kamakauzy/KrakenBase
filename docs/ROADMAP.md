# KrakenBase – Implementation Roadmap

## Phase 0 – Project Skeleton (current)
- [x] Repository structure
- [x] agent.md, SPEC, ARCHITECTURE, CONTRACTS, ROE, DATA_MODELS
- [x] Example configuration
- [ ] Basic Python package layout + pyproject.toml / requirements.txt

## Phase 1 – Sensor Interface (MVP foundation)
- [ ] Kraken client: parse `DOA_value.html` CSV → `DoaReading`
- [ ] Health monitoring (last successful poll age)
- [ ] Settings tasking (read/modify/upload settings.json or middleware)
- [ ] Unit tests for CSV parsing and bearing normalization

## Phase 2 – Baseline + State Machine
- [ ] Simple power baseline engine (start with one band or synthetic input)
- [ ] Adaptive state machine implementing the core loop
- [ ] SQLite event store + state transition logging
- [ ] Configuration loading (YAML + env)

## Phase 3 – Alerting & Observability
- [ ] Meshtastic publisher (text alerts)
- [ ] Rate limiting / de-duplication
- [ ] Minimal FastAPI status endpoints (`/health`, `/state`, `/events`)
- [ ] Structured logging

## Phase 4 – Hand-off
- [ ] HandOffTask model and publisher (MQTT or simple HTTP/UDP)
- [ ] Example secondary-node consumer script (RTL-SDR lock + record)
- [ ] Audit of every hand-off

## Phase 5 – Hardening
- [ ] Graceful degradation when Kraken disappears
- [ ] Array heading fusion (config offset + optional GPS)
- [ ] Retention policies for events and any short recordings
- [ ] Systemd unit + install notes for laptop deployment
- [ ] End-to-end test with real or simulated Kraken output

## Phase 6 – Optional Enhancements (post-v1)
- Secondary node fleet management
- Richer classification hints
- Local web status page
- Integration with existing Recon-Raven event formats for interoperability
- Multi-band parallel baseline tracking

## Definition of Done – v0.1

A laptop running Ubuntu can:
1. Start the official Kraken stack.
2. Start KrakenBase.
3. Detect a controlled test signal as an anomaly.
4. Task the Kraken, obtain a bearing, log it, and send a Meshtastic alert.
5. Automatically return to scanning.
6. Survive temporary disconnection from the Kraken process.

All of the above must respect the ROE document.
