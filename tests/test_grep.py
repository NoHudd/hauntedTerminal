"""grep: real-grep behaviour with beginner-friendly errors."""
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
    session.player.current_room = "dev_null_void"
    session.world.enemy_locations = {
        e: r for e, r in session.world.enemy_locations.items() if r != "dev_null_void"
    }
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_grep_prints_only_matching_lines_and_captures(s: GameSession) -> None:
    out = _out(s, "grep FLAG kern_log")
    assert "FLAG{even_the_void_logs}" in out
    assert "discarded" not in out
    assert s.world.flag_captured("dev_null_void")


def test_missing_arguments_show_usage(s: GameSession) -> None:
    assert "Usage: grep" in _out(s, "grep")
    assert "Usage: grep" in _out(s, "grep FLAG")


def test_unknown_file_is_named_with_a_suggestion(s: GameSession) -> None:
    out = _out(s, "grep FLAG kern_lgo")
    assert "No such file" in out and "kern_log" in out


def test_wrong_case_explains_and_suggests_i(s: GameSession) -> None:
    out = _out(s, "grep flag kern_log")
    assert "case" in out.lower() and "grep -i" in out
    assert not s.world.flag_captured("dev_null_void")


def test_dash_i_ignores_case(s: GameSession) -> None:
    assert "FLAG{even_the_void_logs}" in _out(s, "grep -i flag kern_log")


def test_dash_n_numbers_lines(s: GameSession) -> None:
    out = _out(s, "grep -n FLAG kern_log")
    assert "267:" in out  # 400 lines, flag at index 266 → line 267


def test_huge_match_is_capped(s: GameSession) -> None:
    out = _out(s, "grep kernel kern_log")
    assert "more matching lines" in out
    assert out.count("kernel:") <= 40


def test_pattern_that_misses_the_flag_does_not_capture(s: GameSession) -> None:
    _out(s, "grep hangup kern_log")
    assert not s.world.flag_captured("dev_null_void")


def test_flag_hidden_by_the_cap_is_not_captured(s: GameSession) -> None:
    """'kernel' matches all 400 lines; the flag line (267) is past the 40 shown."""
    _out(s, "grep kernel kern_log")
    assert not s.world.flag_captured("dev_null_void")


def test_quotes_and_forgiving_file_names(s: GameSession) -> None:
    assert "FLAG{even_the_void_logs}" in _out(s, "grep 'FLAG' kern.log")


def test_man_grep_exists(s: GameSession) -> None:
    assert "print lines that match" in _out(s, "man grep")
