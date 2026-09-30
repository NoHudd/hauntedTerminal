"""journal and tree show flag progress."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_journal_counts_and_lists_captured_flags(s: GameSession) -> None:
    s.player.current_room = "root"
    s.submit("cat motd")
    out = _out(s, "journal")
    assert "Flags 1/13 · Secrets 0/5" in out
    assert "FLAG{cat_reads_files}" in out


def test_tree_shows_counts_and_marks_captured_rooms(s: GameSession) -> None:
    s.player.current_room = "root"
    s.submit("cat motd")
    out = _out(s, "tree")
    assert "Flags 1/13 · Secrets 0/5" in out
    root_line = next(line for line in out.splitlines() if "Root" in line)
    assert "⚑" in root_line
    assert "⚑ flag captured" in out
