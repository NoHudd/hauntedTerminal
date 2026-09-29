"""The post-combat tutorial leg: ls -a reveals .bash_profile, cat fires the
memory-restore checkpoint, and only then does the tutorial move on to ps.

Assertions target s.ui.hints (which step fired), not Echo's wording.
"""
from collections.abc import Iterator

import pytest

from engine.api import GameSession

_POST_COMBAT_STATE = {
    "first_ls": True,
    "took_weapon": True,
    "equipped_weapon": True,
    "combat_action_taken": True,
}


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("t", "guardian")
    s.player.tutorial_state.update(_POST_COMBAT_STATE)
    try:
        yield s
    finally:
        s.close()


def _fired(session: GameSession) -> list[str]:
    return [hint["hint_id"] for hint in session.ui.hints]


def test_plain_ls_does_not_advance_past_the_hidden_file_step(session: GameSession) -> None:
    session.ui.hints.clear()
    session.submit("ls")
    assert session.player.tutorial_state.get("ls_a_used", False) is False
    assert "step_hidden" not in _fired(session)


def test_ls_a_fires_the_hidden_file_hint(session: GameSession) -> None:
    session.ui.hints.clear()
    session.submit("ls -a")
    assert session.player.tutorial_state["ls_a_used"] is True
    assert "step_hidden" in _fired(session)


def test_cat_story_beat_fires_the_checkpoint_hint(session: GameSession) -> None:
    session.submit("ls -a")
    session.ui.hints.clear()
    session.submit("cat bash_profile")
    assert session.player.tutorial_state["lore_read"] is True
    assert "step_cat" in _fired(session)


def test_plain_lore_read_is_not_a_checkpoint(session: GameSession) -> None:
    """readme_txt_corrupt has no story_flag: reading it must not count as the
    checkpoint step."""
    session.submit("ls -a")
    session.ui.hints.clear()
    session.submit("cat readme_txt_corrupt")
    assert session.player.tutorial_state.get("lore_read", False) is False


def test_ps_does_not_advance_before_the_checkpoint(session: GameSession) -> None:
    session.submit("ls -a")
    session.ui.hints.clear()
    session.submit("ps")
    assert session.player.tutorial_state.get("ps_used", False) is False


def test_ps_advances_after_the_checkpoint(session: GameSession) -> None:
    session.submit("ls -a")
    session.submit("cat bash_profile")
    session.ui.hints.clear()
    session.submit("ps")
    assert session.player.tutorial_state["ps_used"] is True
    assert "step_ps" in _fired(session)


def test_current_step_walks_the_new_leg(session: GameSession) -> None:
    coach = session.engine.cmd_handler.tutorial
    ts = session.player.tutorial_state
    assert coach.current_step() == "step5_postcombat"
    ts["ls_a_used"] = True
    assert coach.current_step() == "step_hidden"
    ts["lore_read"] = True
    assert coach.current_step() == "step_cat"
    ts["ps_used"] = True
    assert coach.current_step() == "step_ps"
