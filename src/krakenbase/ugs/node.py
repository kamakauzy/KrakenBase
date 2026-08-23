"""UGS node: synthetic, hand-off, camera, uplink. No TX."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from uuid import UUID

import httpx

from krakenbase.models import HandOffTask, UgsEvent, UgsTrigger, utcnow
from krakenbase.rff.capture import capture_burst
from krakenbase.rff.recipe import CaptureRecipe, get_recipe
from krakenbase.ugs import accepts_handoff

logger = logging.getLogger(__name__)


class UgsNode:
    def __init__(
        self,
        node_id: str,
        out_dir: str | Path,
        recipe: CaptureRecipe,
        sensor_id: str,
        backend: str = "synthetic",
        heartbeat_url: str | None = None,
        token: str | None = None,
        site: str | None = None,
        rate_limit_s: float = 60.0,
        uplink_dir: str | Path | None = None,
        camera=None,
    ):
        self.node_id = node_id
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.recipe = recipe
        self.sensor_id = sensor_id
        self.backend = backend
        self.heartbeat_url = heartbeat_url
        self.token = token
        self.site = site
        self.rate_limit_s = rate_limit_s
        self.uplink_dir = Path(uplink_dir) if uplink_dir else None
        self.camera = camera
        self._seen: set[str] = set()
        self._last_uplink: dict[int, float] = {}

    def _write_event(self, event: UgsEvent) -> Path:
        path = self.out_dir / f"{event.event_id}.ugs.json"
        path.write_text(event.model_dump_json(indent=2))
        with (self.out_dir / "ugs.jsonl").open("a") as f:
            f.write(event.model_dump_json() + "\n")
        return path

    def capture(self, freq_hz: int, trigger: UgsTrigger, source_task_id: UUID | None = None, notes: str | None = None) -> UgsEvent:
        burst = capture_burst(
            freq_hz, self.recipe, self.out_dir, sensor_id=self.sensor_id, backend=self.backend,
            stem=f"{self.node_id}_{freq_hz}_{trigger.value}", description=f"ugs {self.node_id} {trigger.value}",
        )
        event = UgsEvent(
            node_id=self.node_id, timestamp=utcnow(), trigger=trigger, freq_hz=freq_hz,
            bandwidth_hz=int(self.recipe.sample_rate), duration_ms=self.recipe.duration_ms,
            sensor_id=self.sensor_id, recipe_id=self.recipe.recipe_id, burst_path=str(burst.meta_path),
            source_task_id=source_task_id, notes=notes or f"backend={burst.backend}",
        )
        path = self._write_event(event)
        if self.uplink_dir:
            self.uplink_dir.mkdir(parents=True, exist_ok=True)
            (self.uplink_dir / path.name).write_text(path.read_text())
        logger.info("UGS %s %s %.4f MHz -> %s", self.node_id, trigger.value, freq_hz / 1e6, burst.meta_path.name)
        return event

    def allow_uplink(self, freq_hz: int) -> bool:
        now = time.time()
        last = self._last_uplink.get(freq_hz, 0.0)
        if now - last < self.rate_limit_s:
            logger.info("UGS rate-limit skip %s Hz", freq_hz)
            return False
        self._last_uplink[freq_hz] = now
        return True

    def synthetic_trigger(self, freq_hz: int = 462_712_500) -> UgsEvent | None:
        if not self.allow_uplink(freq_hz):
            return None
        return self.capture(freq_hz, UgsTrigger.ENERGY, notes="synthetic-trigger")

    def camera_poll(self, freq_hz: int) -> UgsEvent | None:
        if self.camera is None or not self.camera.poll():
            return None
        if not self.allow_uplink(freq_hz):
            return None
        ev = self.capture(freq_hz, UgsTrigger.CAMERA, notes=f"camera={self.camera.camera_id}")
        ev.camera_id = self.camera.camera_id
        self._write_event(ev)
        return ev

    def radio_ready(self) -> bool:
        if self.backend == "rtl":
            return shutil.which("rtl_sdr") is not None
        return True

    def heartbeat_status(self) -> str:
        return "online" if self.radio_ready() else "degraded"

    def handle_task(self, task: HandOffTask) -> UgsEvent | None:
        tid = str(task.task_id)
        if tid in self._seen:
            return None
        if not accepts_handoff(self.node_id, task):
            return None
        self._seen.add(tid)
        return self.capture(task.freq_hz, UgsTrigger.HANDOFF, source_task_id=task.task_id)

    def ingest_json(self, payload: dict) -> UgsEvent | None:
        return self.handle_task(HandOffTask.model_validate(payload))

    def scan_watch_dir(self, watch: str | Path) -> list[UgsEvent]:
        watch = Path(watch)
        if not watch.exists():
            return []
        out: list[UgsEvent] = []
        if (watch / "tasks.jsonl").exists():
            for line in (watch / "tasks.jsonl").read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    ev = self.ingest_json(json.loads(line))
                    if ev:
                        out.append(ev)
                except Exception as exc:
                    logger.warning("bad handoff line: %s", exc)
        for path in watch.glob("*.json"):
            if path.name.endswith(".ugs.json"):
                continue
            try:
                ev = self.ingest_json(json.loads(path.read_text()))
                if ev:
                    out.append(ev)
            except Exception as exc:
                logger.warning("bad handoff file %s: %s", path.name, exc)
        return out

    def heartbeat(self, status: str | None = None, current_freq_hz: int | None = None) -> None:
        if not self.heartbeat_url:
            return
        status = status or self.heartbeat_status()
        headers = {"X-API-Token": self.token} if self.token else {}
        body = {
            "node_id": self.node_id,
            "status": status,
            "capabilities": [f"ugs_{self.recipe.sensor_class}", "ugs_camera" if self.camera else "rtl_sdr"],
            "current_freq_hz": current_freq_hz,
            "site": self.site,
            "notes": None if self.radio_ready() else "no rtl_sdr",
        }
        try:
            httpx.post(self.heartbeat_url, json=body, headers=headers, timeout=3.0).raise_for_status()
        except Exception as exc:
            logger.warning("heartbeat failed: %s", exc)


def default_node(node_id: str = "ugs-bench-01", out_dir: str | Path = "/tmp/krakenbase/ugs",
                 recipe_id: str = "synthetic:48k:0", backend: str = "synthetic") -> UgsNode:
    return UgsNode(node_id=node_id, out_dir=out_dir, recipe=get_recipe(recipe_id),
                   sensor_id=f"{node_id}-sdr0", backend=backend)
