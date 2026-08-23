# KrakenBase

**Fixed-site / patrol-base coherent SIGINT node**

KrakenBase turns a KrakenSDR 5-channel array + laptop into an adaptive  
**scan → detect → DF → alert → hand-off** system for permanent or semi-permanent sites.

Design goals: fewer moving parts than portable Recon-Raven, battery-capable laptop host, clear ROE, clean frequency hand-off to secondary RTL-SDR monitors. **Passive only in v1.**

## Quick start (synthetic – no hardware)

```bash
git clone https://github.com/kamakauzy/KrakenBase.git
cd KrakenBase
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m krakenbase.main --synthetic
```

Status: http://127.0.0.1:8090/health  

Full operator steps: **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**  
Laptop install + systemd: **[docs/INSTALL.md](docs/INSTALL.md)**

## Core loop

1. Maintain spectrum baseline across tactical bands  
2. Detect sustained anomaly  
3. Short coherent DOA dwell on KrakenSDR  
4. Bearing + confidence + frequency  
5. Mesh / local alert  
6. Optional hand-off to secondary RTL-SDR monitor  
7. Always return array to scan  

Optional post-v1:
- RF fingerprint / SEI on a **separate** receive chain (RSP1B preferred). [docs/RFF_INTEGRATION.md](docs/RFF_INTEGRATION.md)
- Remote RF UGS sidecar on grid-down camera poles. [docs/REMOTE_RF_UGS.md](docs/REMOTE_RF_UGS.md)

Neither replaces Kraken bearings.

## Hardware baseline

| Component | Role |
|-----------|------|
| KrakenSDR (UCA) | 5-channel coherent array |
| Laptop (Ubuntu 22.04+) | Heimdall + DOA + KrakenBase |
| GPS (optional) | Absolute heading / position |
| Meshtastic radio | Outbound alerts |
| Secondary RTL-SDR | Long-dwell monitor / record |
| SDRPlay RSP1B (planned) | RFF / SEI I/Q sensor — not the DF array |
| Remote UGS pole (planned) | Camera + sleeping RTL/RSP1B sidecar — not a second Kraken |

## Docs

| File | Purpose |
|------|---------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Run, config, troubleshoot |
| [docs/INSTALL.md](docs/INSTALL.md) | Ubuntu + systemd install |
| [docs/ROE.md](docs/ROE.md) | Operational rules the code enforces |
| [docs/SPEC.md](docs/SPEC.md) | Requirements |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Design |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | Kraken / event / API contracts |
| [docs/RFF_INTEGRATION.md](docs/RFF_INTEGRATION.md) | RF fingerprint / SEI side path (design) |
| [docs/REMOTE_RF_UGS.md](docs/REMOTE_RF_UGS.md) | Remote RF collector on camera poles (design) |
| [agent.md](agent.md) | Instructions for AI coding agents |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phased status |

## Secondary hand-off

```bash
python scripts/secondary_monitor.py --watch /var/lib/krakenbase/handoff
python scripts/secondary_monitor.py --watch /tmp/krakenbase/handoff --rtl
```

## Tests

```bash
pytest -v
```

## Legal / ROE

Passive monitoring and DF only. No transmit paths in v1. See `docs/ROE.md`.
