#!/usr/bin/env python3
"""R1: grab one SigMF burst. Default backend is synthetic (no dongle required)."""

from __future__ import annotations

import argparse
import logging

from krakenbase.rff.capture import capture_burst
from krakenbase.rff.recipe import get_recipe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--freq", type=int, required=True)
    p.add_argument("--recipe", default="synthetic:48k:0")
    p.add_argument("--backend", default="auto", choices=["auto", "synthetic", "rtl"])
    p.add_argument("--sensor-id", default="bench-sdr0")
    p.add_argument("--out", default="/tmp/krakenbase/rff")
    args = p.parse_args()
    burst = capture_burst(
        args.freq,
        get_recipe(args.recipe),
        args.out,
        sensor_id=args.sensor_id,
        backend=args.backend,
    )
    print(burst.meta_path)


if __name__ == "__main__":
    main()
