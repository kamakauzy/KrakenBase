# KrakenBase – Implementation Roadmap

## Phase 0 – Project Skeleton
- [x] Repository structure
- [x] agent.md, SPEC, ARCHITECTURE, CONTRACTS, ROE, DATA_MODELS, USER_GUIDE
- [x] Example + synthetic configuration
- [x] Python package layout + pyproject.toml / requirements.txt

## Phase 1 – Sensor Interface
- [x] Kraken client: parse `DOA_value.html` CSV → `DoaReading`
- [x] Health monitoring (last successful poll age)
- [x] Settings tasking (settings.json / middleware attempt)
- [x] Unit tests for CSV parsing
- [x] SyntheticKrakenClient for offline loop

## Phase 2 – Baseline + State Machine
- [x] Power baseline engine (warm-up + fire-once)
- [x] Adaptive state machine (scan → task → dwell → alert → hand-off → scan)
- [x] SQLite event store + state transition logging
- [x] Configuration loading (YAML + env)

## Phase 3 – Alerting & Observability
- [x] Meshtastic publisher (text alerts + local fallback)
- [x] Rate limiting / de-duplication
- [x] FastAPI `/health`, `/state`, `/events`
- [x] Structured logging

## Phase 4 – Hand-off
- [x] HandOffTask model + file/MQTT publisher
- [x] Secondary-node consumer script (`scripts/secondary_monitor.py`)
- [x] Audit of every hand-off

## Phase 5 – Hardening
- [x] Graceful degradation when Kraken disappears (DEGRADED + recover)
- [x] Array heading offset in config (optional GPS still open)
- [x] Event retention purge (`system.retention_days`)
- [x] Systemd unit + INSTALL.md for laptop deployment
- [x] End-to-end synthetic loop verified

## Phase 6 – Optional Enhancements (post-v1)
- Secondary node fleet management
- Richer classification hints
- Local web status page
- Integration with Recon-Raven event formats
- Multi-band parallel baseline tracking
- [x] Live GPS heading fusion (DOA heading + optional NMEA)
- [x] RF fingerprint / SEI integration **design** — [docs/RFF_INTEGRATION.md](RFF_INTEGRATION.md)
  - [x] R0 contracts + fuse stub (`NO_MODEL`)
  - [x] R1 RSP1B/RTL burst capture + SigMF (no ML required)
  - [x] R2 offline embed + gallery (`builtin_v0`; paper ONNX still not public)
  - [ ] R3 live async fuse into alerts / hand-off / RR export
  - [ ] R4 SNR/recipe gates + operator label API
- [x] Remote RF UGS sidecar **design** — [docs/REMOTE_RF_UGS.md](REMOTE_RF_UGS.md)
  - [x] U0 contracts (`UgsEvent`, `target_node_id`)
  - [x] U1 bench node + synthetic trigger + local burst
  - [x] U2 camera-pole / ONVIF + fleet heartbeat
  - [ ] U3 primary hand-off ↔ UGS event loop + ATAK/RR
  - [ ] U4 optional ONNX embed on RSP1B poles only

## Definition of Done – v0.1

A laptop running Ubuntu can:
1. Start the official Kraken stack **or** run `--synthetic`.
2. Start KrakenBase.
3. Detect a controlled / synthetic signal as an anomaly.
4. Task the array (or synth), obtain a bearing, log it, alert.
5. Optionally publish a hand-off task for a secondary monitor.
6. Automatically return to scanning.
7. Survive temporary disconnection from the Kraken process.

All of the above respects `docs/ROE.md`.
