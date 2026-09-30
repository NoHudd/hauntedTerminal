"""Capturing a chain flag hands out its key and reveals the door."""
import copy
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
    session.player.current_room = "mnt_forest"
    session.world.enemy_locations = {
        e: r for e, r in session.world.enemy_locations.items() if r != "mnt_forest"
    }
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_capturing_the_mnt_flag_grants_lib_key(s: GameSession) -> None:
    out = _out(s, "grep FLAG lost_user_log")
    assert s.player.has_item("lib_key")
    assert s.world.door_visible("usr_lib_arcane")
    assert "a new directory appeared" in out and "/usr" in out
    assert "cd /usr" in out


def test_first_key_gets_the_echo_lesson_once(s: GameSession) -> None:
    out = _out(s, "grep FLAG lost_user_log")
    assert "ECHO>" in out and "doors" in out
    s.player.current_room = "var_dungeon"
    s.world.enemy_locations = {
        e: r for e, r in s.world.enemy_locations.items() if r != "var_dungeon"
    }
    again = _out(s, "cat .system_err_log")
    assert s.player.has_item("chmod_key")
    assert "flags can open doors" not in again.lower()


def test_no_grant_when_door_already_open(s: GameSession) -> None:
    s.world.unlock_room("usr_lib_arcane")
    out = _out(s, "grep FLAG lost_user_log")
    assert not s.player.has_item("lib_key")
    assert "a new directory appeared" not in out


def test_old_save_loses_a_floor_copy_of_a_flag_key(s: GameSession) -> None:
    """Saves from before the keys chain left chmod_key lying in /var; the
    /var flag hands it out now, so loading drops the floor copy."""
    s.world.item_locations["chmod_key"] = "var_dungeon"
    saved = {"player": s.player.to_dict(), "world": copy.deepcopy(s.world.get_state())}
    s.engine._enter_loaded_run(saved)
    assert "chmod_key" not in s.world.item_locations
    s.player.current_room = "var_dungeon"
    s.world.enemy_locations = {
        e: r for e, r in s.world.enemy_locations.items() if r != "var_dungeon"
    }
    s.submit("cat .system_err_log")
    assert [k for k in s.player.inventory if k.startswith("chmod_key")] == ["chmod_key"]


def test_taking_a_dropped_key_reveals_its_door(s: GameSession) -> None:
    s.world.item_locations["sudo_privileges_badge"] = "mnt_forest"
    out = _out(s, "take sudo_privileges_badge")
    assert s.player.has_item("sudo_privileges_badge")
    assert s.world.door_visible("dev_null_void")
    assert "/dev" in out


def test_hint_mentions_the_door(s: GameSession) -> None:
    assert "new door" in _out(s, "hint")


def test_loading_reveals_doors_for_held_keys(s: GameSession) -> None:
    s.player.add_to_inventory("lib_key", s.world.get_item("lib_key"))
    saved = {"player": s.player.to_dict(), "world": copy.deepcopy(s.world.get_state())}
    assert not s.world.door_visible("usr_lib_arcane")  # held, never revealed
    s.engine._enter_loaded_run(saved)
    assert s.world.door_visible("usr_lib_arcane")
