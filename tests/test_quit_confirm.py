"""The quit confirmation: one flow, three clearly-labelled outcomes.

The domain still speaks in y/n/c, so a frontend that cannot show a chooser keeps
working. The chooser is a presentation of that same answer, not a second path.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.events import EventType
from src.ui.screens.quit_confirm import CHOICES, QuitConfirmScreen


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


# --- the chooser itself ------------------------------------------------------

def test_choices_map_onto_the_letters_the_domain_expects() -> None:
    assert [letter for letter, *_ in CHOICES] == ["y", "n", "c"]


def test_arrow_keys_move_and_enter_confirms() -> None:
    picked: list[str] = []
    screen = QuitConfirmScreen(picked.append)

    screen.action_move_down()          # y -> n
    assert screen._index == 1
    screen.action_move_up()            # back to y
    assert screen._index == 0
    screen.action_move_up()            # wraps to c
    assert screen._index == len(CHOICES) - 1


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

    screen.action_pick_quit()
    screen.action_pick_save()
    assert picked == ["n"]
