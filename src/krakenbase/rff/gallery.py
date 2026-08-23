"""Per-sensor gallery. No auto-promote. SQLite on the laptop."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from krakenbase.models import RffDisposition, RffResult, utcnow
from krakenbase.rff.embed import EMBEDDER_ID, cosine, embed_sigmf

SCHEMA = """
CREATE TABLE IF NOT EXISTS emitters (
    emitter_uid TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL,
    recipe_id TEXT NOT NULL,
    vector TEXT NOT NULL,
    count INTEGER NOT NULL,
    labeled INTEGER NOT NULL DEFAULT 0,
    label TEXT,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gal_sensor ON emitters(sensor_id, recipe_id);
"""


@dataclass
class GalleryHit:
    emitter_uid: str
    score: float
    labeled: bool
    label: str | None
    count: int


class Gallery:
    def __init__(self, path: str | Path, match_thr: float = 0.92, new_thr: float = 0.80):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.match_thr = match_thr
        self.new_thr = new_thr
        self._db = sqlite3.connect(str(self.path))
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def _rows(self, sensor_id: str, recipe_id: str) -> list[tuple]:
        cur = self._db.execute(
            "SELECT emitter_uid, vector, count, labeled, label FROM emitters WHERE sensor_id=? AND recipe_id=?",
            (sensor_id, recipe_id),
        )
        return list(cur.fetchall())

    def best(self, vec: list[float], sensor_id: str, recipe_id: str) -> GalleryHit | None:
        best = None
        for uid, raw, count, labeled, label in self._rows(sensor_id, recipe_id):
            score = cosine(vec, json.loads(raw))
            if best is None or score > best.score:
                best = GalleryHit(uid, score, bool(labeled), label, count)
        return best

    def insert(self, vec: list[float], sensor_id: str, recipe_id: str, label: str | None = None) -> str:
        uid = f"unk_{uuid4().hex[:10]}"
        now = utcnow().isoformat()
        self._db.execute("INSERT INTO emitters VALUES (?,?,?,?,?,?,?,?,?)",
                         (uid, sensor_id, recipe_id, json.dumps(vec), 1, 1 if label else 0, label, now, now))
        self._db.commit()
        return uid

    def touch(self, uid: str) -> None:
        self._db.execute("UPDATE emitters SET count=count+1, last_seen=? WHERE emitter_uid=?",
                         (utcnow().isoformat(), uid))
        self._db.commit()

    def label(self, uid: str, label: str) -> bool:
        cur = self._db.execute("UPDATE emitters SET labeled=1, label=? WHERE emitter_uid=?", (label, uid))
        self._db.commit()
        return (cur.rowcount or 0) > 0

    def list_emitters(self, sensor_id: str | None = None) -> list[dict]:
        if sensor_id:
            cur = self._db.execute(
                "SELECT emitter_uid, sensor_id, recipe_id, count, labeled, label, last_seen FROM emitters WHERE sensor_id=?",
                (sensor_id,),
            )
        else:
            cur = self._db.execute(
                "SELECT emitter_uid, sensor_id, recipe_id, count, labeled, label, last_seen FROM emitters"
            )
        cols = ["emitter_uid", "sensor_id", "recipe_id", "count", "labeled", "label", "last_seen"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def ingest_sigmf(self, meta_path: str | Path, sensor_id: str | None = None, recipe_id: str | None = None,
                     source_event_id=None, freq_hz: int | None = None, min_snr_db: float | None = None) -> RffResult:
        vec, info = embed_sigmf(meta_path)
        sid = sensor_id or info.get("sensor_id") or "unknown"
        rid = recipe_id or info.get("recipe_id") or "unknown"
        file_rid = info.get("recipe_id")
        snr = info.get("snr_db")
        now_freq = int(freq_hz or info.get("freq_hz") or 0)
        if min_snr_db is not None and snr is not None and snr < min_snr_db:
            return RffResult(freq_hz=now_freq, sensor_id=sid, recipe_id=rid, disposition=RffDisposition.LOW_SNR,
                             notes=f"snr={snr:.1f} < {min_snr_db}", source_event_id=source_event_id)
        if file_rid and recipe_id and file_rid != recipe_id:
            return RffResult(freq_hz=now_freq, sensor_id=sid, recipe_id=rid, disposition=RffDisposition.RECIPE_MISMATCH,
                             notes=f"file recipe {file_rid} != {recipe_id}", source_event_id=source_event_id)
        hit = self.best(vec, sid, rid)
        if hit and hit.score >= self.match_thr:
            self.touch(hit.emitter_uid)
            disp = RffDisposition.RFF_MATCH if hit.count == 1 else RffDisposition.REPEAT
            return RffResult(freq_hz=now_freq, sensor_id=sid, recipe_id=rid, disposition=disp,
                             emitter_uid=hit.emitter_uid, score=round(hit.score, 4), source_event_id=source_event_id,
                             notes=f"embedder={EMBEDDER_ID} label={hit.label or '-'}")
        if hit and hit.score >= self.new_thr:
            self.touch(hit.emitter_uid)
            return RffResult(freq_hz=now_freq, sensor_id=sid, recipe_id=rid, disposition=RffDisposition.RFF_MATCH,
                             emitter_uid=hit.emitter_uid, score=round(hit.score, 4), source_event_id=source_event_id,
                             notes=f"embedder={EMBEDDER_ID} weak-match")
        uid = self.insert(vec, sid, rid)
        return RffResult(freq_hz=now_freq, sensor_id=sid, recipe_id=rid, disposition=RffDisposition.NEW,
                         emitter_uid=uid, score=round(hit.score, 4) if hit else None, source_event_id=source_event_id,
                         notes=f"embedder={EMBEDDER_ID} unlabeled cluster")
