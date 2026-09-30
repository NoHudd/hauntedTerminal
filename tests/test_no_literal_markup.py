"""Rich `Text` objects print markup tags literally, so style must be passed to
`append`, not written as `[dim]...[/dim]` inside the string."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("t", "guardian")
    s.player.tutorial_state["completed"] = True
    try:
        yield s
    finally:
        s.close()


def _out(session: GameSession, cmd: str) -> str:
    return "\n".join(str(line) for line in session.submit(cmd))


@pytest.mark.parametrize("cmd", ["tree", "journal"])
def test_no_markup_tags_leak_into_the_text(session: GameSession, cmd: str) -> None:
    out = _out(session, cmd)
    for tag in ("[dim]", "[/dim]", "[italic]", "[/italic]"):
        assert tag not in out, f"{cmd} printed a literal {tag}"


def test_journal_with_a_memory_shows_progress_cleanly(session: GameSession) -> None:
    session.submit("cat .bash_profile")
    out = _out(session, "journal")
    assert "Progress:" in out and "[dim]" not in out
