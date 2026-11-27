"""`find` walks the directory tree like the real one: every path under the
start that the player could know about, filtered by `-name` glob. Sealed
directories answer `Permission denied`; hidden rooms and doors whose key has
not revealed them do not exist. `find /dev -name null` still answers once the
Sudo Privileges Badge reveals /dev."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    try:
        yield session
    finally:
        session.close()


def _find(s: GameSession, args: str) -> list[str]:
    """find's own output (an ECHO nudge may follow it)."""
    return str(s.submit(f"find {args}".strip())[0]).splitlines()


def _found(s: GameSession, args: str) -> list[str]:
    """The paths, without the errors find prints along the way."""
    return [line for line in _find(s, args) if not line.startswith("find:")]


def test_name_matches_files_and_directories_by_glob(s: GameSession) -> None:
    assert _found(s, "/ -name motd") == ["/motd"]
    assert _found(s, "/ -name 'mo*'") == ["/motd"]  # quotes are the shell's, not the name
    assert _found(s, "/ -name tmp") == ["/var/tmp"]
    assert "/var/.system_err_log" in _found(s, '/ -name "*_log"')  # dotfiles too


def test_bare_find_walks_the_current_directory_including_dotfiles(s: GameSession) -> None:
    lines = _find(s, "")  # from /home, same as `find .`
    assert lines[0] == "."
    assert "./.bash_profile" in lines and "./segfault_shield" in lines


def test_sealed_directories_deny_and_hidden_ones_do_not_exist(s: GameSession) -> None:
    lines = _find(s, "/")
    assert "/boot" in lines and "find: '/boot': Permission denied" in lines
    assert "/var/backups" not in "\n".join(lines)  # hidden until `ls -a` in /var
    assert "/etc" not in lines  # locked door, no key yet: not even its name
    assert _find(s, "/nowhere") == ["find: '/nowhere': No such file or directory"]


def test_bad_arguments_explain_themselves(s: GameSession) -> None:
    assert _find(s, "/ -name") == ["find: missing argument to '-name'"]
    assert _find(s, "/ -type f") == ["find: unknown predicate '-type'"]


def test_hidden_dev_is_not_found(s: GameSession) -> None:
    assert _find(s, "/dev -name null") == ["find: '/dev': No such file or directory"]


def test_revealed_dev_is_found_from_anywhere(s: GameSession) -> None:
    s.world.reveal_doors("sudo_privileges_badge")
    s.player.current_room = "root"
    assert "/dev/null" in _find(s, "/dev -name null")
