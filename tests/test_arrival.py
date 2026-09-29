"""Arrival rules run from a direct call (CommandHandler.arrive), not from the
ROOM_ENTERED event, which is now a UI notification only."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.events import EventType
from src.game_world import TUTORIAL_ENEMY


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Walker", "guardian")
    s.player.tutorial_state["completed"] = True
    try:
        yield s
    finally:
        s.close()


def test_cd_shows_the_room_before_the_fight_starts(session: GameSession) -> None:
    session.world.spawn_tutorial_enemy("root")
    text = "\n".join(session.submit("cd root"))

    room_name = session.world.get_room("root").name
    assert session.engine.cmd_handler.current_combat_session is not None
    assert text.index(room_name) < text.index("HOSTILE ENTITY DETECTED")


def test_a_room_refresh_does_not_start_a_fight(session: GameSession) -> None:
    session.world.spawn_tutorial_enemy(session.player.current_room)
    session.bus.emit_event(EventType.ROOM_ENTERED, {}, "test")
    assert session.engine.cmd_handler.current_combat_session is None


def test_arriving_brings_back_an_enemy_you_fled_from(session: GameSession) -> None:
    handler = session.engine.cmd_handler
    session.world.mark_enemy_as_fled(TUTORIAL_ENEMY, "root")
    session.submit("cd root")
    assert handler.current_combat_session is not None
    assert handler.current_combat_session.enemy_id == TUTORIAL_ENEMY
