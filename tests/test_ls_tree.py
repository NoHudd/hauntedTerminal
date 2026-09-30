"""ls lists a real directory, and -a is what reveals what is hidden."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Lister", "guardian")
    try:
        yield s
    finally:
        s.close()


def _ls(session: GameSession, args: str = "") -> str:
    return "\n".join(str(line) for line in session.submit(f"ls {args}".strip()))


def test_ls_lists_child_directories(session: GameSession) -> None:
    session.player.current_room = "root"
    session.world.reveal_doors("lib_key")  # /usr is a keyed door
    out = _ls(session)
    for child in ("bin/", "home/", "var/", "usr/"):
        assert child in out, f"{child} missing from the listing of /"


def test_ls_does_not_list_siblings_or_the_whole_world(session: GameSession) -> None:
    """From /home you should see /home's children, not every room in the game."""
    out = _ls(session)                     # /home has no children
    assert "var/" not in out
    assert "bin/" not in out


def test_ls_a_adds_dot_and_dotdot(session: GameSession) -> None:
    session.player.current_room = "root"
    plain, dashed = _ls(session), _ls(session, "-a")
    assert "./" not in plain and "../" not in plain
    assert "./" in dashed and "../" in dashed


def test_ls_a_reveals_a_hidden_child(session: GameSession) -> None:
    # / holds the hidden /root and has no enemies, so ls is not blocked by the
    # combat gate.
    session.player.current_room = "root"
    assert session.world.get_room_state("ghost_hidden")["hidden"] is True
    session.world.reveal_doors("system_badge")  # /root is also a keyed door

    assert "root/" not in _ls(session), "hidden child must not show without -a"

    revealed = _ls(session, "-a")
    assert "root/" in revealed
    assert session.world.get_room_state("ghost_hidden")["hidden"] is False


def test_discovery_requirement_gates_the_reveal(session: GameSession) -> None:
    """/proc/self is the Sudo Trial: an unfleeable boss. It stays invisible until
    something in the world has told the player the trial exists, so nobody can
    stumble into an unwinnable fight while exploring."""
    session.player.current_room = "proc_secrets"
    assert session.player.get_story_flag("sudo_quest_active") is False

    assert "self/" not in _ls(session, "-a"), (
        "ls -a revealed the trial before the player was told about it"
    )
    assert session.world.get_room_state("mirror_sector")["hidden"] is True

    # Talking to the Process Scheduler is what starts the quest.
    session.submit("talk scheduler_process.sys")
    assert session.player.get_story_flag("sudo_quest_active") is True

    assert "self/" in _ls(session, "-a")
    assert session.world.get_room_state("mirror_sector")["hidden"] is False


def test_gated_room_is_unreachable_until_revealed(session: GameSession) -> None:
    out = "\n".join(str(line) for line in session.submit("cd /proc/self"))
    assert "No such file or directory" in out
    assert session.player.current_room == "home_grove"


def test_ls_is_blocked_while_hostiles_are_present(session: GameSession) -> None:
    """Long-standing behaviour: you cannot survey a room you are fighting in."""
    room = session.world.enemy_locations[next(iter(session.world.enemy_locations))]
    session.player.current_room = room
    assert "COMBAT REQUIRED" in _ls(session)


def test_ls_l_shows_permission_bits(session: GameSession) -> None:
    session.player.current_room = "root"
    out = _ls(session, "-l")
    assert "drwxr-xr-x" in out, "an enterable directory should read as traversable"
    assert "dr--------" in out, "a sealed directory should read as unreadable"


def test_sealed_directories_are_still_listed(session: GameSession) -> None:
    """Once its key has revealed /usr you can see it exists even without the
    key in hand; you just cannot go in. (Before that it is invisible — see
    test_key_visibility.py.)"""
    session.player.current_room = "root"
    session.world.reveal_doors("lib_key")
    assert "usr/" in _ls(session)
