"""Crop growth parameters shared by the ML feature pipeline and the irrigation planner.

These are the FAO-56 style numbers the synthetic training data was generated with
(``scripts/generate_dataset.py``). ``tests/test_ml_pipeline.py`` asserts they stay identical to the generator,
so the model is never fed features built with different constants than it was trained on.

Pure Python: no database, HTTP or ML imports.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

# crop -> (Kc initial, Kc mid, Kc end), stage lengths in days (initial, development, mid, late)
CROP_KC: Dict[str, Tuple[float, float, float]] = {
    "rice": (1.05, 1.20, 0.90),
    "maize": (0.30, 1.20, 0.60),
    "cotton": (0.35, 1.15, 0.70),
    "wheat": (0.30, 1.15, 0.40),
}
CROP_STAGE_DAYS: Dict[str, Tuple[int, int, int, int]] = {
    "rice": (20, 30, 40, 30),
    "maize": (20, 35, 40, 25),
    "cotton": (30, 50, 40, 0),
    "wheat": (20, 30, 40, 30),
}

# Crops the shipped ML model was trained on. Anything else is NOT guessed; callers fall back to rules.
SUPPORTED_CROPS: Tuple[str, ...] = tuple(sorted(CROP_KC))

STAGES: Tuple[str, ...] = ("Sowing", "Vegetative", "Flowering", "Harvest")


def normalise_crop(crop: Optional[str]) -> Optional[str]:
    """Lower-case crop key if it is one the model supports, else None."""
    if not isinstance(crop, str):
        return None
    key = " ".join(crop.split()).lower()
    return key if key in CROP_KC else None


def kc_at(crop: str, days_after_sowing: float) -> float:
    """Crop coefficient at a given day after sowing (same piecewise curve as the data generator)."""
    k_ini, k_mid, k_end = CROP_KC[crop]
    d_ini, d_dev, d_mid, d_late = CROP_STAGE_DAYS[crop]
    das = days_after_sowing
    if das < d_ini:
        return k_ini
    if das < d_ini + d_dev:
        return k_ini + (k_mid - k_ini) * (das - d_ini) / d_dev
    if das < d_ini + d_dev + d_mid:
        return k_mid
    if d_late == 0:
        return k_mid
    return max(k_end, k_mid + (k_end - k_mid) * (das - d_ini - d_dev - d_mid) / d_late)


def stage_at(crop: str, days_after_sowing: float) -> str:
    d_ini, d_dev, d_mid, _ = CROP_STAGE_DAYS[crop]
    das = days_after_sowing
    if das < d_ini:
        return "Sowing"
    if das < d_ini + d_dev:
        return "Vegetative"
    if das < d_ini + d_dev + d_mid:
        return "Flowering"
    return "Harvest"
