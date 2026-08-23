#!/usr/bin/env python3
"""R2: embed a SigMF burst into the gallery. Does not name emitters."""

from __future__ import annotations

import argparse
import json

from krakenbase.rff.gallery import Gallery


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("meta", help=".sigmf-meta path")
    p.add_argument("--gallery", default="/var/lib/krakenbase/rff_gallery.db")
    p.add_argument("--sensor-id", default=None)
    p.add_argument("--recipe-id", default=None)
    p.add_argument("--label", default=None, help="operator name; never auto")
    p.add_argument("--list", action="store_true")
    args = p.parse_args()
    gal = Gallery(args.gallery)
    if args.list:
        print(json.dumps(gal.list_emitters(args.sensor_id), indent=2))
        return
    result = gal.ingest_sigmf(args.meta, sensor_id=args.sensor_id, recipe_id=args.recipe_id)
    if args.label and result.emitter_uid:
        gal.label(result.emitter_uid, args.label)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
