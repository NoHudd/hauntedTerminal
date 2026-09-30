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
# /boot's flag gate can strand a run when a key lands behind it (about 1 run in
# 10 before the fix), so the flag test samples far more seeds.
FLAG_SEEDS = list(range(30))
GOAL = "core"          # the boss room, gated by flags_required

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


def _behind_flag_gate(world: GameWorld, room_id: str) -> bool:
    """Is room_id at or under a room that needs flags to enter? Computed here,
    not by the placer, so a placer that forgets the gate cannot hide it."""
    target = room_paths.room_path(room_id)
    for path in room_paths.ancestors(target) + [target]:
        rid = room_paths.room_at(path)
        room = world.get_room(rid) if rid else None
        if room is not None and getattr(room, "flags_required", 0):
            return True
    return False


def _open_rooms(world: GameWorld, held: set[str]) -> set[str]:
    """Rooms walkable with `held` keys before the flag gate opens."""
    return {
        r for r in ItemPlacer(world).rooms_reachable_with(held)
        if not _behind_flag_gate(world, r)
    }


def _keys_obtainable(world: GameWorld) -> set[str]:
    """Keys the player can actually collect before /boot, by repeatedly
    sweeping everywhere currently reachable and taking whatever is there —
    including boss rewards."""
    held: set[str] = set()
    boss_rewards = {"mirror_sector": "sudo_privileges_badge"}

    for _ in range(len(world.rooms) + 2):     # bounded: reachability only grows
        reachable = _open_rooms(world, held)
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
@pytest.mark.parametrize("seed", FLAG_SEEDS)
def test_run_is_completable(player_class: str, seed: int) -> None:
    """/boot opens with flags_required main flags from elsewhere: that many
    flag rooms must be reachable with the keys the run yields before /boot."""
    world = _fresh_world(player_class, seed)
    held = _keys_obtainable(world)
    reachable = _open_rooms(world, held)
    flag_rooms = {
        rid for rid, room in world.rooms.items()
        if room.flag is not None and not room.hidden and rid != GOAL
    }
    needed = world.get_room(GOAL).flags_required
    got = len(flag_rooms & reachable)
    assert got >= needed, (
        f"{player_class} seed {seed}: only {got} of the {needed} flags /boot "
        f"needs are reachable before it (keys: {sorted(held)}; key spots: "
        f"{ {k: v for k, v in world.item_locations.items() if ItemPlacer(world).is_key(k)} })"
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
