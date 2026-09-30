"""Taking an item says what it is, right under "Added … to your inventory"."""
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


def _take(s: GameSession, item_id: str) -> list[str]:
    s.world.item_locations[item_id] = "mnt_forest"
    return [str(x) for x in s.submit(f"take {item_id}")]


def _added_at(lines: list[str]) -> int:
    return next(i for i, line in enumerate(lines) if "to your inventory" in line)


def test_description_follows_added_line(s: GameSession) -> None:
    item = s.world.get_item("health_packet")
    assert item is not None and item.description
    lines = _take(s, "health_packet")
    at = _added_at(lines)
    assert item.description in lines[at + 1]


def test_key_announcement_comes_after_added_and_description(s: GameSession) -> None:
    key = s.world.get_item("sudo_privileges_badge")
    assert key is not None and key.description
    lines = _take(s, "sudo_privileges_badge")
    at = _added_at(lines)
    assert key.description in lines[at + 1]
    announce = next(i for i, line in enumerate(lines) if "a new directory appeared" in line)
    assert announce > at + 1


def test_no_blank_line_when_item_has_no_description(s: GameSession) -> None:
    item = s.world.get_item("health_packet")
    assert item is not None
    item.description = ""
    lines = _take(s, "health_packet")
    at = _added_at(lines)
    assert lines[at + 1].strip() != ""
