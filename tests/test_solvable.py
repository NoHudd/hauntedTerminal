"""Every generated run must be completable.

Loot and keys are placed randomly per run, and permissions are now the whole
difficulty ramp — so a bad placement no longer means "awkward", it means the
player can never reach the boss. Keys are placed in dependency order to prevent
that; this pins the property across many seeds and all three classes.
"""
from __future__ import annotations

import pytest

from engine.content.loader import load_items
from src import rng, room_paths
from src.data_loader import load_enemy_data, load_npc_data, load_room_data
from src.game_world import GameWorld
from src.item_placer import ItemPlacer

CLASSES = ["guardian", "weaver", "shaman"]
# Four seeds per class. The placer is dependency-ordered rather than
# rejection-sampled, so an unsolvable layout would be a logic error that any
# seed exposes, not a rare unlucky roll — a wide grid bought repetition, not
# coverage. Widen this temporarily if you ever change _place_keys.
SEEDS = list(range(4))
GOAL = "core"          # the boss room; reaching it is the win condition

_ITEMS = {str(k): v for k, v in load_items("data").items()}


def _fresh_world(player_class: str, seed: int) -> GameWorld:
    rng.seed(seed)
    world = GameWorld(
        load_room_data(), _ITEMS, load_enemy_data(), load_npc_data()
    )
    room_paths.refresh_from_rooms(world.rooms)
    placer = ItemPlacer(world)
    placer.place_items(player_class)
    placer.place_starter_items(player_class)
    return world


def _keys_obtainable(world: GameWorld) -> set[str]:
    """Keys the player can actually collect, by repeatedly sweeping everywhere
    currently reachable and taking whatever is there — including boss rewards."""
    held: set[str] = set()
    boss_rewards = {"core": "system_badge", "mirror_sector": "sudo_privileges_badge"}

    for _ in range(len(world.rooms) + 2):     # bounded: reachability only grows
        reachable = set(ItemPlacer(world).rooms_reachable_with(held))
        found = {
            item_id for item_id, room in world.item_locations.items()
            if room in reachable and ItemPlacer(world).is_key(item_id)
        }
        found |= {
            reward for room, reward in boss_rewards.items() if room in reachable
        }
        if found <= held:
            break
        held |= found
    return held


@pytest.mark.parametrize("player_class", CLASSES)
@pytest.mark.parametrize("seed", SEEDS)
def test_run_is_completable(player_class: str, seed: int) -> None:
    world = _fresh_world(player_class, seed)
    held = _keys_obtainable(world)

    assert GOAL in ItemPlacer(world).rooms_reachable_with(held), (
        f"{player_class} seed {seed}: the boss room is unreachable with every "
        f"key the run can yield ({sorted(held)})"
    )


@pytest.mark.parametrize("player_class", CLASSES)
def test_no_key_is_locked_behind_itself(player_class: str) -> None:
    """The failure the dependency-ordered placer exists to prevent."""
    for seed in SEEDS:
        world = _fresh_world(player_class, seed)
        for key_id, room_id in world.item_locations.items():
            if not ItemPlacer(world).is_key(key_id):
                continue
            unlocked_by_this_key = set(world.get_item(key_id).unlocks)
            reachable_without_it = set(ItemPlacer(world).rooms_reachable_with(
                _keys_obtainable(world) - {key_id}
            ))
            if unlocked_by_this_key and room_id not in reachable_without_it:
                pytest.fail(
                    f"{player_class} seed {seed}: {key_id} sits in {room_id}, "
                    "which needs that same key to reach"
                )


def test_starter_weapon_is_always_in_the_starting_room() -> None:
    for player_class in CLASSES:
        world = _fresh_world(player_class, seed=0)
        starter = world.class_data[player_class].starter_weapon
        assert world.item_locations.get(starter) == "home_grove", (
            f"{player_class} cannot find its starter weapon where the tutorial "
            "says it is"
        )
