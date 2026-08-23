"""Capture recipes. One gallery / one recipe per physical sensor class."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class CaptureRecipe(BaseModel):
    recipe_id: str
    sensor_class: str
    sample_rate: float = 2_400_000.0
    gain_db: float = 30.0
    duration_ms: int = 40
    datatype: str = "cu8"
    bandwidth_hz: int | None = None
    notes: str | None = None

    @property
    def sample_count(self) -> int:
        return max(1, int(self.sample_rate * (self.duration_ms / 1000.0)))


DEFAULT_RECIPES = [
    CaptureRecipe(
        recipe_id="synthetic:48k:0",
        sensor_class="synthetic",
        sample_rate=48_000.0,
        gain_db=0.0,
        duration_ms=20,
        datatype="cf32_le",
        notes="CI / bench. Not a field gallery.",
    ),
    CaptureRecipe(
        recipe_id="rtl_v4:2.4e6:30",
        sensor_class="rtl_v4",
        sample_rate=2_400_000.0,
        gain_db=30.0,
        duration_ms=40,
        datatype="cu8",
    ),
    CaptureRecipe(
        recipe_id="rtl_v3:2.4e6:30",
        sensor_class="rtl_v3",
        sample_rate=2_400_000.0,
        gain_db=30.0,
        duration_ms=40,
        datatype="cu8",
    ),
    CaptureRecipe(
        recipe_id="rsp1b:2e6:20",
        sensor_class="rsp1b",
        sample_rate=2_000_000.0,
        gain_db=20.0,
        duration_ms=40,
        datatype="cf32_le",
        notes="Needs SoapySDR + sdrplay. R1 writes the recipe only.",
    ),
]


def load_recipes(path: str | Path | None = None) -> dict[str, CaptureRecipe]:
    recipes = {r.recipe_id: r for r in DEFAULT_RECIPES}
    if path is None:
        return recipes
    p = Path(path)
    if not p.exists():
        return recipes
    raw = yaml.safe_load(p.read_text()) or {}
    items: list[Any] = raw.get("recipes", raw) if isinstance(raw, dict) else raw
    for item in items:
        rec = CaptureRecipe.model_validate(item)
        recipes[rec.recipe_id] = rec
    return recipes


def get_recipe(recipe_id: str, path: str | Path | None = None) -> CaptureRecipe:
    recipes = load_recipes(path)
    if recipe_id not in recipes:
        raise KeyError(f"unknown recipe {recipe_id}")
    return recipes[recipe_id]
