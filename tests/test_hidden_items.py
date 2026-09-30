"""Items marked `hidden: true` stay out of plain `ls` and appear with `ls -a`.

The data has always declared this intent ("Requires ls -a to see") but only
rooms honored it. bash_profile is the canary: the tutorial's checkpoint step
depends on `ls -a` actually revealing it.
"""
from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("t", "guardian")
    try:
        yield s
    finally:
        s.close()


def _out(session: GameSession, cmd: str) -> str:
    return "\n".join(str(line) for line in session.submit(cmd))


def test_plain_ls_omits_hidden_items(session: GameSession) -> None:
    out = _out(session, "ls")
    assert "bash_profile" not in out
    assert "readme_txt_corrupt" not in out  # every story file is hidden
    # Visible items in the same room still list.
    assert "segfault_shield" in out


def test_ls_a_reveals_hidden_items(session: GameSession) -> None:
    out = _out(session, "ls -a")
    assert "bash_profile" in out


def test_cat_reads_a_hidden_item_by_name(session: GameSession) -> None:
    """Like real Unix: a hidden file is listable only with -a but always
    readable by name."""
    out = _out(session, "cat bash_profile")
    assert "Sysadmin Spirit" in out


def test_ls_a_shows_hidden_files_with_their_dot(session: GameSession) -> None:
    """What you see is what you type: a hidden file lists as a dotfile, and its
    hint names it the same way, since completion only offers it after a dot."""
    out = _out(session, "ls -a")
    assert ".bash_profile" in out
    assert "cat .bash_profile" in out


def test_echo_points_at_the_dotted_name(session: GameSession) -> None:
    from src.data_loader import load_tutorial_hints

    assert ".bash_profile" in load_tutorial_hints()["step_hidden"]
