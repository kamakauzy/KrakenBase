#!/usr/bin/env python3
"""Export KrakenBase audit events to Recon-Raven bridge JSONL."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from krakenbase.interop.recon_raven import export_events_jsonl
from krakenbase.store.events import EventStore


async def main() -> None:
    ap = argparse.ArgumentParser(description="Export KB events → Recon-Raven JSONL")
    ap.add_argument("--db", required=True, help="Path to events.db")
    ap.add_argument("-o", "--out", required=True, help="Output .jsonl path")
    ap.add_argument("--site", default="krakenbase")
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--type", default=None, help="Filter event type")
    args = ap.parse_args()

    store = EventStore(args.db)
    await store.open()
    rows = await store.recent(limit=args.limit, event_type=args.type)
    rows = list(reversed(rows))
    n = export_events_jsonl(rows, args.out, site_id=args.site)
    await store.close()
    print(f"wrote {n} events → {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
