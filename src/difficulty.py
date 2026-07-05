#!/usr/bin/env python3
"""Difficulty modes: scale enemy HP/damage and XP by the active mode.

The player picks a mode (easy/medium/hard); multipliers live in
data/difficulty.yaml (calibrated by the sim tuner). Applied at two seams:
GameWorld.get_enemy (enemy stats) and combat XP award. See
docs/DIFFICULTY_SIM_DESIGN.md.
"""
from __future__ import annotations

import os

import yaml

from utils.debug_tools import debug_log

MODES = ("easy", "medium", "hard")
DEFAULT_MODE = "medium"

# Safe fallback if the config is missing/malformed (medium = neutral).
_FALLBACK = {
    "easy": {"enemy_hp": 0.8, "enemy_damage": 0.7, "xp_gain": 1.3},
    "medium": {"enemy_hp": 1.0, "enemy_damage": 1.0, "xp_gain": 1.0},
    "hard": {"enemy_hp": 1.3, "enemy_damage": 1.4, "xp_gain": 0.8},
}

_multipliers: dict[str, dict[str, float]] = dict(_FALLBACK)
_mode: str = DEFAULT_MODE


def load(path: str = "data/difficulty.yaml") -> None:
    """Load per-mode multipliers from YAML (falls back to built-in defaults)."""
    global _multipliers
    try:
        if os.path.exists(path):
            with open(path) as fh:
                data = yaml.safe_load(fh) or {}
            merged = dict(_FALLBACK)
            for mode in MODES:
                if isinstance(data.get(mode), dict):
                    merged[mode] = {**_FALLBACK[mode], **data[mode]}
            _multipliers = merged
    except Exception as e:  # never let bad config break the game
        debug_log(f"difficulty: could not load {path}: {e}; using defaults")
        _multipliers = dict(_FALLBACK)


def set_mode(mode: str) -> None:
    global _mode
    _mode = mode if mode in MODES else DEFAULT_MODE


def current_mode() -> str:
    return _mode


def _mult() -> dict[str, float]:
    return _multipliers.get(_mode, _FALLBACK[DEFAULT_MODE])


def scale_enemy(enemy: dict) -> dict:
    """Return a copy of enemy data with HP/damage scaled for the active mode."""
    if not isinstance(enemy, dict):
        return enemy
    m = _mult()
    scaled = dict(enemy)
    if "health" in scaled and isinstance(scaled["health"], (int, float)):
        scaled["health"] = max(1, round(scaled["health"] * m["enemy_hp"]))
    if "damage" in scaled and isinstance(scaled["damage"], (int, float)):
        scaled["damage"] = max(0, round(scaled["damage"] * m["enemy_damage"]))
    return scaled


def scale_xp(amount: int) -> int:
    """Scale an XP (harvesting cycles) award for the active mode."""
    return max(0, round(amount * _mult()["xp_gain"]))


# Load defaults from disk at import (safe if file missing).
load()
