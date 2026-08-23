# KrakenBase – User / Operator Guide

**Audience:** You. Laptop + KrakenSDR (or synthetic mode). No ceremony.

## What this is

Fixed-site coherent SIGINT node. It:

1. Watches spectrum / DOA output  
2. Builds a power baseline  
3. On sustained anomaly → short coherent DF dwell  
4. Alerts (Meshtastic or local log)  
5. Optionally hands the frequency to a secondary RTL-SDR monitor  
6. **Always** returns the array to scan  

Passive only. No TX in v1.

## Two ways to run

### A. Synthetic (no hardware)

```bash
git clone https://github.com/kamakauzy/KrakenBase.git
cd KrakenBase
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m krakenbase.main --synthetic
# or
python -m krakenbase.main -c config/config.synthetic.yaml
```

Expect a full cycle every ~20–30s: anomaly → task → dwell → alert → back to scan.  
Status: `http://127.0.0.1:8090/health`  
Events DB: `/tmp/krakenbase/events.db` (synthetic default)

### B. Live KrakenSDR

1. Start the official Kraken stack (Heimdall + krakensdr_doa) so `DOA_value.html` is on port 8081.  
2. Copy and edit config:

```bash
cp config/config.example.yaml config.yaml
# edit: array.heading_offset_deg, bands, meshtastic interface, data_dir
```

3. Run:

```bash
python -m krakenbase.main -c config.yaml
```

## Config that actually matters

| Key | Why |
|-----|-----|
| `array.heading_offset_deg` | Element 0 vs true north. Wrong = wrong absolute bearings. |
| `array.radius_m` | Measure it. Do not guess. |
| `kraken.min_confidence` | Below this → log only, no alert/hand-off. |
| `baseline.anomaly_margin_db` | How far above baseline counts as interesting. |
| `baseline.min_anomaly_duration_s` | Sustained time before we DF. |
| `baseline.rearm_s` | Same bin will not re-alert until quiet or this cooldown. |
| `dwell.default_s` / `max_s` / `settle_s` | How long to park the array. Keep short. |
| `status_api.token` | Required on POSTs if set. Leave empty only on localhost. |
| `alert.meshtastic.*` | Radio path + rate limit. |
| `handoff.enabled` | Secondary monitor tasking. |

All thresholds live in config. No magic numbers in code.

## Status API

```bash
curl -s http://127.0.0.1:8090/health | jq
curl -s http://127.0.0.1:8090/state | jq
curl -s 'http://127.0.0.1:8090/events?limit=20' | jq
curl -s 'http://127.0.0.1:8090/events?type=doa&limit=10' | jq
curl -s http://127.0.0.1:8090/waterfall | jq
curl -s 'http://127.0.0.1:8090/map/features?limit=20' | jq
```

`/health` → `ok` | `degraded` | `fault`  
`kraken_age_s` should stay low when the DOA process is alive.

## Expected state flow

```
INIT → SCANNING → (anomaly) → TASKING → DWELLING → PROCESSING
     → ALERTING → HANDING_OFF → SCANNING
```

If Kraken goes silent > ~10s → `DEGRADED`. Repeated failed recoveries → `FAULT`. Recovers when DOA returns.

## Array setup (live)

1. UCA preferred, elements in configured order.  
2. Measure radius to phase center, put it in `array.radius_m`.  
3. Sight element 0 to a known azimuth; set `heading_offset_deg`.  
4. Let Kraken finish its own calibration before trusting bearings.  
5. Start KrakenBase after DOA is producing CSV on 8081.

## Meshtastic

- Set `alert.meshtastic.interface` to your serial device (or TCP).  
- Rate limit defaults to 60s per frequency — do not turn this off in the field.  
- Alert format: `KB|<MHz>|<bearing>°|<conf>|<id>`  
- If the radio is missing, alerts fall back to local log (`channel=local`) and still get audited.

## Secondary hand-off

When `handoff.enabled: true`, each high-confidence DOA can publish a task.

**File transport (default):**

```yaml
handoff:
  enabled: true
  transport: file
  # tasks written under data_dir/handoff/
```

Run the consumer on another box (or the same laptop with an RTL-SDR):

```bash
python scripts/secondary_monitor.py --watch /var/lib/krakenbase/handoff
# or with MQTT:
python scripts/secondary_monitor.py --mqtt 127.0.0.1 --topic krakenbase/handoff
```

The stub logs the task and, if `rtl_sdr` / `rtl_fm` is present, can lock and record. It does not need the Kraken array.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Stuck in DEGRADED / FAULT | Is krakensdr_doa up? `curl localhost:8081/DOA_value.html` |
| No anomalies ever | Baseline still warming, or margin too high, or bands wrong |
| Alerts spam | Raise `rate_limit_s`; confirm confidence gate |
| Bad bearings | `heading_offset_deg`, array radius, Kraken calibration |
| Port 8090 in use | Change `status_api.port` in config |
| Permission on data_dir | Point `system.data_dir` somewhere writable |
| Tune not confirmed | Tasking POST did not move the VFO; check Kraken control path |

## ROE (short)

- No transmit paths. `allow_tx=true` will not start.  
- Audit DF, alerts, and hand-offs.  
- Confidence gate before action.  
- Always return to scan after dwell.  
- Config over hard-coding.

Full rules: `docs/ROE.md`.

## Tests

```bash
pip install -e ".[dev]"
pytest -v
```

## What is not in v0.1

- RF fingerprint / remote UGS (design docs only)  
- Multi-Kraken networks  
- Learned emitter models  
- Any TX / EA capability  

Those stay out of scope until you explicitly expand ROE and design.
