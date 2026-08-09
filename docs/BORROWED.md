# Borrowed / Reference Material

## From sigint-field-kit (kamakauzy)
- `kraken_doa_collector.py` – polling pattern, SQLite logging of bearings
- `emitter_locator.py` – triangulation / CEP ideas (useful later for multi-observation)
- `sigint_adaptive.sh` / adaptive collection logic – the scan → anomaly → focused dwell loop
- Baseline diff concepts
- Antenna calculator thinking (array radius must be correct)

## From Recon-Raven (kamakauzy)
- Event-oriented design and correlation IDs
- FastAPI status surface patterns
- Config YAML + environment override approach
- DF solver / weighted bearing ideas (simplified here)
- Overall “F3EAD-aligned” mindset mapped to a fixed site

## From official KrakenRF software
- Heimdall DAQ + krakensdr_doa as the coherent sensor
- `DOA_value.html` CSV format (primary data contract)
- `settings.json` / middleware control plane
- UCA geometry requirements and calibration behavior

## Intentionally Not Borrowed
- Full multi-SDR portable orchestration
- HackRF TX paths and safety gates
- Heavy web dashboard / live waterfall requirements
- Mobile power / thermal compromises
- Complex federation between many Raven nodes

KrakenBase is a focused fixed-site derivative, not a fork.
