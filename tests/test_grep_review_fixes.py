"""Beginner-facing fixes from the Phase 2 review: the grep lesson survives an
arrival fight and is taught in whichever grep room comes first; grep explains
swapped arguments, quoted phrases and cat-only flags; Tab completes grep;
Echo's remark about the log wall comes before the wall."""
import asyncio
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "weaver")
    session.player.tutorial_state["completed"] = True
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def _clear(s: GameSession, room: str) -> None:
    s.world.enemy_locations = {e: r for e, r in s.world.enemy_locations.items() if r != room}


def test_lesson_waits_until_the_room_is_safe(s: GameSession) -> None:
    flags = s.engine.cmd_handler.flags
    s.world.enemy_locations["glitched_process.tmp"] = "mnt_forest"
    s.player.current_room = "mnt_forest"
    s.ui.clear_console()
    flags.on_room_entered("mnt_forest")
    assert not s.world.flag_taught("mnt_forest")
    _clear(s, "mnt_forest")
    flags.after_command(in_combat=False)
    assert s.world.flag_taught("mnt_forest")
    assert "grep FLAG lost_user_log" in "\n".join(s.ui.drain())


def test_first_grep_room_teaches_even_without_its_own_lesson(s: GameSession) -> None:
    _clear(s, "usr_lib_arcane")
    s.player.current_room = "usr_lib_arcane"
    s.ui.clear_console()
    s.engine.cmd_handler.flags.on_room_entered("usr_lib_arcane")
    assert "grep FLAG catalog_db" in "\n".join(s.ui.drain())


def test_no_generic_lesson_once_grep_is_known(s: GameSession) -> None:
    s.world.mark_flag_captured("mnt_forest")
    _clear(s, "dev_null_void")
    s.player.current_room = "dev_null_void"
    s.ui.clear_console()
    s.engine.cmd_handler.flags.on_room_entered("dev_null_void")
    assert "grep FLAG kern_log" not in "\n".join(s.ui.drain())


def test_remark_comes_before_the_wall_and_names_the_command(s: GameSession) -> None:
    _clear(s, "usr_lib_arcane")
    s.player.current_room = "usr_lib_arcane"
    out = _out(s, "cat catalog_db")
    assert out.index("ECHO>") < out.index("catalog:")
    assert "grep FLAG catalog_db" in out[: out.index("catalog:")]


def test_grep_on_a_cat_flag_file_points_at_cat(s: GameSession) -> None:
    s.player.current_room = "root"
    out = _out(s, "grep FLAG motd")
    assert "cat motd" in out
    assert not s.world.flag_captured("root")


def test_case_tip_keeps_the_dot_on_hidden_files(s: GameSession) -> None:
    _clear(s, "var_dungeon")
    s.player.current_room = "var_dungeon"
    assert "grep -i FLAG .system_err_log" in _out(s, "grep FLAG .system_err_log")


def test_swapped_arguments_are_explained(s: GameSession) -> None:
    _clear(s, "dev_null_void")
    s.player.current_room = "dev_null_void"
    out = _out(s, "grep kern_log FLAG")
    assert "word first" in out and "grep FLAG kern_log" in out


def test_quoted_phrases_are_one_pattern(s: GameSession) -> None:
    _clear(s, "dev_null_void")
    s.player.current_room = "dev_null_void"
    out = _out(s, 'grep "something survived" kern_log')
    assert "FLAG{even_the_void_logs}" in out
    assert s.world.flag_captured("dev_null_void")


def test_tab_completes_grep_and_its_file(s: GameSession) -> None:
    from src.ui.command_suggester import CommandSuggester

    s.player.current_room = "dev_null_void"
    sug = CommandSuggester(get_player=lambda: s.player, get_world=lambda: s.world)
    assert asyncio.run(sug.get_suggestion("gr")) == "grep"
    assert asyncio.run(sug.get_suggestion("grep FLAG ke")) == "grep FLAG kern_log"
