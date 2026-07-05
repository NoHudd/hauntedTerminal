"""Headless engine tests.

Prove the engine runs, accepts commands, and never crashes on a scripted or
randomised playthrough — with no Textual App. Formalises the manual "does it
still work" check and a lite version of the playtest-simulator.

Note: event_bus and state_manager are process-global singletons, so each test
uses a fresh GameSession and closes it (unsubscribing its handlers) to stay
isolated.
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.game_states import GameState

CLASSES = ["guardian", "weaver", "shaman"]


def test_headless_ui_satisfies_protocol() -> None:
    # The headless adapter must implement every UIProtocol method so it can
    # stand in for the real UI (keeps the abstraction honest).
    from engine.headless import HeadlessUI
    from src.ui.ui_interface import UIProtocol

    ui = HeadlessUI()
    assert UIProtocol is not None  # imported contract we check against
    for name in (
        "run", "shutdown", "update_output", "append_output", "display_message",
        "update_output_renderable", "update_inventory", "update_stats",
        "update_exits", "update_player_name", "clear_console", "display_game_over",
    ):
        assert callable(getattr(ui, name, None)), f"HeadlessUI missing {name}"


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    try:
        yield s
    finally:
        s.close()


@pytest.mark.parametrize("player_class", CLASSES)
def test_new_game_boots_each_class(session: GameSession, player_class: str) -> None:
    # Startup room/stat rendering flows through the event bus -> panels, not
    # update_output, so HeadlessUI captures no text here by design; assert the
    # engine reached a valid playing state instead.
    session.new_game("Tester", player_class)
    assert session.state == GameState.PLAYING
    assert session.player.player_class == player_class
    assert session.player.max_health > 0
    assert session.player.total_damage > 0


def test_basic_commands_produce_output(session: GameSession) -> None:
    session.new_game("Tester", "guardian")
    for cmd in ("ls", "pwd", "inventory", "help", "map"):
        out = session.submit(cmd)
        assert out, f"'{cmd}' produced no output"


def test_movement_changes_room(session: GameSession) -> None:
    session.new_game("Tester", "guardian")
    assert session.player.current_room == "home_grove"
    session.submit("cd root")
    assert session.player.current_room == "root"


@pytest.mark.parametrize("player_class", CLASSES)
def test_random_walk_never_crashes(session: GameSession, player_class: str) -> None:
    """Fuzz: drive a stream of plausible commands and assert the engine never
    raises and never leaves a sane state. Deterministic via a fixed seed."""
    rng = random.Random(1234)
    session.new_game("Tester", player_class)

    verbs = ["ls", "pwd", "inventory", "map", "journal", "keys", "help", "examine"]
    directions = [
        "root", "home_grove", "var_dungeon", "bin_armory", "mnt_forest",
        "usr_lib_arcane", "back",
    ]
    valid_states = {
        GameState.PLAYING,
        GameState.IN_COMBAT,
        GameState.GAME_OVER,
    }

    for _ in range(60):
        if rng.random() < 0.5:
            cmd = f"cd {rng.choice(directions)}"
        else:
            cmd = rng.choice(verbs)
        # Must not raise. Combat may start/end; that is fine.
        session.submit(cmd)
        assert session.state in valid_states, f"bad state after '{cmd}': {session.state}"
        if session.state == GameState.GAME_OVER:
            break
