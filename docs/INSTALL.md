# KrakenBase – Install (Ubuntu laptop)

Target: Ubuntu 22.04/24.04 x86_64, co-located with official Kraken stack.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
# optional secondary capture
sudo apt install -y rtl-sdr
```

Install and start the **official** KrakenRF stack separately so  
`http://127.0.0.1:8081/DOA_value.html` is live before KrakenBase.

## 2. App user + dirs

```bash
sudo useradd -r -m -d /opt/krakenbase -s /usr/sbin/nologin krakenbase || true
sudo mkdir -p /opt/krakenbase /etc/krakenbase /var/lib/krakenbase
sudo chown -R krakenbase:krakenbase /opt/krakenbase /var/lib/krakenbase
```

## 3. Code + venv

```bash
sudo -u krakenbase -H bash -c '
  cd /opt/krakenbase
  git clone https://github.com/kamakauzy/KrakenBase.git .
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -U pip
  pip install -e ".[dev]"
'
```

For Meshtastic radios:

```bash
sudo -u krakenbase -H /opt/krakenbase/.venv/bin/pip install 'meshtastic>=2.3.0'
sudo usermod -aG dialout krakenbase
```

## 4. Config

```bash
sudo cp /opt/krakenbase/config/config.example.yaml /etc/krakenbase/config.yaml
sudo chown krakenbase:krakenbase /etc/krakenbase/config.yaml
sudoedit /etc/krakenbase/config.yaml
```

Minimum edits:
- `system.data_dir` / `audit_db` → `/var/lib/krakenbase/...`
- `array.heading_offset_deg` and `array.radius_m` (measure)
- `baseline.bands` to your authorized ranges
- `alert.meshtastic.interface` if using mesh
- `system.retention_days` (default 30; `0` = keep forever)

## 5. systemd

```bash
sudo cp /opt/krakenbase/deploy/krakenbase.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now krakenbase
sudo systemctl status krakenbase
journalctl -u krakenbase -f
```

## 6. Smoke checks

```bash
curl -s http://127.0.0.1:8090/health
curl -s http://127.0.0.1:8090/state
sudo -u krakenbase -H /opt/krakenbase/.venv/bin/python -m krakenbase.main --synthetic
```

## 7. Secondary node (optional)

```bash
python scripts/secondary_monitor.py --watch /var/lib/krakenbase/handoff
python scripts/secondary_monitor.py --watch /var/lib/krakenbase/handoff --rtl
```

## Uninstall

```bash
sudo systemctl disable --now krakenbase
sudo rm /etc/systemd/system/krakenbase.service
sudo systemctl daemon-reload
```

## Notes

- Bind status API to localhost only unless you know what you are doing.
- Kraken calibration must finish before bearings are trustworthy.
- See `docs/USER_GUIDE.md` for operations and troubleshooting.
