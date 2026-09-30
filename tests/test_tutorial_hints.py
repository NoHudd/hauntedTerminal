"""Tutorial text lives in data/tutorial_hints.yaml, not in Python.

The risk in moving it out is a silent gap: code asks for a step id that the YAML
does not define, and the player simply gets no instruction at the moment they
most need one. These tests pin the two halves together.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from engine.api import GameSession
from src.data_loader import load_class_data, load_tutorial_hints

# Every hint id the game asks for, read out of the source rather than restated,
# so adding a show_hint("stepN") call without YAML text fails here.
SRC = "\n".join(p.read_text() for p in Path("src").rglob("*.py"))

# Direct calls: tutorial.show_hint("step2")
_DIRECT = re.findall(r'show_hint\(\s*["\']([a-z0-9_]+)["\']', SRC)

# Indirect: handle_unknown_command re-shows whatever step the player is on, via
# tutorial.show_hint(current_step). Those ids are the string literals returned
# by TutorialCoach.current_step, so read them out of that function's body.
_STEP_FN = re.search(
    r"def current_step\(self\).*?(?=\n    def )", SRC, re.S
)
_INDIRECT = re.findall(r'return\s+["\']([a-z0-9_]+)["\']', _STEP_FN.group(0)) if _STEP_FN else []

REQUESTED_IDS = sorted(set(_DIRECT) | set(_INDIRECT))


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Ada", "weaver")
    try:
        yield s
    finally:
        s.close()


def _text(lines) -> str:
    return "\n".join(str(line) for line in lines)


def test_source_actually_requests_hints() -> None:
    assert REQUESTED_IDS, "found no show_hint call sites — check the regex"


def test_every_requested_hint_has_text() -> None:
    missing = sorted(set(REQUESTED_IDS) - set(load_tutorial_hints()))
    assert not missing, (
        f"code asks for tutorial steps {missing} but the YAML defines no text, "
        "so the player would get silence at those steps"
    )


def test_no_unreachable_hint_text() -> None:
    """The other direction: text nothing ever shows is dead content."""
    orphans = set(load_tutorial_hints()) - set(REQUESTED_IDS)
    assert not orphans, f"tutorial text never shown to anyone: {sorted(orphans)}"


def test_hints_render_without_leftover_placeholders(session: GameSession) -> None:
    handler = session.engine.cmd_handler
    broken = {}
    for hint_id in REQUESTED_IDS:
        handler.player.tutorial_state["completed"] = False
        session.ui.clear_console()
        handler.tutorial.show_hint(hint_id)
        out = _text(session.ui.drain())
        if not out.strip() or "{" in out:
            broken[hint_id] = out[:80]
    assert not broken, f"hints that rendered empty or with a placeholder left: {broken}"


def test_weapon_name_comes_from_class_data(session: GameSession) -> None:
    """It used to be a hardcoded class->weapon map in the handler, free to drift
    from classes.yaml. The weaver's starter weapon is the canary."""
    handler = session.engine.cmd_handler
    handler.player.tutorial_state["completed"] = False
    session.ui.clear_console()

    handler.tutorial.show_hint("step2")
    expected = load_class_data()["weaver"].starter_weapon

    assert expected in _text(session.ui.drain())


def test_explicit_item_name_wins(session: GameSession) -> None:
    """When the caller knows which weapon is actually on the floor, that is what
    the hint should name."""
    handler = session.engine.cmd_handler
    handler.player.tutorial_state["completed"] = False
    session.ui.clear_console()

    handler.tutorial.show_hint("step2", "a_specific_weapon")

    assert "a_specific_weapon" in _text(session.ui.drain())


def test_completed_marks_the_tutorial_done(session: GameSession) -> None:
    handler = session.engine.cmd_handler
    handler.player.tutorial_state["completed"] = False

    handler.tutorial.show_hint("completed")

    assert handler.player.tutorial_state["completed"] is True


def test_hints_are_silent_once_complete(session: GameSession) -> None:
    handler = session.engine.cmd_handler
    handler.player.tutorial_state["completed"] = True
    session.ui.clear_console()

    handler.tutorial.show_hint("step1")

    assert _text(session.ui.drain()).strip() == ""


def test_unknown_hint_id_is_survivable(session: GameSession) -> None:
    handler = session.engine.cmd_handler
    handler.player.tutorial_state["completed"] = False
    session.ui.clear_console()

    handler.tutorial.show_hint("no_such_step")  # must not raise

    assert _text(session.ui.drain()).strip() == ""


def test_navigation_hints_describe_the_real_ls_output(session: GameSession) -> None:
    """step6 used to point at a 'Where you can go' section that ls no longer has."""
    hints = load_tutorial_hints()
    assert "Where you can go" not in hints["step6"]
    assert "Directories" in hints["step6"]
