"""Every generated run must be completable.

Loot is placed randomly per run, but keys are not: room flags hand them out
in a fixed chain (and bosses drop the rest). This walks that chain and pins
that /boot's flag gate can be met, across a few seeds and all three classes.
"""
from __future__ import annotations

import pytest

from engine.content.loader import load_items
from src import rng, room_paths
from src.data_loader import load_enemy_data, load_npc_data, load_room_data
from src.game_world import GameWorld
from src.item_placer import ItemPlacer

CLASSES = ["guardian", "weaver", "shaman"]
# Keys come from the flag chain, not from placement, so the seed no longer
# decides whether a run is winnable; a few seeds guard against loot placement
# ever touching keys again.
FLAG_SEEDS = list(range(4))
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
    """Keys the player can earn before /boot: flag grants in every room
    reachable so far (the chain), plus the Shadow's badge once /proc/self is."""
    held: set[str] = set()
    for _ in range(len(world.rooms) + 2):     # bounded: reachability only grows
        reachable = _open_rooms(world, held)
        found = set()
        for rid in reachable:
            flag = world.get_room(rid).flag
            if flag is not None and flag.grants:
                found.add(str(flag.grants))
        if "mirror_sector" in reachable:
            found.add("sudo_privileges_badge")
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
        f"needs are reachable before it (keys: {sorted(held)})"
    )


def test_placer_scatters_no_keys() -> None:
    """Keys come from flags and bosses only; none lie on a floor."""
    for player_class in CLASSES:
        world = _fresh_world(player_class, seed=0)
        placer = ItemPlacer(world)
        assert not [k for k in world.item_locations if placer.is_key(k)]


def test_starter_weapon_is_always_in_the_starting_room() -> None:
    for player_class in CLASSES:
        world = _fresh_world(player_class, seed=0)
        starter = world.class_data[player_class].starter_weapon
        assert world.item_locations.get(starter) == "home_grove", (
            f"{player_class} cannot find its starter weapon where the tutorial "
            "says it is"
        )
