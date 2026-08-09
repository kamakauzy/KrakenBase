"""Heading fusion: array offset + optional GPS/compass from DOA or NMEA."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HeadingState:
    absolute_offset_deg: float = 0.0
    gps_heading_deg: float | None = None
    compass_heading_deg: float | None = None
    source: str = "config"
    updated_at: float = 0.0
    stale_after_s: float = 30.0

    @property
    def age_s(self) -> float | None:
        if not self.updated_at:
            return None
        return time.time() - self.updated_at

    @property
    def is_stale(self) -> bool:
        age = self.age_s
        return age is None or age > self.stale_after_s

    def effective_offset(self) -> float:
        if self.compass_heading_deg is not None and not self.is_stale:
            return self.compass_heading_deg % 360.0
        if self.gps_heading_deg is not None and not self.is_stale:
            return self.gps_heading_deg % 360.0
        return self.absolute_offset_deg % 360.0


class HeadingFusion:
    def __init__(
        self,
        heading_offset_deg: float = 0.0,
        nmea_path: str | Path | None = None,
        stale_after_s: float = 30.0,
    ):
        self.state = HeadingState(
            absolute_offset_deg=heading_offset_deg,
            stale_after_s=stale_after_s,
        )
        self.nmea_path = Path(nmea_path) if nmea_path else None

    def update_from_doa(
        self,
        gps_heading: float | None = None,
        compass_heading: float | None = None,
    ) -> None:
        if gps_heading is None and compass_heading is None:
            return
        if compass_heading is not None:
            self.state.compass_heading_deg = compass_heading % 360.0
            self.state.source = "compass"
            self.state.updated_at = time.time()
        if gps_heading is not None:
            self.state.gps_heading_deg = gps_heading % 360.0
            if self.state.source != "compass":
                self.state.source = "gps"
            self.state.updated_at = time.time()

    def poll_nmea(self) -> None:
        if not self.nmea_path or not self.nmea_path.exists():
            return
        try:
            lines = self.nmea_path.read_text(errors="ignore").strip().splitlines()[-40:]
        except Exception as exc:
            logger.debug("NMEA read failed: %s", exc)
            return
        heading = None
        source = "gps"
        for line in reversed(lines):
            if not line.startswith("$"):
                continue
            parts = line.split(",")
            talker = parts[0]
            try:
                if "HDT" in talker and len(parts) > 1 and parts[1]:
                    heading = float(parts[1])
                    source = "gps"
                    break
                if "HDG" in talker and len(parts) > 1 and parts[1]:
                    heading = float(parts[1])
                    source = "compass"
                    break
                if "RMC" in talker and len(parts) > 8 and parts[8]:
                    heading = float(parts[8])
                    source = "gps"
                    break
            except ValueError:
                continue
        if heading is not None:
            if source == "compass":
                self.state.compass_heading_deg = heading % 360.0
            else:
                self.state.gps_heading_deg = heading % 360.0
            self.state.source = source
            self.state.updated_at = time.time()

    def absolute_bearing(self, relative_bearing_deg: float) -> float:
        self.poll_nmea()
        return (relative_bearing_deg + self.state.effective_offset()) % 360.0

    def snapshot(self) -> dict:
        return {
            "source": self.state.source,
            "config_offset_deg": self.state.absolute_offset_deg,
            "gps_heading_deg": self.state.gps_heading_deg,
            "compass_heading_deg": self.state.compass_heading_deg,
            "effective_offset_deg": self.state.effective_offset(),
            "age_s": self.state.age_s,
            "stale": self.state.is_stale,
        }
