# KrakenBase – AI Agent Instructions

You are implementing **KrakenBase**, a fixed-site coherent SIGINT platform.

## Project Identity

- **Name**: KrakenBase  
- **Purpose**: Adaptive spectrum monitoring + coherent DF on a KrakenSDR array for permanent / patrol-base use  
- **Host**: Laptop running Ubuntu (preferred) or other x86 Linux  
- **Sensor**: KrakenSDR 5-channel coherent receiver (Heimdall DAQ + krakensdr_doa)  
- **Philosophy**: Fewer moving parts, clear ROE, passive-first, clean frequency hand-off to secondary monitors  

## Non-Negotiable Constraints

1. **Passive only in v1**  
   - No transmit code paths, no HackRF TX, no jamming, no active probing.  
   - Any future TX must be behind explicit multi-gate ROE controls and is out of scope for initial implementation.

2. **Legal & ROE first**  
   - Every significant action (DF dwell, alert, hand-off) must be logged with timestamp, operator context, and reason.  
   - Default configuration must be defensive / training oriented.

3. **Borrow, do not copy blindly**  
   - Re-use patterns and proven code from:  
     - `kamakauzy/sigint-field-kit` (kraken_doa_collector, emitter_locator, adaptive scripts, baseline logic)  
     - `kamakauzy/Recon-Raven` (event model, FastAPI structure, DF solver ideas, config patterns)  
   - Do **not** import the full mobile/backpack complexity, multi-SDR orchestration, or TX safety gates from Recon-Raven.

4. **Kraken is the source of truth for coherent bearings**  
   - Prefer the official DOA output (`DOA_value.html` CSV or settings.json control).  
   - Do not re-implement MUSIC/Capon unless there is a very strong reason.

5. **Single primary box preferred**  
   - Everything runs on the laptop when possible.  
   - Secondary RTL-SDR nodes are optional consumers of hand-off tasks.

## Preferred Tech Stack

- Python 3.11+  
- FastAPI (lightweight control & status API)  
- SQLite / aiosqlite (event store)  
- httpx / aiohttp (Kraken polling & control)  
- Pydantic v2 (all schemas)  
- APScheduler or simple asyncio loops for the adaptive cycle  
- Meshtastic Python library for alerts  
- YAML config  

Avoid heavy ML frameworks in v1 unless classification is strictly required.

## Core State Machine (must implement)

```
SCANNING
  ↓ anomaly detected (baseline deviation)
TASKING_KRAKEN
  ↓ VFO parked, short dwell
COLLECTING_DOA
  ↓ bearing + confidence received
ALERTING + HANDOFF
  ↓ mesh alert sent, secondary tasked (if available)
RETURNING_TO_SCAN
  ↓
SCANNING
```

Keep dwell times short (1–5 s configurable). Always return the array to scan.

## Coding Standards for Agents

- Prefer small, focused modules over god classes.  
- Every external interface (Kraken, Meshtastic, secondary nodes) must have a clear contract in `docs/CONTRACTS.md`.  
- Use type hints and Pydantic models everywhere data crosses a boundary.  
- Logging must be structured and include `event_id` correlation where possible.  
- Configuration must be externalized (YAML + env overrides).  
- Write tests for the state machine and for Kraken data parsing.  
- Never hard-code frequencies, gains, or confidence thresholds.

## What “Done” Looks Like for v0.1

- Can start Heimdall + krakensdr_doa on the laptop.  
- KrakenBase service polls DOA output and maintains a simple power baseline.  
- On threshold breach it tasks a VFO, collects a bearing, logs the event, and emits a Meshtastic text alert.  
- Returns to scanning automatically.  
- All actions audited.  
- Config driven.  
- Clear separation between sensor interface and decision logic.

## Forbidden

- Adding transmit capability.  
- Silent failure on Kraken disconnect (must surface health status).  
- Spamming the mesh with low-confidence or duplicate alerts.  
- Storing raw IQ indefinitely without explicit operator action.  
- Assuming the antenna array heading is always 0° without configuration.

When in doubt, prefer the simpler, more auditable, more passive solution.
