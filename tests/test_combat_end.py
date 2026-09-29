"""The game's reaction to a fight ending is one direct call chain
(CombatSession -> CommandHandler.end_combat -> engine hook), not a set of
COMBAT_ENDED listeners whose order depended on subscription order."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.events import EventType
from src.game_states import GameState
from src.game_world import TUTORIAL_ENEMY
from src.tutorial_coach import TutorialCoach


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Fighter", "guardian")
    s.player.tutorial_state["completed"] = True
    try:
        yield s
    finally:
        s.close()


def _fight_in_root(s: GameSession, lethal: bool = False) -> None:
    s.world.spawn_tutorial_enemy("root")
    if lethal:
        s.player.health = 1
    s.submit("cd root")
    session = s.engine.cmd_handler.current_combat_session
    assert session is not None and s.state == GameState.IN_COMBAT
    if lethal:
        session.enemy_damage = 10**6
        session.enemy_health = 10**6


def test_only_observers_listen_to_combat_events(session: GameSession) -> None:
    for et in (EventType.COMBAT_STARTED, EventType.COMBAT_ENDED):
        owners = {type(getattr(cb, "__self__", None)) for cb in session.bus._listeners.get(et, [])}
        assert owners <= {TutorialCoach}, f"{et.name} has game-rule listeners: {owners}"


def test_fleeing_returns_you_to_the_previous_room(session: GameSession) -> None:
    _fight_in_root(session)
    session.submit("flee")
    assert session.engine.cmd_handler.current_combat_session is None
    assert session.state == GameState.PLAYING
    assert session.player.current_room == "home_grove"
    assert TUTORIAL_ENEMY in session.world.fled_enemies.get("root", [])


def test_dying_ends_the_run(session: GameSession) -> None:
    seen: list[dict] = []
    session.bus.subscribe(EventType.GAME_OVER, lambda e: seen.append(e.data))
    _fight_in_root(session, lethal=True)
    attack = next(iter(session.engine.cmd_handler.current_combat_session.available_attacks))
    session.submit(attack)

    assert session.state == GameState.GAME_OVER
    assert session.engine.cmd_handler.flow.in_game_over_mode is True
    assert [d.get("reason") for d in seen] == ["defeat"]


def test_a_kill_is_announced_once_and_removes_the_enemy(
    session: GameSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.combat.rng.randint", lambda a, b: a)  # the attack lands
    kills: list[dict] = []
    session.bus.subscribe(EventType.ENEMY_DEFEATED, lambda e: kills.append(e.data))
    _fight_in_root(session)
    combat = session.engine.cmd_handler.current_combat_session
    combat.enemy_health = 1
    session.submit(next(iter(combat.available_attacks)))

    assert [k["enemy_id"] for k in kills] == [TUTORIAL_ENEMY]
    assert TUTORIAL_ENEMY not in session.world.get_enemies_in_room("root")
    assert TUTORIAL_ENEMY in session.engine.cmd_handler.loot.awarded
