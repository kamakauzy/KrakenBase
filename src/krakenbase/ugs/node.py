"""U1 bench UGS node: synthetic trigger + hand-off consume + local SigMF."""

from __future__ import annotations

import json
import logging
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
        self._seen: set[str] = set()

    def _write_event(self, event: UgsEvent) -> Path:
        path = self.out_dir / f"{event.event_id}.ugs.json"
        path.write_text(event.model_dump_json(indent=2))
        feed = self.out_dir / "ugs.jsonl"
        with feed.open("a") as f:
            f.write(event.model_dump_json() + "\n")
        return path

    def capture(
        self,
        freq_hz: int,
        trigger: UgsTrigger,
        source_task_id: UUID | None = None,
        notes: str | None = None,
    ) -> UgsEvent:
        burst = capture_burst(
            freq_hz,
            self.recipe,
            self.out_dir,
            sensor_id=self.sensor_id,
            backend=self.backend,
            stem=f"{self.node_id}_{freq_hz}_{trigger.value}",
            description=f"ugs {self.node_id} {trigger.value}",
        )
        event = UgsEvent(
            node_id=self.node_id,
            timestamp=utcnow(),
            trigger=trigger,
            freq_hz=freq_hz,
            bandwidth_hz=int(self.recipe.sample_rate),
            duration_ms=self.recipe.duration_ms,
            sensor_id=self.sensor_id,
            recipe_id=self.recipe.recipe_id,
            burst_path=str(burst.meta_path),
            source_task_id=source_task_id,
            notes=notes or f"backend={burst.backend}",
        )
        self._write_event(event)
        logger.info(
            "UGS %s %s %.4f MHz -> %s",
            self.node_id,
            trigger.value,
            freq_hz / 1e6,
            burst.meta_path.name,
        )
        return event

    def synthetic_trigger(self, freq_hz: int = 462_712_500) -> UgsEvent:
        return self.capture(freq_hz, UgsTrigger.ENERGY, notes="synthetic-trigger")

    def handle_task(self, task: HandOffTask) -> UgsEvent | None:
        tid = str(task.task_id)
        if tid in self._seen:
            return None
        if not accepts_handoff(self.node_id, task):
            logger.info("UGS %s ignore task for %s", self.node_id, task.target_node_id)
            return None
        self._seen.add(tid)
        return self.capture(task.freq_hz, UgsTrigger.HANDOFF, source_task_id=task.task_id)

    def ingest_json(self, payload: dict) -> UgsEvent | None:
        task = HandOffTask.model_validate(payload)
        return self.handle_task(task)

    def scan_watch_dir(self, watch: str | Path) -> list[UgsEvent]:
        watch = Path(watch)
        if not watch.exists():
            return []
        out: list[UgsEvent] = []
        files = list(watch.glob("*.json"))
        feed = watch / "tasks.jsonl"
        if feed.exists():
            for line in feed.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = self.ingest_json(json.loads(line))
                    if ev:
                        out.append(ev)
                except Exception as exc:
                    logger.warning("bad handoff line: %s", exc)
        for path in files:
            if path.name.endswith(".ugs.json"):
                continue
            try:
                ev = self.ingest_json(json.loads(path.read_text()))
                if ev:
                    out.append(ev)
            except Exception as exc:
                logger.warning("bad handoff file %s: %s", path.name, exc)
        return out

    def heartbeat(self, status: str = "online", current_freq_hz: int | None = None) -> None:
        if not self.heartbeat_url:
            return
        headers = {}
        if self.token:
            headers["X-API-Token"] = self.token
        body = {
            "node_id": self.node_id,
            "status": status,
            "capabilities": [f"ugs_{self.recipe.sensor_class}", "rtl_sdr"],
            "current_freq_hz": current_freq_hz,
            "site": self.site,
        }
        try:
            r = httpx.post(self.heartbeat_url, json=body, headers=headers, timeout=3.0)
            r.raise_for_status()
        except Exception as exc:
            logger.warning("heartbeat failed: %s", exc)


def default_node(
    node_id: str = "ugs-bench-01",
    out_dir: str | Path = "/tmp/krakenbase/ugs",
    recipe_id: str = "synthetic:48k:0",
    backend: str = "synthetic",
) -> UgsNode:
    return UgsNode(
        node_id=node_id,
        out_dir=out_dir,
        recipe=get_recipe(recipe_id),
        sensor_id=f"{node_id}-sdr0",
        backend=backend,
    )
