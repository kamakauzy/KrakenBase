#!/usr/bin/env python3
"""
Secondary monitor node – consumes KrakenBase hand-off tasks.

Watches a handoff directory (JSONL / per-task JSON) or an MQTT topic.
When a task arrives, logs it and optionally locks an RTL-SDR with rtl_fm
or records a short capture with rtl_sdr.

Usage:
  python scripts/secondary_monitor.py --watch /var/lib/krakenbase/handoff
  python scripts/secondary_monitor.py --watch /tmp/krakenbase/handoff --rtl
  python scripts/secondary_monitor.py --mqtt 127.0.0.1 --topic krakenbase/handoff
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
logger = logging.getLogger("secondary_monitor")


def handle_task(task: dict, use_rtl: bool, record_dir: Path, record_seconds: int) -> None:
    freq_hz = int(task.get("freq_hz", 0))
    if not freq_hz:
        logger.warning("Task missing freq_hz: %s", task)
        return

    conf = task.get("confidence")
    bearing = task.get("bearing_deg")
    task_id = str(task.get("task_id", "?"))[:8]
    max_dwell = int(task.get("max_dwell_min", 10))

    logger.info(
        "TASK %s  %.4f MHz  bearing=%s  conf=%s  max_dwell=%smin",
        task_id,
        freq_hz / 1e6,
        f"{bearing:.0f}\u00b0" if bearing is not None else "?",
        f"{conf:.0f}" if conf is not None else "?",
        max_dwell,
    )

    if not use_rtl:
        logger.info("  (no --rtl) would lock secondary SDR here")
        return

    record_dir.mkdir(parents=True, exist_ok=True)
    out = record_dir / f"{task_id}_{freq_hz}.cu8"

    rtl_sdr = shutil.which("rtl_sdr")
    rtl_fm = shutil.which("rtl_fm")

    if rtl_sdr:
        cmd = [
            rtl_sdr,
            "-f",
            str(freq_hz),
            "-s",
            "2400000",
            "-n",
            str(2_400_000 * record_seconds),
            str(out),
        ]
        logger.info("  running: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, check=False, timeout=record_seconds + 15)
            logger.info("  wrote %s", out)
        except Exception as exc:
            logger.error("  rtl_sdr failed: %s", exc)
    elif rtl_fm:
        wav = record_dir / f"{task_id}_{freq_hz}.raw"
        cmd = [
            rtl_fm,
            "-f",
            str(freq_hz),
            "-M",
            "fm",
            "-s",
            "22050",
            "-g",
            "40",
            str(wav),
        ]
        logger.info("  running rtl_fm for %ss \u2192 %s", record_seconds, wav)
        try:
            proc = subprocess.Popen(cmd)
            time.sleep(record_seconds)
            proc.terminate()
            proc.wait(timeout=5)
            logger.info("  done")
        except Exception as exc:
            logger.error("  rtl_fm failed: %s", exc)
    else:
        logger.warning("  rtl_sdr / rtl_fm not found on PATH \u2013 install librtlsdr tools")


def watch_dir(path: Path, use_rtl: bool, record_dir: Path, record_seconds: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    feed = path / "tasks.jsonl"
    seen: set[str] = set()
    logger.info("Watching %s (JSONL + *.json)", path)

    for p in path.glob("*.json"):
        if p.name == "tasks.jsonl":
            continue
        seen.add(p.stem)

    while True:
        for p in sorted(path.glob("*.json")):
            if p.name == "tasks.jsonl" or p.stem in seen:
                continue
            try:
                task = json.loads(p.read_text())
                seen.add(p.stem)
                handle_task(task, use_rtl, record_dir, record_seconds)
            except Exception as exc:
                logger.error("Bad task file %s: %s", p, exc)

        if feed.exists():
            with feed.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        task = json.loads(line)
                        tid = str(task.get("task_id", line[:40]))
                        if tid in seen:
                            continue
                        seen.add(tid)
                        handle_task(task, use_rtl, record_dir, record_seconds)
                    except Exception as exc:
                        logger.debug("Skip JSONL line: %s", exc)

        time.sleep(1.0)


def watch_mqtt(host: str, port: int, topic: str, use_rtl: bool, record_dir: Path, record_seconds: int) -> None:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logger.error("paho-mqtt not installed. pip install paho-mqtt")
        sys.exit(1)

    def on_message(_client, _userdata, msg):
        try:
            task = json.loads(msg.payload.decode())
            handle_task(task, use_rtl, record_dir, record_seconds)
        except Exception as exc:
            logger.error("MQTT message error: %s", exc)

    client = mqtt.Client()
    client.on_message = on_message
    client.connect(host, port, 60)
    client.subscribe(topic)
    logger.info("MQTT subscribed %s:%s %s", host, port, topic)
    client.loop_forever()


def main() -> None:
    ap = argparse.ArgumentParser(description="KrakenBase secondary monitor / hand-off consumer")
    ap.add_argument("--watch", type=Path, help="Handoff directory (file transport)")
    ap.add_argument("--mqtt", help="MQTT broker host")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", default="krakenbase/handoff")
    ap.add_argument("--rtl", action="store_true", help="Attempt rtl_sdr / rtl_fm capture")
    ap.add_argument("--record-dir", type=Path, default=Path("/tmp/krakenbase/secondary"))
    ap.add_argument("--record-seconds", type=int, default=8)
    args = ap.parse_args()

    if args.watch:
        watch_dir(args.watch, args.rtl, args.record_dir, args.record_seconds)
    elif args.mqtt:
        watch_mqtt(args.mqtt, args.port, args.topic, args.rtl, args.record_dir, args.record_seconds)
    else:
        ap.error("Provide --watch DIR or --mqtt HOST")


if __name__ == "__main__":
    main()
