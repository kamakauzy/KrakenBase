"""U2 camera / dry-contact triggers. Config URLs, no Amcrest hardcoded."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CameraTrigger:
    def __init__(
        self,
        motion_file: str | Path | None = None,
        gpio_file: str | Path | None = None,
        event_url: str | None = None,
        match: str = "Motion",
        camera_id: str = "cam0",
    ):
        self.motion_file = Path(motion_file) if motion_file else None
        self.gpio_file = Path(gpio_file) if gpio_file else None
        self.event_url = event_url
        self.match = match
        self.camera_id = camera_id
        self._last_mtime: float = 0.0
        self._last_gpio = "0"
        self._last_http = False

    def _file_edge(self) -> bool:
        if not self.motion_file or not self.motion_file.exists():
            return False
        mtime = self.motion_file.stat().st_mtime
        if mtime > self._last_mtime:
            self._last_mtime = mtime
            return True
        return False

    def _gpio_edge(self) -> bool:
        if not self.gpio_file or not self.gpio_file.exists():
            return False
        val = self.gpio_file.read_text().strip() or "0"
        edge = val not in ("0", "low", "false") and self._last_gpio in ("0", "low", "false", "")
        self._last_gpio = val
        return edge

    def _http_level(self) -> bool:
        if not self.event_url:
            return False
        try:
            import httpx

            r = httpx.get(self.event_url, timeout=2.0)
            hit = r.status_code == 200 and self.match.lower() in r.text.lower()
        except Exception as exc:
            logger.debug("camera http: %s", exc)
            return False
        edge = hit and not self._last_http
        self._last_http = hit
        return edge

    def poll(self) -> bool:
        return self._file_edge() or self._gpio_edge() or self._http_level()
