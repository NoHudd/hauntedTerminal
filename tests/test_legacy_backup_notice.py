"""A spent Legacy Backup says so, and trying to use one mid-fight explains
that it works on its own instead of a flat "cannot be used"."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.game_states import GameState


@pytest.fixture
def fight() -> Iterator[GameSession]:
    s = GameSession()
    try:
        s.new_game("Rob", "weaver")
        s.player.tutorial_state["completed"] = True
        s.world.spawn_tutorial_enemy("root")
        yield s
    finally:
        s.close()


def _give_backup(s: GameSession, key: str = "legacy_backup") -> None:
    # A second copy lives under a suffixed key, as loot drops add it.
    s.player.add_to_inventory(key, s.world.get_item("legacy_backup"))


def _start(s: GameSession) -> str:
    s.submit("cd root")
    combat = s.engine.cmd_handler.current_combat_session
    assert combat is not None and s.state == GameState.IN_COMBAT
    combat.enemy_health = 10**6
    combat.enemy_damage = 10**6
    return next(iter(combat.available_attacks))


def test_last_backup_spent_says_none_are_left(fight: GameSession) -> None:
    _give_backup(fight)
    attack = _start(fight)
    out = "\n".join(fight.submit(attack))
    assert "restores you from a snapshot" in out
    assert "spent" in out and "no backups left" in out.lower()


def test_a_second_backup_is_counted(fight: GameSession) -> None:
    _give_backup(fight)
    _give_backup(fight, "legacy_backup_2")
    attack = _start(fight)
    out = "\n".join(fight.submit(attack))
    assert "spent" in out and "1 backup left" in out


def test_using_a_backup_mid_fight_explains_it_is_automatic(fight: GameSession) -> None:
    _give_backup(fight)
    _start(fight)
    out = "\n".join(fight.submit("use legacy_backup"))
    assert "cannot be used in combat" not in out
    assert "works automatically" in out
    assert fight.player.has_item("legacy_backup")
    assert fight.state == GameState.IN_COMBAT
