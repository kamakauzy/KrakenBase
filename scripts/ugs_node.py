#!/usr/bin/env python3
"""U1 bench RF collector. Synthetic trigger or hand-off watch. No TX."""

from __future__ import annotations

import argparse
import logging
import time

from krakenbase.rff.recipe import get_recipe
from krakenbase.ugs.node import UgsNode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser(description="KrakenBase UGS bench node")
    p.add_argument("--node-id", default="ugs-bench-01")
    p.add_argument("--out", default="/tmp/krakenbase/ugs")
    p.add_argument("--recipe", default="synthetic:48k:0")
    p.add_argument("--backend", default="synthetic", choices=["auto", "synthetic", "rtl"])
    p.add_argument("--sensor-id", default=None)
    p.add_argument("--watch", default=None, help="handoff directory")
    p.add_argument("--synthetic-trigger", action="store_true")
    p.add_argument("--freq", type=int, default=462_712_500)
    p.add_argument("--heartbeat", default=None)
    p.add_argument("--token", default=None)
    p.add_argument("--site", default=None)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    node = UgsNode(
        node_id=args.node_id,
        out_dir=args.out,
        recipe=get_recipe(args.recipe),
        sensor_id=args.sensor_id or f"{args.node_id}-sdr0",
        backend=args.backend,
        heartbeat_url=args.heartbeat,
        token=args.token,
        site=args.site,
    )
    node.heartbeat("online")

    if args.synthetic_trigger:
        node.synthetic_trigger(args.freq)
        if args.once or not args.watch:
            node.heartbeat("online")
            return

    if not args.watch:
        raise SystemExit("need --watch and/or --synthetic-trigger")

    while True:
        node.scan_watch_dir(args.watch)
        node.heartbeat("online")
        if args.once:
            break
        time.sleep(2.0)


if __name__ == "__main__":
    main()
