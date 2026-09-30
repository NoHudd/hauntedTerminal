"""Legacy Backup promises to revive you at 50% HP when you die. Nothing read
its auto_revive effect, so it never fired: a player died to the /boot boss
carrying one."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("t", "guardian")
    s.player.tutorial_state["completed"] = True
    s.world.item_locations["legacy_backup"] = s.player.current_room
    s.submit("take legacy_backup")
    assert s.player.has_item("legacy_backup")
    try:
        yield s
    finally:
        s.close()


def _out(session: GameSession, cmd: str) -> str:
    return "\n".join(str(line) for line in session.submit(cmd))


def test_a_lethal_hit_in_combat_is_survived_once(session: GameSession) -> None:
    h = session.engine.cmd_handler
    h.world.item_locations["segfault_shield"] = session.player.current_room
    session.player.tutorial_state["completed"] = False
    session.submit("take segfault_shield")
    session.submit("equip segfault_shield")
    session.submit("take cracked_firewall")
    session.submit("equip cracked_firewall")
    combat = h.current_combat_session
    assert combat is not None

    combat._enemy_turn = lambda: session.player.take_damage(9999)
    session.player.health = 1
    attack_id = next(iter(combat.available_attacks))
    combat.enemy_health = 10_000  # the fight must outlast this turn
    session.submit(attack_id)

    assert session.player.is_alive()
    assert session.player.health == session.player.max_health // 2
    assert not session.player.has_item("legacy_backup")
    assert h.current_combat_session is not None  # the fight goes on
    assert not h.flow.in_game_over_mode


def test_a_lethal_effect_outside_combat_is_survived(session: GameSession) -> None:
    h = session.engine.cmd_handler
    h.effects.execute_effect({"damage": 9999})
    assert session.player.is_alive()
    assert not session.player.has_item("legacy_backup")
    assert not h.flow.in_game_over_mode


def test_the_backup_is_single_use(session: GameSession) -> None:
    h = session.engine.cmd_handler
    h.effects.execute_effect({"damage": 9999})
    h.effects.execute_effect({"damage": 9999})
    assert not session.player.is_alive()


def test_revive_is_announced(session: GameSession) -> None:
    h = session.engine.cmd_handler
    session.ui.clear_console()
    h.effects.execute_effect({"damage": 9999})
    assert "Legacy Backup" in "\n".join(session.ui.drain())


def test_using_it_explains_that_it_is_automatic(session: GameSession) -> None:
    out = _out(session, "use legacy_backup")
    assert "cannot use" not in out.lower()
    assert "automatic" in out.lower()
    assert session.player.has_item("legacy_backup")
