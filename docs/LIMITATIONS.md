# KrakenBase – Operational notes

## What is implemented

| Capability | Status |
|------------|--------|
| Adaptive DF loop | Yes |
| Multi-band baselines (per-band bin_hz, scope filter) | Yes |
| Scrolling power waterfall UI (`/waterfall` + `/`) | Yes – power-history heatmap |
| GPS / compass heading fusion | Yes – DOA CSV + optional NMEA file |
| Fleet registry | Yes – SQLite persistent `data_dir/fleet.db` |
| Classification | Yes – heuristic labels + known-emitter YAML |
| Recon-Raven export | Yes – `scripts/export_rr.py` JSONL bridge |
| Meshtastic alerts | Yes – local fallback |
| Secondary hand-off | Yes – file / MQTT + consumer |
| TX | **No** – ROE hard off |

## Power waterfall vs IQ FFT

- `/waterfall` returns time-ordered frames of per-bin EMA power from the baseline engine.
- That is a real scrolling heatmap of what KrakenBase uses for anomaly decisions.
- Side-by-side with Kraken App if you need Heimdall IQ spectrograms.

## Heading

- Absolute bearing = relative DOA + fused offset.
- Fresh compass from DOA beats GPS track; both beat static `heading_offset_deg`.
- Set `array.nmea_path` to a NMEA dump file (`$HDT` / `$HDG` / `$RMC`) when available.

## Fleet

- Heartbeats persist across restarts in SQLite.
- Nodes older than ~90s without heartbeat mark OFFLINE.

## Interop

```bash
python scripts/export_rr.py --db /var/lib/krakenbase/events.db -o /tmp/kb_rr.jsonl --site patrol-base-01
```

Bridge fields: `id`, `ts`, `kind`, `site`, `freq_hz`, `bearing_deg`, `confidence`, `power_db`, `tags[]`, `source=krakenbase`.
