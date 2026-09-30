"""`cd` + Tab completes the doors `ls` shows — never a hidden room before
`ls -a` finds it, nor a locked door before its key reveals it."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.ui.command_suggester import CommandSuggester


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    session.player.current_room = "root"
    try:
        yield session
    finally:
        session.close()


def _tab(s: GameSession, typed: str) -> str | None:
    suggester = CommandSuggester(get_player=lambda: s.player, get_world=lambda: s.world)
    return asyncio.run(suggester.get_suggestion(typed))


def test_cd_completes_a_visible_door(s: GameSession) -> None:
    assert _tab(s, "cd /b") == "cd /bin"
    assert _tab(s, "cd /h") == "cd /home"


def test_locked_door_stays_out_until_its_key_reveals_it(s: GameSession) -> None:
    assert _tab(s, "cd /u") is None
    s.world.reveal_doors("lib_key")
    assert _tab(s, "cd /u") == "cd /usr"


def test_hidden_room_stays_out_until_discovered(s: GameSession) -> None:
    assert _tab(s, "cd /var/b") is None
    s.world.discover_room("archive")
    assert _tab(s, "cd /var/b") == "cd /var/backups"


def test_room_ids_follow_the_same_rule(s: GameSession) -> None:
    assert _tab(s, "cd bin_") == "cd bin_armory"
    assert _tab(s, "cd usr_") is None
    assert _tab(s, "cd arch") is None
