"""The recap counts flags and ranks the run; a full clear earns an epilogue."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.events import EventType
from src.ui.endings import FULL_CLEAR_EPILOGUE, build_recap, rank_for


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "weaver")
    try:
        yield session
    finally:
        session.close()


def _won(s: GameSession) -> dict:
    events: list[dict] = []
    s.bus.subscribe(EventType.GAME_WON, lambda e: events.append(e.data))
    s.engine.cmd_handler.flow.win_game()
    return events[-1]


def test_rank_ladder() -> None:
    assert rank_for(11, 13, 0, 5) == "Operator"
    assert rank_for(12, 13, 0, 5) == "Sysadmin"
    assert rank_for(13, 13, 4, 5) == "Sysadmin Supreme"
    assert rank_for(13, 13, 5, 5) == "root"


def test_recap_shows_flags_and_rank(s: GameSession) -> None:
    for rid in ("root", "home_grove"):
        s.world.mark_flag_captured(rid)
    stats = _won(s)["stats"]
    assert (stats["flags"], stats["flags_total"]) == (2, 13)
    recap = build_recap(stats)
    assert "Flags 2/13" in recap and "Secrets 0/5" in recap and "rank:" in recap


def test_full_clear_gets_the_epilogue(s: GameSession) -> None:
    for rid, room in s.world.rooms.items():
        if room.flag is not None and not room.hidden:
            s.world.mark_flag_captured(rid)
    assert FULL_CLEAR_EPILOGUE in _won(s)["sections"]


def test_partial_clear_gets_no_epilogue(s: GameSession) -> None:
    s.world.mark_flag_captured("root")
    assert FULL_CLEAR_EPILOGUE not in _won(s)["sections"]
