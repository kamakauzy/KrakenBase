"""Hand-off task publishers (file + optional MQTT)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from krakenbase.config import HandOffSettings
from krakenbase.models import DoaEvent, HandOffTask, utcnow

logger = logging.getLogger(__name__)


class HandOffPublisher:
    """Publish HandOffTask after a high-confidence DOA."""

    def __init__(self, settings: HandOffSettings, data_dir: str | Path):
        self.settings = settings
        self.data_dir = Path(data_dir)
        self.out_dir = self.data_dir / "handoff"
        self._mqtt = None

        if settings.enabled and settings.transport == "mqtt":
            try:
                import paho.mqtt.publish as publish  # noqa: F401

                self._mqtt_publish = publish
            except Exception as exc:
                logger.warning("MQTT hand-off unavailable (%s) – using file", exc)
                self.settings.transport = "file"

    async def publish(self, doa: DoaEvent) -> HandOffTask:
        task = HandOffTask(
            freq_hz=doa.freq_hz,
            modulation_hint=None,
            priority=self.settings.defaults.priority,
            max_dwell_min=self.settings.defaults.max_dwell_min,
            record_iq=self.settings.defaults.record_iq,
            created_at=utcnow(),
            source_event_id=doa.event_id,
            target_node_id=self.settings.defaults.target_node_id,
        )
        rff = getattr(doa, "rff", None)
        if rff is not None and rff.disposition.value == "NEW":
            task.record_iq = True
            task.priority = max(1, task.priority - 2)

        if not self.settings.enabled:
            logger.debug("Hand-off disabled – task not published")
            return task

        payload = task.model_dump(mode="json")
        payload["bearing_deg"] = doa.bearing_deg
        payload["confidence"] = doa.confidence
        if rff is not None:
            payload["rff_disposition"] = rff.disposition.value
            payload["emitter_uid"] = rff.emitter_uid
            payload["rff_score"] = rff.score

        if self.settings.transport == "mqtt":
            try:
                self._mqtt_publish.single(
                    self.settings.mqtt.topic,
                    payload=json.dumps(payload, default=str),
                    hostname=self.settings.mqtt.host,
                    port=self.settings.mqtt.port,
                )
                logger.info("Hand-off MQTT %s → %.4f MHz", self.settings.mqtt.topic, task.freq_hz / 1e6)
            except Exception as exc:
                logger.error("MQTT hand-off failed: %s – falling back to file", exc)
                self._write_file(task, payload)
        else:
            self._write_file(task, payload)
        return task

    def _write_file(self, task: HandOffTask, payload: dict) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{task.task_id}.json"
        path.write_text(json.dumps(payload, indent=2, default=str))
        with (self.out_dir / "tasks.jsonl").open("a") as f:
            f.write(json.dumps(payload, default=str) + "\n")
        logger.info("Hand-off file %s  %.4f MHz", path.name, task.freq_hz / 1e6)
