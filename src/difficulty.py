#!/usr/bin/env python3
"""Difficulty modes: scale enemy HP/damage and XP by the active mode.

The player picks a mode (easy/medium/hard); multipliers live in
data/difficulty.yaml (calibrated by the sim tuner). Applied at two seams:
GameWorld.get_enemy (enemy stats) and combat XP award.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import yaml

from utils.debug_tools import debug_log

if TYPE_CHECKING:
    from engine.schema import Enemy

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


def set_mode_multipliers(mode: str, enemy_hp: float, enemy_damage: float,
                         xp_gain: float) -> None:
    """Override a mode's multipliers in memory (used by the sim tuner)."""
    _multipliers[mode] = {
        "enemy_hp": enemy_hp,
        "enemy_damage": enemy_damage,
        "xp_gain": xp_gain,
    }


def all_multipliers() -> dict[str, dict[str, float]]:
    """Current multipliers for all modes (copy)."""
    return {m: dict(_multipliers.get(m, _FALLBACK[m])) for m in MODES}


def scale_enemy(enemy: Enemy) -> Enemy:
    """Return a copy of an Enemy with HP/damage scaled for the active mode."""
    m = _mult()
    scaled = enemy.model_copy()
    scaled.health = max(1, round(enemy.health * m["enemy_hp"]))
    scaled.damage = max(0, round(enemy.damage * m["enemy_damage"]))
    return scaled


def scale_xp(amount: int) -> int:
    """Scale an XP (harvesting cycles) award for the active mode."""
    return max(0, round(amount * _mult()["xp_gain"]))


# Load defaults from disk at import (safe if file missing).
load()
