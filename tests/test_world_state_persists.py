"""Regression: room contents must survive a save/load round trip.

The *_locations dicts are the only runtime truth for what is in a room. These
getters used to also union in the room's static YAML list "as a backup", which
made a defeat unrepresentable across a save: killing an enemy removed it from
enemy_locations, but _load_game_data_for_load re-reads the YAML fresh, so every
scripted boss came back to life on load.
"""
from __future__ import annotations

import pytest

from engine.content.loader import load_items
from src.data_loader import load_enemy_data, load_npc_data, load_room_data
from src.game_world import GameWorld


def _world(initialize_state: bool = True) -> GameWorld:
    items = {str(k): v for k, v in load_items("data").items()}
    return GameWorld(
        load_room_data(), items, load_enemy_data(), load_npc_data(),
        initialize_state=initialize_state,
    )


def _round_trip(world: GameWorld) -> GameWorld:
    """Mimic the load path: fresh content, no init, then restore saved state."""
    restored = _world(initialize_state=False)
    restored.set_state(world.get_state())
    return restored


# Every room with a hand-authored `enemies:` list — the scripted bosses.
PINNED = ["core", "mirror_sector", "opt_mage_tower", "srv_warrior_tomb"]


@pytest.mark.parametrize("room_id", PINNED)
def test_defeated_pinned_enemy_stays_dead_after_load(room_id: str) -> None:
    world = _world()
    present = world.get_enemies_in_room(room_id)
    assert present, f"{room_id} should start with pinned enemies"

    for enemy_id in list(present):
        world.remove_enemy_from_room(enemy_id)
    assert world.get_enemies_in_room(room_id) == []

    assert _round_trip(world).get_enemies_in_room(room_id) == [], (
        f"{room_id} enemies resurrected on load — the YAML fallback is back"
    )


def test_cleared_room_still_reads_cleared_after_load() -> None:
    world = _world()
    for enemy_id in list(world.get_enemies_in_room("core")):
        world.remove_enemy_from_room(enemy_id)
    world.mark_flag_captured("core")  # /boot's flag drops with the Overlord

    assert _round_trip(world).is_room_cleared("core")


def test_taken_item_stays_taken_after_load() -> None:
    world = _world()
    item_id = world.get_items_in_room("home_grove")[0]

    world.remove_item_from_room(item_id)
    assert item_id not in world.get_items_in_room("home_grove")

    assert item_id not in _round_trip(world).get_items_in_room("home_grove"), (
        "picked-up item respawned from room YAML on load"
    )


def test_dropped_item_is_visible_again() -> None:
    world = _world()
    item_id = world.get_items_in_room("home_grove")[0]
    world.remove_item_from_room(item_id)
    world.add_item_to_room(item_id, "home_grove")

    assert item_id in world.get_items_in_room("home_grove")
    assert item_id in _round_trip(world).get_items_in_room("home_grove")


def test_world_init_seeds_locations_from_yaml() -> None:
    """The getters read only the locations dicts, so init must populate them."""
    world = _world()
    assert "home_guardian.sys" in world.get_npcs_in_room("home_grove")
    assert world.get_items_in_room("home_grove"), "fixed room items were not seeded"
    assert world.get_enemies_in_room("core") == ["daemon_overlord.sys"]
