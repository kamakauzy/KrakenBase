# KrakenBase – Operational notes

Honest status. Design docs are not features.

## What is implemented

| Capability | Status |
|------------|--------|
| Adaptive DF loop | Yes |
| Tune confirm after task | Yes – DOA freq must match target within `tune_tolerance_hz` |
| Multi-band baselines | Yes – scope filter + per-band `bin_hz` |
| Anomaly re-arm | Yes – clears when quiet; `baseline.rearm_s` while still hot |
| Power history API | Yes – `/waterfall` from baseline EMA frames |
| Map LOB overlay | Yes – `/map/features` (needs `site.lat/lon`) |
| Heading fusion | Yes – wired into absolute bearing (DOA heading + optional NMEA) |
| Fleet registry | Yes – SQLite `data_dir/fleet.db` |
| Classification | Heuristic labels + known-emitter YAML. Not ML. |
| Recon-Raven export | Yes – `scripts/export_rr.py` |
| Meshtastic alerts | Yes – if radio/CLI works; otherwise **local log** (`channel=local`) |
| Secondary hand-off | Yes – **file default**; MQTT if `paho-mqtt` installed |
| RF fingerprint / remote UGS | **Design only** – see RFF + REMOTE_RF_UGS docs |
| Status UI | Partial – `web/index.html` + APIs. OSM tiles need network. |
| TX / probe / jam | **No** – `roe.allow_tx=true` refuses to start |

## What the baseline actually sees

Kraken RSSI of the **current VFO row(s)**, not a separate `rtl_power` sweep. If Heimdall is parked on one chunk, you only baseline that chunk. Do not brief "full-band scan" unless you add another sensor.

## Mesh honesty

- `channel=meshtastic` means the radio (or CLI) accepted the text.
- `channel=local` means it was logged here. Nobody on the mesh got it.
- Rate-limit returns `success=false`.

## Hand-off

`transport: mqtt` without `paho-mqtt` becomes file and logs a warning. Check `data_dir/handoff/`.

## API

- Default bind `127.0.0.1`.
- Set `status_api.token` if anything but localhost can reach the port. POST `/fleet/heartbeat` requires the token when set.

## Heading

Absolute bearing = relative DOA + fused offset. Stale GPS/compass falls back to `heading_offset_deg`. Measure the array.

## Interop

```bash
python scripts/export_rr.py --db /var/lib/krakenbase/events.db -o /tmp/kb_rr.jsonl --site patrol-base-01
```
