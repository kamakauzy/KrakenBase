#!/usr/bin/env python3
"""U1/U2 RF collector: synthetic, hand-off, camera/GPIO, heartbeat. No TX."""

from __future__ import annotations

import argparse
import logging
import time

from krakenbase.rff.recipe import get_recipe
from krakenbase.ugs.camera import CameraTrigger
from krakenbase.ugs.node import UgsNode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser(description="KrakenBase UGS node")
    p.add_argument("--node-id", default="ugs-bench-01")
    p.add_argument("--out", default="/tmp/krakenbase/ugs")
    p.add_argument("--recipe", default="synthetic:48k:0")
    p.add_argument("--backend", default="synthetic", choices=["auto", "synthetic", "rtl"])
    p.add_argument("--sensor-id", default=None)
    p.add_argument("--watch", default=None)
    p.add_argument("--synthetic-trigger", action="store_true")
    p.add_argument("--freq", type=int, default=462_712_500)
    p.add_argument("--heartbeat", default=None)
    p.add_argument("--token", default=None)
    p.add_argument("--site", default=None)
    p.add_argument("--once", action="store_true")
    p.add_argument("--rate-limit-s", type=float, default=60.0)
    p.add_argument("--uplink", default=None, help="shop drop dir (NanoBeam share)")
    p.add_argument("--motion-file", default=None)
    p.add_argument("--gpio-file", default=None)
    p.add_argument("--camera-url", default=None)
    p.add_argument("--camera-match", default="Motion")
    p.add_argument("--camera-id", default="cam0")
    args = p.parse_args()

    cam = None
    if args.motion_file or args.gpio_file or args.camera_url:
        cam = CameraTrigger(
            motion_file=args.motion_file,
            gpio_file=args.gpio_file,
            event_url=args.camera_url,
            match=args.camera_match,
            camera_id=args.camera_id,
        )

    node = UgsNode(
        node_id=args.node_id,
        out_dir=args.out,
        recipe=get_recipe(args.recipe),
        sensor_id=args.sensor_id or f"{args.node_id}-sdr0",
        backend=args.backend,
        heartbeat_url=args.heartbeat,
        token=args.token,
        site=args.site,
        rate_limit_s=args.rate_limit_s,
        uplink_dir=args.uplink,
        camera=cam,
    )
    node.heartbeat()

    if args.synthetic_trigger:
        node.synthetic_trigger(args.freq)

    looping = bool(args.watch or cam)
    if not looping and not args.synthetic_trigger:
        raise SystemExit("need --watch, --synthetic-trigger, and/or camera/gpio")
    if not looping:
        return

    while True:
        if args.watch:
            node.scan_watch_dir(args.watch)
        if cam:
            node.camera_poll(args.freq)
        node.heartbeat()
        if args.once:
            break
        time.sleep(2.0)


if __name__ == "__main__":
    main()
