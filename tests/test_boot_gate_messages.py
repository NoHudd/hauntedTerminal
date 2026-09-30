"""The gate tells a beginner exactly what opens it."""
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


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_cd_boot_says_how_many_flags(s: GameSession) -> None:
    s.world.mark_flag_captured("root")
    out = _out(s, "cd /boot")
    assert "Permission denied" in out
    assert "11 flags" in out and "You have 1" in out and "tree" in out


def test_paths_through_boot_are_gated(s: GameSession) -> None:
    assert "11 flags" in _out(s, "cd /boot/kernel")


def test_tree_marks_boot_with_its_flag_count(s: GameSession) -> None:
    out = _out(s, "tree")
    boot_line = next(line for line in out.splitlines() if "boot/" in line)
    assert "11 flags (0/11)" in boot_line
