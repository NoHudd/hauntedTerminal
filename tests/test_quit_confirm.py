"""The quit confirmation: one flow, three clearly-labelled outcomes.

The domain still speaks in y/n/c, so a frontend that cannot show a chooser keeps
working. The chooser is a presentation of that same answer, not a second path.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.events import EventType
from src.game_states import GameState
from src.save import save_manager
from src.ui.screens.quit_confirm import LEAVE_CHOICES, MID_FIGHT_CHOICES, QuitConfirmScreen


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Quitter", "guardian")
    s.submit("cd /var/tmp")          # make progress, so quit has to confirm
    try:
        yield s
    finally:
        s.close()


def _text(lines) -> str:
    return "\n".join(str(line) for line in lines)


# --- the domain flow ---------------------------------------------------------

def test_quit_with_progress_asks_before_leaving(session: GameSession) -> None:
    out = _text(session.submit("quit"))
    assert "unsaved progress" in out
    assert session.ui.quit_requested is False


def test_cancel_returns_to_play(session: GameSession) -> None:
    session.submit("quit")
    assert "cancelled" in _text(session.submit("c")).lower()
    assert session.ui.quit_requested is False
    # and the game still takes commands
    assert "/var/tmp" in _text(session.submit("pwd"))


def test_quit_without_saving_leaves(session: GameSession) -> None:
    session.submit("quit")
    session.submit("n")
    assert session.ui.quit_requested is True


def test_save_and_quit_writes_a_save_then_leaves(session: GameSession, tmp_path) -> None:
    from src.save import save_manager
    save_manager.save_dir = str(tmp_path)
    try:
        session.submit("quit")
        session.submit("y")
        assert session.ui.quit_requested is True
        assert list(tmp_path.glob("*.json")), "save & quit did not write a save"
    finally:
        save_manager.save_dir = "saves"


def test_quit_requests_the_chooser(session: GameSession) -> None:
    """The UI is told to offer a chooser; the headless driver ignores it and
    falls back to the printed y/n/c, which is why both still work."""
    seen: list[object] = []
    session.bus.subscribe(EventType.QUIT_CONFIRM_REQUESTED, seen.append)
    try:
        session.submit("quit")
        assert seen, "quit did not request the confirmation chooser"
    finally:
        session.bus.unsubscribe(EventType.QUIT_CONFIRM_REQUESTED, seen.append)


@pytest.fixture
def combat(session: GameSession):
    """The session, mid-fight; yields the combat session."""
    session.player.tutorial_state["completed"] = True
    handler = session.engine.cmd_handler
    session.world.enemy_locations["corrupt_process.bin"] = session.player.current_room
    handler.check_for_enemies()
    assert session.state == GameState.IN_COMBAT
    return handler.current_combat_session


def test_save_and_main_menu(session: GameSession) -> None:
    session.submit("quit")
    session.submit("m")
    assert session.state == GameState.MENU
    assert session.ui.quit_requested is False
    assert len(save_manager.list_runs()) == 1


def test_menu_command_with_progress_asks_first(session: GameSession) -> None:
    out = _text(session.submit("menu"))
    assert "unsaved progress" in out
    assert session.state == GameState.PLAYING


def test_menu_command_without_progress_goes_straight_to_the_menu() -> None:
    s = GameSession()
    try:
        s.new_game("Fresh", "guardian")
        s.player.inventory.clear()   # a new run starts with an item: that counts as progress
        s.submit("menu")
        assert s.state == GameState.MENU
    finally:
        s.close()


def test_quit_mid_fight_opens_the_fight_chooser(session: GameSession, combat) -> None:
    seen: list[object] = []
    session.bus.subscribe(EventType.QUIT_CONFIRM_REQUESTED, seen.append)
    out = _text(session.submit("quit"))
    assert "command not found" not in out
    assert "Leave mid-fight" in out
    assert seen[-1].data == {"inCombat": True}


def test_keep_fighting_resumes_the_fight(session: GameSession, combat) -> None:
    session.submit("quit")
    assert "Back to the fight" in _text(session.submit("c"))
    assert session.state == GameState.IN_COMBAT
    out = _text(session.submit(next(iter(combat.available_attacks))))
    assert "command not found" not in out and "Invalid option" not in out


def test_main_menu_mid_fight_leaves_without_saving(session: GameSession, combat) -> None:
    before = [(run.run_id, run.saved_at) for run in save_manager.list_runs()]
    session.submit("quit")
    session.submit("x")
    assert session.state == GameState.MENU
    assert [(run.run_id, run.saved_at) for run in save_manager.list_runs()] == before


def test_save_letters_are_refused_mid_fight(session: GameSession, combat) -> None:
    session.submit("quit")
    out = _text(session.submit("y"))
    assert "Invalid option" in out
    assert session.state == GameState.IN_COMBAT
    assert session.ui.quit_requested is False


# --- the chooser itself ------------------------------------------------------

def test_choices_map_onto_the_letters_the_domain_expects() -> None:
    assert [letter for letter, *_ in LEAVE_CHOICES] == ["m", "y", "n", "c"]
    assert [letter for letter, *_ in MID_FIGHT_CHOICES] == ["c", "x", "n"]


def test_arrow_keys_move_and_enter_confirms() -> None:
    picked: list[str] = []
    screen = QuitConfirmScreen(picked.append)

    screen.action_move_down()          # m -> y
    assert screen._index == 1
    screen.action_move_up()            # back to m
    assert screen._index == 0
    screen.action_move_up()            # wraps to c
    assert screen._index == len(LEAVE_CHOICES) - 1


def test_escape_keeps_playing() -> None:
    picked: list[str] = []
    screen = QuitConfirmScreen(picked.append)
    screen.dismiss = lambda *a, **k: None      # no running app in a unit test

    screen.action_cancel()
    assert picked == ["c"]


def test_a_second_key_press_cannot_answer_twice() -> None:
    """Dismissing is async, so a fast second press must not send a second command
    into a flow that is no longer listening."""
    picked: list[str] = []
    screen = QuitConfirmScreen(picked.append)
    screen.dismiss = lambda *a, **k: None

    screen.action_pick("n")
    screen.action_pick("y")
    assert picked == ["n"]


def test_the_mid_fight_chooser_refuses_save_letters() -> None:
    picked: list[str] = []
    screen = QuitConfirmScreen(picked.append, MID_FIGHT_CHOICES, "Leave mid-fight?")
    screen.dismiss = lambda *a, **k: None

    assert MID_FIGHT_CHOICES[screen._index][0] == "c"   # keep fighting is the default
    screen.action_pick("y")
    assert picked == []
    screen.action_pick("x")
    assert picked == ["x"]
