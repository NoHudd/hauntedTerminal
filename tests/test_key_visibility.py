"""Listings show only doors you can open (or /boot, the goal)."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.viewmodels.view_builder import ViewBuilder


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "guardian")
    session.player.tutorial_state["completed"] = True
    session.player.current_room = "root"
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_ls_hides_locked_doors_until_revealed(s: GameSession) -> None:
    out = _out(s, "ls")
    assert "usr/" not in out and "etc/" not in out and "dev/" not in out
    assert "boot/" in out and "bin/" in out
    s.world.reveal_doors("lib_key")
    assert "usr/" in _out(s, "ls")


def test_ls_a_does_not_discover_a_secret_behind_an_unrevealed_lock(s: GameSession) -> None:
    out = _out(s, "ls -a")
    assert "opt/" not in out
    assert not s.world.is_discovered("opt_mage_tower")


def test_tree_hides_locked_branches(s: GameSession) -> None:
    out = _out(s, "tree")
    assert "usr/" not in out and "games/" not in out
    assert "boot/" in out


def test_cd_to_an_invisible_door_is_no_such_file(s: GameSession) -> None:
    out = _out(s, "cd /usr")
    assert "No such file or directory" in out
    assert "lib_key" not in out


def test_cd_typo_does_not_suggest_invisible_rooms(s: GameSession) -> None:
    assert "usr" not in _out(s, "cd us")


def test_scene_exits_hide_invisible_doors(s: GameSession) -> None:
    view = ViewBuilder.build_room_view(s.world, "root")
    assert not any(e.startswith("/usr") or e.startswith("/etc") for e in view.exits)


def test_tutorial_example_skips_invisible_dirs(s: GameSession) -> None:
    coach = s.engine.cmd_handler.tutorial
    assert all(s.world.door_visible(r) for r in coach._visible_directories())
