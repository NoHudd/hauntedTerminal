"""Starting the game clears the pre-game prompt; player-facing text never loses a
word to markup; command words are not names."""
from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
import yaml
from rich.style import Style
from textual.color import Color

from engine.api import GameSession
from src.game_states import GameState

_TAG = re.compile(r"(?<!\\)\[(/?)([^\[\]\n]*)\]")


def _swallowed(markup: str) -> list[str]:
    """Bracketed words the renderer would treat as a style tag and drop, e.g.
    the "[item]" in "use [item]"."""
    lost = []
    for closing, body in _TAG.findall(markup):
        if closing or not body.strip():
            continue
        try:
            Style.parse(body)
            continue
        except Exception:
            pass
        try:
            Color.parse(body)
            continue
        except Exception:
            lost.append(body)
    return lost


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tess", "guardian")
    s.player.tutorial_state["completed"] = True
    try:
        yield s
    finally:
        s.close()


def test_starting_the_game_replaces_the_pre_game_prompt(session: GameSession) -> None:
    session.ui.update_output("Want a quick tutorial? (yes / skip)")
    session.engine.start_game()
    out = "\n".join(session.ui.drain())
    assert "Want a quick tutorial" not in out
    assert session.world.get_room(session.player.current_room).name in out


def test_tutorial_text_keeps_every_word() -> None:
    hints = yaml.safe_load(open("data/tutorial_hints.yaml"))
    lost = {hint_id: _swallowed(text) for hint_id, text in hints.items()}
    assert not {k: v for k, v in lost.items() if v}


def test_command_output_keeps_every_word(session: GameSession) -> None:
    commands = ["help", "ps", "use", "take", "cat", "drop", "examine", "talk", "equip", "find"]
    lost = {
        command: words
        for command in commands
        if (words := [
            w for line in session.submit(command) if isinstance(line, str)
            for w in _swallowed(line)
        ])
    }
    assert not lost, f"words the renderer would drop, by command: {lost}"


def test_command_words_are_not_names() -> None:
    s = GameSession()
    try:
        s.engine.state_manager.set_state(GameState.TUTORIAL_NAME_INPUT, emit_event=False)
        s.engine.selected_class = "guardian"
        for name in ["quit", "ls", "Help", " yes "]:
            s.engine._handle_tutorial_name_input(name)
            assert s.engine.player is None, f"{name!r} was accepted as a name"
        s.engine._handle_tutorial_name_input("Tess")
        assert s.engine.player is not None and s.engine.player.name == "Tess"
    finally:
        s.close()
