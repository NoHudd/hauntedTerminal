"""man, tree, whoami, echo, clear — the commands that exist to teach the real thing."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.commands import build_registry
from src.commands.shell import MANPAGES


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Ada", "shaman")
    try:
        yield s
    finally:
        s.close()


def _text(lines) -> str:
    return "\n".join(str(line) for line in lines)


# --- man ---------------------------------------------------------------------

def test_every_documented_command_is_a_real_verb() -> None:
    """A manual page for something you cannot type would be a lie."""
    registry = build_registry()
    for name in MANPAGES:
        assert name in registry, f"man {name} documents a command that does not exist"


@pytest.mark.parametrize("command", sorted(MANPAGES))
def test_man_page_has_the_standard_sections(command: str, session: GameSession) -> None:
    out = _text(session.submit(f"man {command}"))
    for section in ("NAME", "SYNOPSIS", "DESCRIPTION", "IN THIS FILESYSTEM"):
        assert section in out, f"man {command} is missing {section}"
    assert command.upper() in out


def test_man_with_no_argument_lists_the_pages(session: GameSession) -> None:
    out = _text(session.submit("man"))
    assert "ls" in out and "cd" in out


def test_man_distinguishes_game_verbs_from_unix(session: GameSession) -> None:
    """`take` is a real verb here but not a real command, and saying so is the
    honest answer rather than inventing a take(1)."""
    out = _text(session.submit("man take"))
    assert "not of Unix" in out or "No manual entry" in out


def test_man_on_nonsense_reports_no_entry(session: GameSession) -> None:
    assert "No manual entry" in _text(session.submit("man frobnicate"))


# --- tree --------------------------------------------------------------------

def test_tree_shows_hierarchy_and_your_position(session: GameSession) -> None:
    out = _text(session.submit("tree"))
    assert "home/" in out
    assert "← you are here" in out


def test_tree_marks_sealed_directories(session: GameSession) -> None:
    session.world.reveal_doors("lib_key")  # seen, but the key is not held
    out = _text(session.submit("tree"))
    assert "🔒" in out, "a locked directory should be marked as sealed"
    assert "lib_key" in out, "and should name the key that opens it"


def test_tree_hides_undiscovered_directories(session: GameSession) -> None:
    assert session.world.get_room_state("mirror_sector")["hidden"] is True
    assert "self/" not in _text(session.submit("tree"))

    session.world.discover_room("mirror_sector")
    assert "self/" in _text(session.submit("tree"))


# --- the small ones ----------------------------------------------------------

def test_whoami_reports_name_and_class(session: GameSession) -> None:
    out = _text(session.submit("whoami"))
    assert "Ada" in out and "Shaman" in out


def test_echo_repeats_its_arguments(session: GameSession) -> None:
    assert "hello world" in _text(session.submit("echo hello world"))


def test_clear_empties_the_output(session: GameSession) -> None:
    assert _text(session.submit("clear")).strip() == ""
