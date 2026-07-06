"""Difficulty-mode tests (difficulty-sim Part A).

Modes scale enemy HP/damage and XP; multipliers come from data/difficulty.yaml.
"""
from __future__ import annotations

import pytest

from src import difficulty


@pytest.fixture(autouse=True)
def _reset_mode():
    difficulty.load()
    difficulty.set_mode("medium")
    yield
    difficulty.set_mode("medium")


def _enemy_hp(mode: str) -> int:
    difficulty.set_mode(mode)
    return difficulty.scale_enemy({"health": 100, "damage": 10})["health"]


def test_enemy_hp_is_ordered_easy_medium_hard() -> None:
    # The tuner may move exact multipliers, but the mode ordering must hold:
    # easy enemies are the frailest, hard the toughest.
    assert _enemy_hp("easy") <= _enemy_hp("medium") <= _enemy_hp("hard")


def test_easy_gives_more_xp_than_hard() -> None:
    difficulty.set_mode("easy")
    easy_xp = difficulty.scale_xp(50)
    difficulty.set_mode("hard")
    hard_xp = difficulty.scale_xp(50)
    assert easy_xp >= hard_xp


def test_easy_is_not_tougher_than_hard() -> None:
    # Aggregate toughness (HP as proxy) must not invert between the extremes.
    assert _enemy_hp("easy") <= _enemy_hp("hard")


def test_scale_enemy_does_not_mutate_input() -> None:
    difficulty.set_mode("hard")
    original = {"health": 100, "damage": 10}
    difficulty.scale_enemy(original)
    assert original == {"health": 100, "damage": 10}


def test_get_enemy_applies_difficulty() -> None:
    from engine.api import GameSession

    s = GameSession()
    try:
        s.new_game("T", "guardian")
        eid = next(iter(s.world.enemies))
        difficulty.set_mode("easy")
        easy = s.world.get_enemy(eid, "guardian")["health"]
        difficulty.set_mode("hard")
        hard = s.world.get_enemy(eid, "guardian")["health"]
        assert hard > easy
    finally:
        difficulty.set_mode("medium")
        s.close()


def test_invalid_mode_falls_back_to_medium() -> None:
    difficulty.set_mode("nonsense")
    assert difficulty.current_mode() == "medium"
