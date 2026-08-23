# KrakenBase on a DragonOS laptop + Kraken array

This is the roll document. Not a feature list.

**Target:** DragonOS FocalX (22.04), Noble (24.04), or Resolute (26.04) x86_64 laptop  
**Array:** KrakenSDR 5-ch UCA, official Heimdall + `krakensdr_doa` on **this same box**  
**ROE:** RX only. `roe.allow_tx=true` will not start.

If you have never seen `DOA_value.html` produce CSV on this laptop, stop and fix Kraken first.

## What you are installing

| Piece | Job | Do not use it for |
|-------|-----|-------------------|
| Official Kraken stack | Coherent DF | Fingerprints, long I/Q |
| KrakenBase | Scan → anomaly → short dwell → alert → hand-off | Second DF solver |
| Optional RSP1B | RFF burst sensor | MUSIC bearings |
| Optional extra RTL | Secondary monitor / UGS bench | Sharing USB with the array |

The five Kraken dongles are the array. An extra RTL-SDR on the same USB controller will steal a slot or reset a bus. Plug extras into a **powered hub on a different controller**, or leave them unplugged until the array is stable.

## Day-0 order (do not skip)

1. Synthetic KrakenBase (no SDR).
2. Official Kraken stack + one known beacon → bearings look sane.
3. KrakenBase live against that stack.
4. Then RFF / UGS. Not before.

## 0. Machine

- x86_64 laptop, 16 GB RAM if you also run Heimdall + a browser. 8 GB is miserable.
- Measure `array.radius_m`. Sight element 0. Write both numbers down before you type YAML.
- Blacklist DVB **before** you fight drivers:

```bash
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-dvb_usb_rtl28xxu.conf
sudo update-initramfs -u
```

Replug the Kraken after reboot. `lsusb` should show five Realtek devices.

DragonOS already ships a pile of SDR tools. Do **not** `apt purge librtlsdr` unless the official Kraken install script tells you to. Kraken uses a forked librtlsdr. Random `rtl_tcp` / GQRX on those same dongles will wreck coherence.

## 1. Official Kraken stack

Use KrakenRF's current x86 script, not a random blog:

https://github.com/krakenrf/krakensdr_docs/wiki/09.-VirtualBox,-Docker-Images-and-Install-Scripts

After install + reboot:

```bash
cd ~/krakensdr_doa   # or wherever the script put it
./kraken_doa_start.sh
```

Pass:

```bash
curl -s http://127.0.0.1:8081/DOA_value.html | head
```

You want CSV, not an empty page and not a connection refused. Finish Kraken's own calibration. KrakenBase will happily log garbage bearings if you skip this.

## 2. KrakenBase

Interactive user is fine on a field laptop. systemd `krakenbase` user is for a parked box (see `docs/INSTALL.md`).

```bash
sudo apt install -y python3-venv python3-pip git rtl-sdr
mkdir -p ~/src /var/tmp/krakenbase
cd ~/src
git clone https://github.com/kamakauzy/KrakenBase.git
cd KrakenBase
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
pytest -q
```

If pytest is red, **do not** plug the array in and hope. Fix the venv.

### Synthetic first (mandatory)

```bash
python -m krakenbase.main --synthetic
```

Other terminal:

```bash
curl -s http://127.0.0.1:8090/health
curl -s http://127.0.0.1:8090/state
curl -s 'http://127.0.0.1:8090/events?limit=5'
```

You should see SCANNING → TASKING → DWELLING → ALERTING → SCANNING on a ~20 s synth beacon.

Ctrl-C. Then live config.

```bash
cp config/config.example.yaml ~/krakenbase.yaml
```

Minimum live edits:

```yaml
system:
  site_id: "dragon-01"
  data_dir: "/home/YOU/krakenbase-data"
  audit_db: "/home/YOU/krakenbase-data/events.db"
  log_level: INFO

kraken:
  host: "127.0.0.1"
  doa_port: 8081
  min_confidence: 70.0

array:
  radius_m: 0.15          # MEASURE
  heading_offset_deg: 0.0 # SIGHT element 0

site:
  lat: null
  lon: null

baseline:
  power_source: "kraken"
  anomaly_margin_db: 10.0
  min_anomaly_duration_s: 2.0
  rearm_s: 300.0

alert:
  meshtastic:
    enabled: false
    interface: "/dev/ttyUSB0"

handoff:
  enabled: true
  transport: file

rff:
  enabled: false

ugs:
  enabled: false
  cue_dwell: false

roe:
  allow_tx: false
  version: "0.1"

status_api:
  host: "127.0.0.1"
  port: 8090
  token: null
```

Create the data dir, add your user to `plugdev` / `dialout`, start **Kraken DOA first**, then:

```bash
mkdir -p ~/krakenbase-data
python -m krakenbase.main -c ~/krakenbase.yaml
```

Pass:

- `/health` → `ok` or briefly `degraded` while Kraken starts, not stuck `FAULT`
- `kraken_age_s` stays small
- A known emitter in a configured band produces one anomaly, one dwell, then SCANNING again

If tasking never confirms tune: Kraken control path is wrong. KrakenBase will refuse to pretend the VFO moved. That is correct.

## 3. RFF on this laptop (after DF works)

RSP1B is the fingerprint radio. The array is not.

Today the capture backends are **synthetic** and **`rtl_sdr` CLI**. There is no blessed live Soapy/RSP1B writer in-tree.

```bash
python scripts/rff_capture.py --recipe rtl_v4:2.4e6:30 --backend rtl \
  --freq 462712500 --out ~/krakenbase-data/rff --sensor-id dragon-rtl0

python scripts/rff_embed.py ~/krakenbase-data/rff/*.sigmf-meta \
  --gallery ~/krakenbase-data/rff_gallery.db --label handheld-red
```

Then enable `rff` in YAML with matching `sensor_id` / `recipe_id` / paths. Do not mix RTL bursts into an RSP1B gallery.

`builtin_v0` is a 32-d toy embedder. It is not the BAE paper model.

## 4. UGS later

Poles are a different box. On the laptop you only ingest. Leave `cue_dwell: false`.

## 5. Common DragonOS self-owns

| You did | What happens |
|---------|----------------|
| GQRX / SDR++ opened a Kraken dongle | Coherence dies, KB goes DEGRADED |
| Extra RTL on the same bus as the Kraken | Random channel drop |
| Started KB before Heimdall | FAULT until DOA exists |
| Guessed `radius_m` | Pretty, wrong LOBs |
| `cue_dwell: true` on day one | Array parks on camera glitches |

## 6. Stop

```bash
pkill -f 'krakenbase.main' || true
```

Data stays in `system.data_dir`. That is the audit trail.

## Related

- [USER_GUIDE.md](USER_GUIDE.md)
- [INSTALL.md](INSTALL.md)
- [LIMITATIONS.md](LIMITATIONS.md)
- [ROE.md](ROE.md)
