"""The engine sends the player's stats and inventory once after each command;
commands used to send them too, so the UI got every view twice."""
from __future__ import annotations

from engine.api import GameSession
from src.events import EventType


def test_take_sends_each_view_once() -> None:
    s = GameSession()
    try:
        s.new_game("Tess", "guardian")
        s.world.item_locations["health_packet"] = s.player.current_room
        seen: list[EventType] = []
        for et in (EventType.PLAYER_STATS_CHANGED, EventType.PLAYER_INVENTORY_CHANGED):
            s.bus.subscribe(et, lambda e: seen.append(e.type))

        s.submit("take health_packet")

        assert seen.count(EventType.PLAYER_INVENTORY_CHANGED) == 1
        assert seen.count(EventType.PLAYER_STATS_CHANGED) == 1
        assert "health_packet" in s.player.inventory
    finally:
        s.close()
