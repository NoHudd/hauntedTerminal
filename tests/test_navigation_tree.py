"""cd behaves like a shell, and permission gates the whole path.

Movement is no longer restricted by the exit graph — you may cd to any path you
can reach. What restricts you is permission, on every ancestor as well as the
destination, which is what makes a sealed /usr also seal /usr/games.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Nav", "guardian")
    try:
        yield s
    finally:
        s.close()


def _text(lines) -> str:
    return "\n".join(str(line) for line in lines)


def _goto(session: GameSession, room_id: str) -> None:
    """Move without going through cd, so a test can set up anywhere."""
    session.player.current_room = room_id


# --- free movement -----------------------------------------------------------

def test_cd_reaches_a_room_that_is_not_an_exit(session: GameSession) -> None:
    """/var/tmp is not in /home's exit list; a real shell would still go there."""
    assert "deprecated_dir" not in session.world.get_exits("home_grove")
    session.submit("cd /var/tmp")
    assert session.player.current_room == "deprecated_dir"


def test_cd_with_no_argument_goes_home(session: GameSession) -> None:
    _goto(session, "deprecated_dir")
    session.submit("cd")
    assert session.player.current_room == "home_grove"


def test_cd_dot_dot_walks_to_the_parent(session: GameSession) -> None:
    _goto(session, "deprecated_dir")          # /var/tmp
    session.submit("cd ..")
    assert session.player.current_room == "var_dungeon"


def test_cd_dot_stays_put(session: GameSession) -> None:
    session.submit("cd .")
    assert session.player.current_room == "home_grove"


def test_relative_path_resolves_against_the_current_directory(
    session: GameSession,
) -> None:
    _goto(session, "var_dungeon")
    session.submit("cd tmp")
    assert session.player.current_room == "deprecated_dir"


def test_unknown_path_reports_no_such_file(session: GameSession) -> None:
    out = _text(session.submit("cd /nope"))
    assert "No such file or directory" in out
    assert session.player.current_room == "home_grove"


# --- permission --------------------------------------------------------------

def test_sealed_directory_is_refused_and_names_its_key(session: GameSession) -> None:
    out = _text(session.submit("cd /usr"))
    assert "Permission denied" in out
    assert "lib_key" in out
    assert session.player.current_room == "home_grove"


def test_a_sealed_parent_seals_its_children(session: GameSession) -> None:
    """/usr/games is not locked itself; /usr above it is."""
    assert not session.world.get_room_state("usr_share_games").get("locked", False)

    out = _text(session.submit("cd /usr/games"))
    assert "Permission denied" in out
    assert "/usr" in out, "the denial should name the ancestor that blocked it"
    assert session.player.current_room == "home_grove"


def test_holding_the_key_opens_the_door_on_entry(session: GameSession) -> None:
    key = session.world.get_item("lib_key")
    session.player.add_to_inventory("lib_key", key)

    session.submit("cd /usr")
    assert session.player.current_room == "usr_lib_arcane"


def test_key_opens_an_ancestor_so_the_child_is_reachable(session: GameSession) -> None:
    session.player.add_to_inventory("lib_key", session.world.get_item("lib_key"))

    session.submit("cd /usr/games")
    assert session.player.current_room == "usr_share_games"


def test_undiscovered_directory_looks_like_it_does_not_exist(
    session: GameSession,
) -> None:
    """A hidden room is indistinguishable from a missing one — which is exactly
    what makes `ls -a` worth learning."""
    assert session.world.get_room_state("archive")["hidden"] is True
    out = _text(session.submit("cd /var/backups"))
    assert "No such file or directory" in out


def test_a_guardian_with_the_key_may_enter_the_tower(session: GameSession) -> None:
    """The trials are open to every class now; only the key gates them."""
    session.player.add_to_inventory("opt_key", session.world.get_item("opt_key"))
    session.world.discover_room("opt_mage_tower")  # /opt is hidden until found
    session.world.unlock_room("opt_mage_tower")
    allowed, _ = session.world.check_access("opt_mage_tower", session.player)
    assert allowed
