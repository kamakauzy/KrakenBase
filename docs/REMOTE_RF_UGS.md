# KrakenBase – Remote RF UGS (camera-pole sidecar)

**Status:** design / post-v1 enhancement  
**Audience:** KrakenBase maintainers and operators building unmanned OPs  
**Sister docs:** [RFF_INTEGRATION.md](RFF_INTEGRATION.md), [ARCHITECTURE.md](ARCHITECTURE.md), [CONTRACTS.md](CONTRACTS.md), [ROE.md](ROE.md), [ROADMAP.md](ROADMAP.md)  
**Does not replace:** the base KrakenSDR array, Heimdall DOA, or `scripts/secondary_monitor.py` on a bench. This is the *outboard* half of hand-off: trees, driveway mouths, trail junctions.

---

## 0. One-sentence pitch

Hang a **sleeping RTL-SDR / RSP1B + tiny SBC** on the same stick as a grid-down IP camera. When PIR, camera motion, seismic, or an RF energy gate fires, grab a short I/Q burst, write SigMF locally, and ship an 80-byte event back over the link you already paid for. The base Kraken still owns bearings. The tree does not run MUSIC.

---

## 1. Why this exists

KrakenBase v1 assumes the secondary monitor is nearby: a laptop USB RTL watching `/var/lib/krakenbase/handoff`. That is correct for a patrol base. It is useless for an approach you will not walk every hour.

Civilian grid-down camera networks already solved the *pipe*:

- Cheap IP PTZ (Amcrest-class) on PoE  
- Ubiquiti NanoBeam as a directional "wireless Ethernet" (typically 5 GHz AirMax)  
- Prism / AirMax hub at the shop  
- RTSP into ATAK or a laptop  
- Battery / solar / Milwaukee adapters, no cell, no cloud  

Reference pattern (not a dependency, not an endorsement of their BOM): Dirty Civilian, *Grid-Down Camera Network for Unmanned Observation*, 2026-05-09, https://www.youtube.com/watch?v=EGrAjJPGJHY

They already said the camera is a **data pipe** and floated swapping it for other sensors. Trail cams lose because they are SD-card time machines or cell-tower snitches. This doc is the RF payload for that pipe.

What the camera cannot tell you:

- A radio keyed up behind the PIR cone  
- Same handheld as last Tuesday (`emitter_uid`) vs a new radio on a known GMRS channel  
- Cue for the *base* array when the PTZ is looking at a deer  

What you must not do: strap a KrakenSDR + 5-element UCA to a camo tripod and call it a UGS. That is a second base, not a sidecar.

---

## 2. Hard constraints

Same ROE as the rest of the project (`docs/ROE.md`), plus site physics:

1. **Passive RF only.** No probe pulses, no "active interrogation," no TX on the collector. The NanoBeam / Meshtastic already emit; do not add a third always-on radio if you can avoid it.
2. **Collector sleeps.** Wake on trigger or a short scheduled listen. `rtl_tcp` 24/7 across the backhaul is a failure mode.
3. **No DF on the tree.** No MUSIC/Capon on a Pi. Bearing comes from KrakenBase primary.
4. **One gallery per sensor class.** Remote RTL-v4 embeddings are not RSP1B embeddings and not Kraken CH0. See RFF doc §2–3.
5. **Metadata first, IQ second.** Default event is JSON. Raw bursts stay on the node unless `record_iq` / `retain_bursts` is on and the link can take it (it usually cannot).
6. **Reuse the existing backhaul.** Do not stand up a 2.4 GHz AP "for convenience."
7. **Audit.** Every wake, skip, burst, and uplink is an event with `node_id` + `source_event_id`.
8. **Config, not code.** Bands, gains, burst_ms, triggers, uplink path live in YAML.
9. **Legal.** Same as cameras: own land / authorized site / training AO. This is not a stalking kit.

`agent.md` still says avoid heavy ML on the primary. It is *more* true on a Zero 2 W. ONNX on a remote node is Phase U4, optional, RSP1B nodes only.

---

## 3. Roles vs what already exists

| Asset | Role | Not |
|-------|------|-----|
| KrakenSDR + laptop | Primary DF, baseline, alerts, hand-off publisher | A trail sensor |
| RSP1B at the *base* | Preferred RFF sensor (RFF doc) | Every tree |
| `secondary_monitor.py` | Local USB consumer of `HandOffTask` | Remote unattended node |
| Fleet registry (`fleet.db`) | Heartbeats, capabilities, ONLINE/OFFLINE | IQ store |
| Camera + NanoBeam pole | Eyes + IP pipe | Covert (5 GHz AirMax beacons) |
| **This sidecar** | Triggered I/Q + coarse detect + event uplink | Second Kraken |

Capability strings for `SecondaryNode.capabilities`:

- `rtl_sdr` — already implied  
- `ugs_rtl_v4` / `ugs_rtl_v3` / `ugs_rsp1b`  
- `ugs_camera` — shares pole with PTZ, can accept slew hints  
- `rff_embed` — only if a frozen ONNX is actually on that node  

Primary must not send `record_iq` + embed tasks to a node that only advertised `rtl_sdr`.

---

## 4. System view

```
                    ┌────────────────────────────────────────┐
                    │  Base (KrakenBase laptop)           │
                    │  Kraken UCA · Heimdall · SM         │
                    │  events.db · Meshtastic · ATAK/RR   │
                    └────────────────────────────┬──────────────────────┘
                                   │ HandOffTask / UgsEvent
                                   │ MQTT | file | IP | mesh
          ┌────────────────────────├───────────────────────┐
          │              5 GHz AirMax / LAN / mesh          │
          └─────────────┬─────────────────────┬───────────────┘
                       │                    │
              ┌────────├────────┐  ┌────────├────────┐
              │  UGS pole A     │  │  UGS pole B     │
              │  PTZ (optional) │  │  RF-only        │
              │  NanoBeam       │  │  NanoBeam/mesh  │
              │  Pi + RTL/RSP   │  │  Pi + RTL       │
              │  PIR / seismic  │  │  energy gate    │
              └─────────────────┘  └─────────────────┘
```

Happy path:

1. Base detects anomaly, DFs, publishes `HandOffTask` with `freq_hz` + optional `record_iq`.  
2. *Or* the pole self-triggers (PIR / energy) and emits `UgsEvent` first.  
3. Node wakes collector, tunes, captures `burst_ms`, writes sidecar JSON + optional SigMF.  
4. Node uplinks event only (default). IQ stays until pulled or a later window.  
5. Base fuses: camera clip + RF event + (if close enough) Kraken bearing.  
6. Collector sleeps. Array returns to SCANNING. Nobody waits on the Pi.

Self-trigger without a base task is allowed. That is how you catch a radio the camera never saw. Rate-limit it or the mesh becomes a toy.

---

## 5. Data models (additions)

Extend `docs/DATA_MODELS.md` / `models.py`. Keep Pydantic v2.

```python
class UgsTrigger(str, Enum):
    HANDOFF = "handoff"          # HandOffTask from primary
    CAMERA = "camera"            # Amcrest/ONVIF motion or alarm IO
    PIR = "pir"
    SEISMIC = "seismic"
    MAG = "mag"
    ENERGY = "energy"            # local rtl_power / threshold
    SCHEDULE = "schedule"        # short listen window
    MANUAL = "manual"

class UgsEvent(BaseModel):
    event_id: UUID
    node_id: str                 # fleet id, e.g. "ugs-west-gate"
    timestamp: datetime
    trigger: UgsTrigger
    freq_hz: int | None
    bandwidth_hz: int | None
    rssi_db: float | None
    snr_db: float | None
    duration_ms: int
    sensor_id: str               # "rtl-v4-0" | "rsp1b-0"
    recipe_id: str               # hash(rate, gain, bw, lna)
    burst_path: str | None       # local only unless retain + pull
    source_task_id: UUID | None  # HandOffTask if cued
    camera_id: str | None
    lat: float | None
    lon: float | None
    notes: str | None
```

Reuse, do not fork:

- `HandOffTask` — add `target_node_id: str | None` so the primary can pick a pole instead of "any USB RTL."  
- `RffCaptureTask` / `RffResult` — if the node has embed capability; same fields as RFF doc §5.  
- `SecondaryNode` — heartbeat + `current_freq_hz` + capabilities.

Uplink payload (keep under Meshtastic comfort if that path is used):

```
KB-UGS|west|462.7125|E|1.4s|A1B2
```

Full JSON on IP/MQTT. Scores and embeddings never on mesh.

---

## 6. Capture recipe

Identical discipline to RFF doc §6. Fingerprints die when gain changes.

**RTL-SDR v4 (default remote)**

- 2.4 MSPS CU8  
- Burst 20–100 ms after energy rise (or fixed window if cued to a freq)  
- Gain locked in YAML  
- Gallery name `rtl_v4` if you ever embed here  

**RSP1B (high-value poles only)**

- 2.048 or 2.4 MSPS, stay 14-bit  
- Same burst logic  
- Gallery `rsp1b` — never mix with RTL files  

**Scheduled listen**

- 1–3 s `rtl_power`-style sweep of configured bands every `listen_interval_s`  
- If a bin exceeds margin, promote to a burst  
- This is how you catch talk-only traffic with no PIR  

Format: SigMF (preferred) or `.cu8` + JSON sidecar with `source_event_id`, `recipe_id`, GPS if the pole has it.

Retention: default **metadata forever-ish** (events.db + node jsonl), **IQ days** via `system.retention_days`. Pull IQ over the 5 GHz link only on demand (`GET` from node or sneakernet SD).

---

## 7. Triggers (pick two, not seven)

| Trigger | Good for | Failure |
|---------|----------|---------|
| Camera / ONVIF alarm | People/vehicles in FOV | Misses radios off-axis; IR wash; fog |
| PIR | Warm movers | Animals; no RF context |
| Seismic / mag | Vehicles on a road | Foot traffic weak; setup craft |
| RF energy gate | Key-ups you cannot see | Birds on the squelch; needs a baseline |
| Hand-off from base | Known-interesting freq after DF | Useless if base is dark |
| Schedule | Pattern of life | Battery; more emissions if you uplink every miss |

Recommended default: **energy gate + camera OR**, hand-off as override. Seismic if the pole is a road.

GPIO / ONVIF mapping lives in config. Do not hard-code Amcrest model numbers in Python.

---

## 8. Backhaul (the part that gets you found)

The DC-style NanoBeam is **not covert**. 5 GHz AirMax is a persistent beacon. Anyone with a decent SDR and LOS can see a WISP dish. You accepted that when you hung the camera. Rules:

1. Collector does not add Wi-Fi, Bluetooth advertising, or a second 5 GHz radio.  
2. Prefer the existing NanoBeam for JSON events (bytes, not megabytes).  
3. Meshtastic for "something happened" when IP is down — same rate-limit / de-dupe as `alert.meshtastic`.  
4. No IQ over Meshtastic. Ever.  
5. Faraday / ferrite the USB dongle. RTL clock spurs are a tell.  
6. Scheduled listen should not also scheduled-*uplink* empty results.

If you need a quieter OP, drop the camera + NanoBeam and run RF-only + Meshtastic metadata. You lose live video. That is the trade.

---

## 9. Power budget (grid-down, not a lab PSU)

Order-of-magnitude, not a datasheet:

| Load | Draw | Duty |
|------|------|------|
| Amcrest-class PTZ + IR | 4–8 W | High when IR / PTZ moves |
| NanoBeam | 3–6 W | Always if the camera is live |
| Pi Zero 2 W idle | <1 W | Always if not HAT-slept |
| RTL-SDR | ~1 W | Burst / listen only |
| RSP1B | ~1 W | Burst / listen only |

The radio sidecar is cheap. The camera link is the hog. If the mission is RF-first, omit the PTZ and keep the Pi + dongle + mesh on a 20–40 Ah pack + small panel for days. If the mission is video-first, the RF add-on is rounding error — unless you leave `rtl_tcp` up.

Sleep the dongle between listens. A "smart" USB power switch is worth more than another neural net.

---

## 10. Config contract

Add `ugs:` to `config/config.example.yaml` (node-side image may use a stripped YAML).

```yaml
ugs:
  enabled: false
  node_id: "ugs-west-gate"
  sensor: "rtl_v4"                 # rtl_v4 | rtl_v3 | rsp1b
  sensor_id: "rtl-v4-0"
  sample_rate_hz: 2400000
  burst_ms: 40
  gain_db: 30                      # lock it
  min_snr_db: 6
  retain_bursts: false
  burst_dir: "/var/lib/krakenbase/ugs/bursts"
  listen_interval_s: 120           # 0 = no schedule
  listen_s: 2
  uplink: "ip"                     # ip | mqtt | mesh | file
  mqtt_topic: "krakenbase/ugs"
  triggers:
    handoff: true
    camera: true
    energy: true
    pir: false
    seismic: false
    schedule: true
  camera:
    onvif_host: "192.168.1.20"
    alarm_input: 1
  energy:
    margin_db: 12
    min_duration_ms: 80
    bands:
      - { name: "GMRS", start_hz: 462500000, stop_hz: 467700000, bin_hz: 12500 }
```

Primary `handoff.defaults` may include `target_node_id` and `prefer_ugs: true`.

If `ugs.enabled: true` on a node with no dongle → heartbeat `DEGRADED`, no crash, camera (if any) still works.

---

## 11. ATAK / Recon-Raven / mesh

- ATAK: CoT or video overlay already carries the camera. Add a point or sensor marker: freq, node_id, trigger, short id. Do not embed IQ.  
- `interop/recon_raven.py`: export `UgsEvent` as `kind=ugs` with tags `ugs:energy`, `node:ugs-west-gate`, `sensor:rtl-v4`.  
- Meshtastic: same compact grammar as alerts; de-dupe on `(node_id, freq_hz, window)`.  
- Camera slew (optional, later): if ONVIF PTZ is present, a high-confidence base DOA *near* that pole may send a bearing hint. That is not v1. Mis-slew is worse than no slew.

---

## 12. Suggested layout (when implemented)

```
src/krakenbase/ugs/
  __init__.py
  node.py            # remote daemon: triggers, capture, uplink, sleep
  energy.py          # local threshold / rtl_power wrapper
  onvif_trigger.py   # optional camera alarm
scripts/ugs_node.py  # entrypoint on the Pi
scripts/secondary_monitor.py   # keep; local USB remains valid
docs/REMOTE_RF_UGS.md
```

Do not drag ONNX into `ugs_node` by default. Optional extra `[ugs]` in pyproject: `numpy`, `onnxruntime` only if embed is compiled in.

`scripts/secondary_monitor.py` stays the dumb local consumer. `ugs_node.py` is the unattended cousin that can also *originate* events.

---

## 13. Implementation phases

### Phase U0 – Contracts (same day as R0)
- `UgsEvent`, `target_node_id` on `HandOffTask`, capabilities strings.  
- Tests: models round-trip; primary ignores UGS if `ugs.enabled` is false.

### Phase U1 – Bench node (real value)
- `scripts/ugs_node.py --synthetic-trigger` writes sidecar JSON + fake CU8.  
- GPIO or CLI trigger → burst with `rtl_sdr` if present.  
- File/MQTT uplink a `UgsEvent`. No wireless required.

### Phase U2 – Pole
- PoE split with the camera. ONVIF or dry-contact alarm → capture.  
- Events over the NanoBeam LAN to the shop.  
- Fleet heartbeat so OFFLINE is visible.

### Phase U3 – Base loop
- Primary `HandOffTask` can target `ugs-west-gate`.  
- Incoming `UgsEvent` can raise priority / set `record_iq` / cue a short Kraken dwell if the freq is in a monitored band.  
- ATAK / RR export.

### Phase U4 – Optional embed
- Only on RSP1B poles. Frozen ONNX from RFF R2. Same `recipe_id` rules.  
- Still no auto-promote.

Stop after U2 if you never train a net. A disciplined burst archive on the approaches is the product.

---

## 14. Tests that must exist

- UGS disabled: KrakenBase goldens unchanged.  
- No dongle: node heartbeats degraded, does not exception-loop.  
- Synthetic trigger produces valid `UgsEvent` JSON.  
- Hand-off with `target_node_id` is ignored by nodes that do not match.  
- Mesh-sized message stays short; IQ path is off by default.  
- Recipe_id mismatch refuses RFF fuse (shared with RFF tests).  
- Rate-limit: N energy events on the same freq in one window collapse to one uplink.

---

## 15. Failure modes

| Failure | Behavior |
|---------|----------|
| Dongle missing / USB flake | DEGRADED heartbeat; camera still up |
| NanoBeam down | Queue events locally; mesh if configured; drop IQ |
| PIR/animals | Rate-limit + require energy *or* duration; do not auto-alert mesh on PIR-only |
| Energy false alarm | Raise margin; do not "fix" with a bigger model first |
| Node stolen | No cloud account to dump. IQ default off. Rotate mesh keys like you should have already |
| Operator leaves `rtl_tcp` on | Battery and RF signature; treat as misconfig, log it |

---

## 16. What this is not

- Not a backpack Kraken.  
- Not C-UAS at 2.4 GHz (this kit's collectors top out ~1.7–2 GHz depending on dongle).  
- Not a substitute for a person in an OP. It is a force-multiplier so the person is not *on the X* for every driveway.  
- Not covert microwave. You already hung a 5 GHz dish.  
- Not automatic lethal cueing. Detect and notify. ROE stays human.

---

## 17. Operator SOP (short)

1. Build one pole with camera only. Confirm RTSP at the shop.  
2. Add Pi + RTL on the same PoE injector. `ugs.enabled: false` except for a bench trigger test.  
3. Fire a handheld in front of the camera. Confirm `UgsEvent` + optional CU8 on SD.  
4. Enable energy gate on *your* authorized bands only.  
5. Register `node_id` in fleet. Watch OFFLINE when you pull power.  
6. Only then point the primary hand-off at that node.  
7. If you change gain, cable, or dongle, new `recipe_id`. Start a new burst folder.

---

## 18. Roadmap mapping

- Phase 6 "secondary node fleet management" → these poles *are* the fleet.  
- RFF R1 capture path → U1/U2 is the remote implementation of that capture.  
- Recon-Raven export → `kind=ugs`.  
- Meshtastic alerts → same publisher, different prefix.

Bump `roe.version` only if uplink content or IQ-default policy changes. Design-only check-in does not.

---

## 19. References

- This repo: `ARCHITECTURE` §2.6–3, `SPEC` FR-30–32, `CONTRACTS` HandOffTask, `fleet/registry.py`, `scripts/secondary_monitor.py`, [RFF_INTEGRATION.md](RFF_INTEGRATION.md).  
- Dirty Civilian, *Grid-Down Camera Network for Unmanned Observation* (2026-05-09) — camera + NanoBeam + Prism + ATAK pattern.  
- Classic UGS: seismic/PIR wake → camera snapshot → sleep. RF burst is the same state machine with a dongle.

---

*If the pole cannot survive a night on the pack you already use for the camera, the RF addon is not the problem — the 5 GHz dish is. Sleep the collector anyway.*
