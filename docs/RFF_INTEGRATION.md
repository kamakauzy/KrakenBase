# KrakenBase – RF Fingerprint / SEI Integration

**Status:** design / post-v1 enhancement  
**Audience:** KrakenBase maintainers and DARC / patrol-base operators  
**Depends on:** `docs/ARCHITECTURE.md`, `docs/SPEC.md`, `docs/CONTRACTS.md`, `docs/DATA_MODELS.md`, `docs/ROE.md`, `docs/ROADMAP.md` Phase 6  
**Does not replace:** Kraken MUSIC bearings. RFF is a *label and association* layer, not a second DF solver.

---

## 0. One-sentence pitch

After a high-confidence DF dwell, a **separate receive chain** (SDRPlay RSP1B preferred; RTL-SDR v4 only if that is all you have) captures a short I/Q burst, embeds it with a **frozen, offline ONNX model**, and answers: *have we seen this hardware before, on this sensor, at this site?*

That answer is fused onto the existing `DoaEvent` / `HandOffTask` / Recon-Raven export. The array still always returns to scan.

---

## 1. Why this exists (and what is already broken)

KrakenBase v1 classification is honest about being dumb:

- `EmitterClassifier` is **heuristic**: duration, margin_dB, band name, YAML frequency match (`known_emitters*.yaml`).
- `KNOWN` means "this channel is in a list," not "this radio is the same physical transmitter as last Tuesday."
- Two different Baofengs on 462.550 look identical to the classifier. A repeater and a handheld on the same pair look identical.
- SPEC §4 already forbids automatic promotion of emitters into a permanent known-good database without operator review. That rule stays.

RFF / specific emitter identification (SEI) and emitter data association (EDA) are the missing layer for:

- Pattern-of-life: same emitter, new bearing or time.
- De-duplication: don't mesh-spam every key-up of the same radio.
- Hand-off priority: raise `record_iq` and dwell when the embedding is *new*.
- Recon-Raven interop: a stable `emitter_uid` instead of only `freq_hz`.

Reference concept (not a dependency): Hiles & Ahmad, BAE Systems Digital Intelligence, *A Generic Machine Learning Framework for Radio Frequency Fingerprinting*, arXiv:2510.09775 (Dec 2025). Framework only. No public weights. We reimplement the *task split* (embed → match / cluster / open-set), not their proprietary DMR/AIS/drone sets.

---

## 2. Hard constraints (ROE + architecture)

These are non-negotiable and match `docs/ROE.md` + `agent.md`:

1. **Passive only.** No TX, no probe pulses, no "active fingerprint interrogation."
2. **Kraken remains the bearing source of truth.** Do not reimplement MUSIC. Do not stall the state machine on inference.
3. **Do not fingerprint across radios.** One gallery per physical sensor class. RSP1B embeddings are not comparable to Kraken CH0 or RTL-SDR v4 embeddings.
4. **No silent auto-promote.** New clusters stay `UNKNOWN` / `rff_new` until an operator names them in YAML or a review queue.
5. **Config, not code.** Model path, sample rate, burst length, thresholds, which SDR is the RFF sensor — all YAML.
6. **Audit.** Every embed, match, reject, and gallery write is an event with `event_id` correlation to the triggering `DoaEvent`.
7. **Always return to scan.** RFF capture happens on the *secondary* chain or a short post-dwell slice. The UCA is not held for a 30-second neural net party.
8. **Default: do not keep raw IQ.** Burst files are ephemeral unless `handoff.defaults.record_iq` or `rff.retain_bursts` is explicitly on, with retention days.
9. **Offline-first.** Inference is ONNX Runtime (CPU). No cloud. Training is a laptop job *before* the site goes dark.

`agent.md` said "avoid heavy ML in v1." This is Phase 6. Keep PyTorch out of the runtime path. Train elsewhere; ship `.onnx` + a gallery file.

---

## 3. Hardware roles on *this* kit

KrakenBase today: KrakenSDR UCA + laptop + optional GPS + Meshtastic + secondary RTL-SDR.

Operator kit in scope: **Kraken array + SDRPlay RSP1B + RTL-SDR v3/v4 + Raspberry Pi and/or laptop.**

| Asset | KrakenBase job | RFF job | Do not use for |
|-------|----------------|---------|----------------|
| KrakenSDR (5× 8-bit, 24–1766 MHz, ≤2.56 MHz) | Coherent DF, VFO dwell, optional power baseline | Optional *cue only* (best-element IQ after Heimdall cal) | Primary SEI gallery. 8-bit + retune/cal cycles poison fingerprints. |
| Laptop (Ubuntu) | Heimdall + `krakensdr_doa` + KrakenBase brain | Train embeddings; run ONNX; hold gallery SQLite | Running 5ch IQ record + training + DF UI until the fans file a grievance |
| Raspberry Pi 4/5 | Optional Kraken DAQ host (official image) **or** secondary node | Light ONNX *if* the laptop is dark | Same box as 5ch @ 2.4 MSPS *and* embedding |
| SDRPlay RSP1B (14-bit @ ≤~6 MSPS, 1 kHz–2 GHz) | New: **RFF sensor** | Primary I/Q for embed/match | Pretending it shares a gallery with RTL/Kraken |
| RTL-SDR v4 | Secondary monitor (`scripts/secondary_monitor.py`) | Fallback RFF sensor, separate gallery `rtl_v4` | Mixing v3 and v4 in one model |
| RTL-SDR v3 | Spare / dedicated band watch | Last-resort gallery `rtl_v3` | HF comparison vs v4 without a dedicated model |

**Coverage hole (brief it, don't hide it):** this kit dies at ~1.77–2.0 GHz. 2.4 / 5.8 GHz Wi-Fi drone C2 is out. DMR / GMRS / VHF air / AIS-class / many tactical UHF problems are in.

**Power (grid-down):** Kraken ~11 W + host 10–25 W is the budget hog. RSP1B is ~1 W. Keep RFF on the cheap radio so the array can sleep in SCANNING.

---

## 4. Where it plugs into the existing loop

Current happy path (`ARCHITECTURE.md` §3):

```
SCANNING → anomaly → TASKING → DWELLING → PROCESSING
        → ALERTING → HANDING_OFF → SCANNING
```

RFF is a **side path after PROCESSING**, never a new blocking state on the array:

```
PROCESSING
  ├─ existing: pick best DoA, classify heuristic
  ├─ NEW (async, non-blocking):
  │     if doa.confidence >= kraken.min_confidence
  │        publish RffCaptureTask {freq, event_id, bearing, rssi}
  │        secondary / local RSP1B: record N ms I/Q (fixed recipe)
  │        slice burst → ONNX embed → gallery query
  │        write RffResult onto DoaEvent + events.db
  └─ ALERTING / HANDING_OFF use fused labels
```

If the RSP1B is busy or missing, DF + heuristic classification still fire. RFF is best-effort, same philosophy as Meshtastic and secondary nodes.

### Insertion points in code (do not god-class this)

| Module | Change |
|--------|--------|
| `models.py` | Add `RffCaptureTask`, `RffResult`, `RffHit`, extend `ClassificationLabel`, extend `HandOffTask` |
| `core/classifier.py` | Keep heuristics. Add `fuse(heuristic, rff) → ClassificationResult` |
| `core/state_machine.py` | After successful DOA, fire-and-forget capture task. Do not await embed. |
| `handoff/publisher.py` | Copy `rff_*` fields onto hand-off JSON; set `record_iq=true` when `rff_status=new` |
| `scripts/secondary_monitor.py` | RSP1B / Soapy path; write SigMF or CU8+sidecar; optional local embed |
| `interop/recon_raven.py` | Export `emitter_uid`, `rff_score`, `rff_status` as tags |
| `config/*.yaml` | New `rff:` section |
| `store/events.py` | Persist type `rff` |
| `api/app.py` | `GET /rff/gallery`, `POST /rff/label` (operator name), health includes model loaded? |
| `tests/` | Fake embeddings, fusion rules, "no model → degrade cleanly" |

Heimdall / `krakensdr_doa` stay unmodified black boxes (`ARCHITECTURE.md` §2.1).

---

## 5. Data models (additions)

Extend `docs/DATA_MODELS.md`. Proposed Pydantic:

```python
class RffStatus(str, Enum):
    MATCH = "match"          # cosine >= match_threshold to named or stable cluster
    LIKELY = "likely"        # between likely and match
    NEW = "new"              # below new_threshold; open-set
    LOW_SNR = "low_snr"
    SENSOR_MISMATCH = "sensor_mismatch"
    NO_MODEL = "no_model"
    SKIPPED = "skipped"

class RffCaptureTask(BaseModel):
    task_id: UUID
    source_event_id: UUID          # DoaEvent
    freq_hz: int
    sample_rate_hz: int            # from config, not guessed
    burst_ms: int
    sensor_id: str                 # "rsp1b-0" | "rtl-v4-0" | "kraken-ch0"
    recipe_id: str                 # hash of rate/bw/gain/LNA so you cannot mix recipes
    created_at: datetime

class RffHit(BaseModel):
    gallery_id: str
    name: str | None               # None until operator labels
    score: float                   # cosine similarity
    last_seen: datetime | None
    n_obs: int = 0

class RffResult(BaseModel):
    event_id: UUID
    source_event_id: UUID
    sensor_id: str
    recipe_id: str
    model_id: str                  # onnx filename + hash
    status: RffStatus
    embedding_dim: int
    top_hits: list[RffHit]
    emitter_uid: str | None        # stable local ID, e.g. "e_7f3a"
    snr_db: float | None
    burst_path: str | None         # only if retain_bursts
    notes: str | None
```

`ClassificationLabel` additions (do not overload `KNOWN`):

- `RFF_MATCH` — hardware-consistent with a labeled gallery entry  
- `RFF_NEW` — open-set / new cluster  
- `RFF_REPEAT` — unlabeled but seen before (association without a name)

Heuristic `KNOWN` remains "frequency in YAML." Fusion example:

- YAML known + RFF new on that channel → alert text: `known-channel, new-radio` (this is the whole point).
- YAML unknown + RFF match to `e_7f3a` → treat as repeat emitter even if the freq drifted inside tolerance.

`HandOffTask` extra fields:

```python
emitter_uid: str | None = None
rff_status: str | None = None
rff_score: float | None = None
sensor_id: str | None = None
```

When `rff_status == new`, default `record_iq` to true *if* config allows, so the secondary keeps evidence.

---

## 6. Capture recipe (the part people skip and then cry)

Fingerprints die when the recipe changes. Lock it per `sensor_id`.

**RSP1B (preferred)**

- Sample rate: **2.048 or 2.4 MSPS** (stay in 14-bit territory; do not chase 10 MHz and collapse to 8-bit).
- IF BW: narrowest that still holds the emission (200–600 kHz for NFM/DMR-class; wider only if the signal is wider).
- Gain / LNA / GR: **fixed per site**, written into `recipe_id`.
- Burst: energy gate → **10–50 ms** after rise, or a known preamble window if you have one. Not "record 30 s of FM and hope."
- Format: CS16 or CU8 + **SigMF** (freq, rate, gain, sensor serial, `source_event_id`).
- Antenna: dedicated or a *hard-switched* copy of one Kraken element. Same cable every time.

**RTL-SDR v4 fallback**

- 2.4 MSPS CU8, same burst logic, gallery name `rtl_v4`. Accept worse quantization.

**Kraken CH0**

- Only if Heimdall IQ is already flowing and you accept 8-bit + coherence-cal artifacts. Gallery name `kraken-ch0`. Do not mix with RSP1B.

Never train one model on mixed files from those three.

---

## 7. Model / inference (offline combat, not a research cluster)

**Train (laptop, pre-mission)**

1. Collect labeled bursts from *your* radios on the *RFF sensor* across range, time of day, and at least two headings if possible.
2. Small 1-D CNN or FCN on raw I/Q (or short STFT). Siamese / prototype head is better than 8-way softmax — you will not have PLAN serial numbers.
3. Export ONNX. Target: few MB, CPU ONNX Runtime.
4. Optional public warm-start data (Pluto indoor OFDM set, ORACLE, etc.) is **not** your gallery. Fine-tune or discard.

**Infer (site)**

- Load ONNX once at process start.
- Burst → float32 I/Q (normalize per recipe) → embedding vector (e.g. 64–128 dim).
- Cosine kNN against gallery (sqlite + numpy is enough; FAISS later if you actually get thousands of emitters).
- Thresholds in YAML: `match`, `likely`, `new`.
- Open-set: below `new` → create unlabeled cluster after N repeats (config `min_obs_to_cluster`, default 3).

**Pi vs laptop**

- Laptop: train + default infer.
- Pi: infer-only ONNX if the secondary node owns the RSP1B. Do not train on the Pi.

Related public edge evidence (not this repo): quantized TFLite RFF on Pi-class CPUs in the sub-millisecond to tens-of-ms range. A 20 MB Siamese is already "fits." Latency is not the hard problem. Domain shift is.

---

## 8. Config contract (`rff:` section)

Add to `config/config.example.yaml`:

```yaml
rff:
  enabled: false                 # off until a model + sensor exist
  sensor: "rsp1b"                # rsp1b | rtl_v4 | rtl_v3 | kraken_ch0
  sensor_id: "rsp1b-0"
  soapy_driver: "sdrplay"        # or rtlsdr
  sample_rate_hz: 2048000
  burst_ms: 20
  gain_db: 20                    # lock it
  model_path: "/var/lib/krakenbase/rff/embed.onnx"
  gallery_path: "/var/lib/krakenbase/rff/gallery.sqlite"
  match_threshold: 0.82
  likely_threshold: 0.70
  new_threshold: 0.55
  min_obs_to_cluster: 3
  min_snr_db: 8
  retain_bursts: false
  burst_dir: "/var/lib/krakenbase/rff/bursts"
  timeout_ms: 400                # if embed not back, DF continues
  fuse_into_alerts: true
```

If `enabled: true` and model missing → `NO_MODEL`, health `degraded` for RFF only, DF loop unaffected.

---

## 9. Alert and mesh format

Keep Meshtastic short (`CONTRACTS.md` §4). Optional extra token when RFF is on:

```
KB|462.7125|142°|87|e7f3a|M
```

- `e7f3a` = `emitter_uid` prefix  
- `M` match / `N` new / `R` repeat unlabeled / omit if skipped  

Do not put scores on the mesh. Full `RffResult` stays in SQLite.

De-dupe window should key on **`(emitter_uid or freq) + time`**, not freq alone, once RFF is trusted. Until then, keep freq de-dupe so a bad model cannot silence a new radio on a known channel.

---

## 10. Recon-Raven / fleet

`interop/recon_raven.py` already lifts classification labels into `tags[]`. Add:

```python
"emitter_uid": payload.get("emitter_uid"),
"rff_status": payload.get("rff_status"),
"rff_score": payload.get("rff_score"),
```

and tags `rff:match`, `rff:new`, `rff:repeat`, `sensor:rsp1b-0`.

Fleet secondary nodes (`SecondaryNode.capabilities`) should advertise `rff_rsp1b` or `rff_rtl` so the primary does not send capture tasks to a node that can only `rtl_fm`.

---

## 11. Implementation phases (do not boil the ocean)

### Phase R0 – Contracts only (1 day)
- Models + YAML + event type `rff`.
- Classifier fuse() with a **stub** RffResult (`NO_MODEL`).
- Tests: heuristic unchanged when RFF off.

### Phase R1 – Capture path (real value even without ML)
- Extend `secondary_monitor.py`: `--rsp1b` / Soapy, write `task_id_freq.cs16` + json sidecar / SigMF.
- Flip `record_iq` from hand-off when config says so.
- Retention job respects `system.retention_days`.
- This alone makes later training possible.

### Phase R2 – Offline embed + gallery
- `scripts/rff_train.py` (laptop, optional extra deps in `pyproject` extra `[rff]`).
- `scripts/rff_embed.py` scores a directory of bursts.
- Gallery sqlite: `emitter_uid`, name, vector blob, sensor_id, recipe_id, n_obs.

### Phase R3 – Live fuse
- Async worker on laptop or secondary: consume capture → embed → store → patch latest DoaEvent.
- Alerts include uid when available.
- `POST /rff/label` for operator naming. No auto-promote.

### Phase R4 – Site hardening
- SNR gate, recipe_id mismatch → `SENSOR_MISMATCH`.
- Synthetic client emits fake embeddings for CI.
- Document collect SOP in `docs/USER_GUIDE.md`.

Stop after R1 if the model work is not funded. A disciplined burst archive is worth more than a 91% paper number trained on someone else's LimeSDR.

---

## 12. Tests that must exist

- RFF disabled: state machine + classifier goldens unchanged.
- Model file absent: status `NO_MODEL`, no exception, DF still alerts.
- Recipe_id mismatch: reject embed, do not write a false match.
- Fusion: YAML known + RFF new → both labels present; alert not suppressed.
- Thresholds: scores on either side of `match_threshold`.
- Hand-off JSON includes `emitter_uid` when present.
- `secondary_monitor` dry-run does not require hardware (`--synthetic-burst`).

---

## 13. Failure modes

| Failure | Behavior |
|---------|----------|
| No RSP1B / Soapy | Skip RFF; log; DF continues |
| Burst SNR < min | `LOW_SNR`; do not update gallery |
| ONNX crash | Catch, `NO_MODEL`/`SKIPPED`, never kill the SM |
| Gallery empty | Everything `NEW`; do not alert-flood; rate-limit still freq-based |
| Operator labels wrong radio | Manual rename/merge in gallery; audit row |
| People train on Kraken IQ and infer on RSP1B | `SENSOR_MISMATCH` if recipe/sensor ids differ; if they force it anyway, they deserve the 40% accuracy |

---

## 14. What this is not

- Not a substitute for DF. A match without a bearing is trivia.
- Not courtroom "this serial number." It is *same-sensor, same-recipe association*.
- Not C-UAS at 2.4 GHz on this hardware.
- Not BAE's paper dropped into `/opt`. That paper has no code and proprietary I/Q.
- Not an excuse to store days of IQ on a patrol-base laptop (ROE default).

---

## 15. Suggested repo layout (when implemented)

```
src/krakenbase/rff/
  __init__.py
  capture.py          # Soapy / rtl_sdr burst
  embed.py            # ONNX session
  gallery.py          # sqlite kNN
  fuse.py             # heuristic + rff → ClassificationResult
scripts/rff_train.py
scripts/rff_embed.py
docs/RFF_INTEGRATION.md   # this file
models/rff/               # onnx + LICENSE notes (git-lfs or local only)
```

Keep `[rff]` extra optional in `pyproject.toml` (`onnxruntime`, `numpy`). Do not make ONNX a hard runtime dep for people who only want DF.

---

## 16. Operator SOP (short)

1. Leave `rff.enabled: false` until R1 capture works on a known handheld.
2. Collect 20+ bursts × 3 ranges × 2 days on the RSP1B. Same gain.
3. Train on the laptop. Export ONNX. Copy to `model_path`.
4. Enable RFF. Watch `/events` for `rff` rows. Name clusters that repeat.
5. Trust `RFF_REPEAT` for de-dupe only after a week of not being laughed at by reality.
6. If you change LNA, cable, or sample rate, you started a new gallery. `recipe_id` is there so you cannot pretend otherwise.

---

## 17. Roadmap mapping

This document is the design for `docs/ROADMAP.md` Phase 6 items:

- "Richer classification hints" → heuristic + RFF fuse  
- "Integration with Recon-Raven event formats" → `emitter_uid` on the JSONL bridge  
- Secondary fleet capabilities → `rff_rsp1b`

Bump `roe.version` only if retention or mesh content policy changes. RFF off-by-default does not require an ROE bump.

---

## 18. References (verify, don't worship)

- KrakenBase: this repository (`ARCHITECTURE`, `SPEC` FR-30–32, `CONTRACTS` HandOffTask, `EmitterClassifier`).
- Hiles & Ahmad, arXiv:2510.09775 — generic RFF task framework; DMR/AIS/drone demos; low-complexity models; no public code.
- Dhakal et al., Siamese RFF on ADALM-PLUTO I/Q (public indoor dataset) — sandbox only.
- KrakenRF Heimdall / `gr-krakensdr` — coherent IQ is available; still the wrong default SEI sensor.
- SDRPlay RSP1B public specs — 14-bit at lower rates, 1 kHz–2 GHz.

---

*If the model cannot tell two site handhelds apart on the RSP1B in a controlled collect, it does not ship. Ship the capture path anyway.*
