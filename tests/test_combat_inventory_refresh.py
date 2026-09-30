"""Using an item in combat must refresh the Inventory panel: it used to keep
showing a used-up Health Packet until the fight ended."""
from __future__ import annotations

from typing import Any

from engine.api import GameSession
from engine.events import EventType
from src.game_states import GameState


def test_using_an_item_in_combat_refreshes_the_inventory_panel() -> None:
    s = GameSession()
    try:
        s.new_game("Tess", "guardian")
        s.player.tutorial_state["completed"] = True
        s.player.add_to_inventory("health_packet", s.world.get_item("health_packet"))
        s.world.spawn_tutorial_enemy("root")
        s.submit("cd root")
        assert s.state == GameState.IN_COMBAT
        s.player.health = 10

        views: list[dict[str, Any]] = []
        s.bus.subscribe(
            EventType.PLAYER_INVENTORY_CHANGED, lambda e: views.append(e.data)
        )
        s.submit("use health_packet")

        assert "health_packet" not in s.player.inventory
        assert views, "the Inventory panel was never told the item was used"
        assert "health_packet" not in [item["id"] for item in views[-1]["items"]]
    finally:
        s.close()
