"""A Legacy Backup revives you once and is spent; the Inventory panel must
drop it at once, or the next death looks like the backup failed."""
from __future__ import annotations

from typing import Any

from engine.api import GameSession
from engine.events import EventType
from src.game_states import GameState


def test_backup_revives_once_then_the_next_death_ends_the_run() -> None:
    s = GameSession()
    try:
        s.new_game("Rob", "weaver")
        s.player.tutorial_state["completed"] = True
        s.player.add_to_inventory("legacy_backup", s.world.get_item("legacy_backup"))
        s.world.spawn_tutorial_enemy("root")
        s.submit("cd root")
        combat = s.engine.cmd_handler.current_combat_session
        assert combat is not None and s.state == GameState.IN_COMBAT
        combat.enemy_health = 10**6
        combat.enemy_damage = 10**6
        attack = next(iter(combat.available_attacks))

        views: list[dict[str, Any]] = []
        s.bus.subscribe(EventType.PLAYER_INVENTORY_CHANGED, lambda e: views.append(e.data))
        out = "\n".join(s.submit(attack))

        assert "restores you from a snapshot" in out
        assert s.state == GameState.IN_COMBAT and s.player.is_alive()
        assert "legacy_backup" not in s.player.inventory
        assert "legacy_backup" not in [i["id"] for i in views[-1]["items"]]

        s.submit(attack)
        assert s.state == GameState.GAME_OVER
    finally:
        s.close()
