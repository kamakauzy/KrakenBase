# KrakenBase

Patrol-base KrakenSDR node: **scan → detect → DF → alert → hand freq to an RTL → scan.**

Passive only. No TX. No fingerprint theater on this branch.

## Quick start

```bash
git clone https://github.com/kamakauzy/KrakenBase.git
cd KrakenBase
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m krakenbase.main --synthetic
```

Status: http://127.0.0.1:8090/health

Live array: [docs/DRAGONOS.md](docs/DRAGONOS.md)  
What this is (and is not): [docs/SCOPE.md](docs/SCOPE.md)

## Hand-off

```bash
python scripts/secondary_monitor.py --watch /var/lib/krakenbase/handoff
python scripts/secondary_monitor.py --watch /var/lib/krakenbase/handoff --rtl
```

## Not in main

RFF, UGS, fleet, ATAK, and the 32-d "SEI" toy are on **`archive/phase6-rff-ugs`**.

```bash
git fetch origin archive/phase6-rff-ugs
```

## Legal

`docs/ROE.md`. `roe.allow_tx=true` will not start.
