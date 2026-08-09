# KrakenBase – Product Specification

## 1. Vision

A fixed-site coherent SIGINT node that continuously monitors tactical bands, detects deviations from an established baseline, performs short coherent direction-finding dwells with a KrakenSDR array, alerts operators (via mesh or local channels), and hands interesting frequencies to secondary RTL-SDR monitors for persistent collection.

Primary use cases: patrol base, training compound, permanent spectrum awareness site, defensive monitoring.

## 2. Functional Requirements

### 2.1 Scanning & Baseline
- FR-01: Continuously or periodically measure power across configured frequency ranges (VHF/UHF/ISM tactical bands).
- FR-02: Maintain a rolling statistical baseline (mean, std, or percentile) per frequency bin or channel.
- FR-03: Detect anomalies when current power exceeds baseline by a configurable margin for a configurable duration.
- FR-04: Support both wideband power scanning and Kraken-native spectrum awareness.

### 2.2 Coherent DF
- FR-10: On anomaly, task the KrakenSDR (via settings.json or middleware) to park a VFO on the frequency of interest.
- FR-11: Collect DOA result (bearing, confidence, RSSI, timestamp) from the official Kraken output.
- FR-12: Support short configurable dwell times (default 1–5 s).
- FR-13: Fuse array-relative bearing with configured or GPS-derived array heading to produce absolute bearing when possible.
- FR-14: Always release the VFO and return to scan mode after dwell (or on timeout / low confidence).

### 2.3 Alerting
- FR-20: Emit structured local events for every high-confidence DF result.
- FR-21: Send compact human-readable alerts over Meshtastic (frequency, bearing, confidence, short ID).
- FR-22: Support rate limiting and de-duplication so the mesh is not flooded.
- FR-23: Log every alert with full context for audit.

### 2.4 Frequency Hand-off
- FR-30: Publish a tasking message containing frequency, optional modulation hint, priority, and max dwell time.
- FR-31: Secondary nodes (simple RTL-SDR + software) can consume the task and begin monitoring/recording.
- FR-32: Hand-off is best-effort; primary does not block on secondary acknowledgment in v1.

### 2.5 Health & Observability
- FR-40: Continuously monitor Kraken connectivity and DOA data freshness.
- FR-41: Expose a simple status API (health, current state, last anomaly, last bearing).
- FR-42: Structured logging of all state transitions and decisions.

## 3. Non-Functional Requirements

- NFR-01: Passive only. No RF transmission capability in v1.
- NFR-02: Must run on a single Ubuntu laptop with KrakenSDR attached.
- NFR-03: Survive temporary loss of Kraken (enter degraded SCANNING or FAULT state, recover automatically).
- NFR-04: Configuration via YAML + environment variables. No hard-coded operational parameters.
- NFR-05: All significant actions must be auditable (who/what/when/why).
- NFR-06: Resource-conscious – prefer low CPU when scanning; higher CPU only during short DF dwells.
- NFR-07: Battery-friendly operation is desirable but not at the expense of reliability.

## 4. Explicit Non-Goals (v1)

- Mobile / backpack operation and power optimization.
- Multi-Kraken array networks.
- Real-time speech-to-text transcription on the primary node.
- Active electronic attack or any form of transmission.
- Full web dashboard with live waterfall (status API is sufficient).
- Automatic promotion of emitters into a permanent “known good” database without operator review.

## 5. Success Criteria for v0.1 MVP

- Laptop can run official Kraken stack + KrakenBase side-by-side.
- Anomaly on a test signal triggers a DF dwell and produces a logged bearing.
- Meshtastic alert is sent for high-confidence results.
- System returns to scanning without manual intervention.
- Configuration and ROE files are present and enforced.
