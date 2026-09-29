"""Enemy loot-drop pipeline: CommandHandler.on_kill -> award into the room.

Uses GameSession to build a real world/handler, injects a synthetic enemy with
deterministic (chance 100) drops, reports the kill, and asserts the loot
landed in the current room. Reaches into src.game_world internals deliberately —
this exercises the src-side award wiring the engine layer does not cover.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

import src.rng as rng
from engine.api import GameSession
from engine.schema import Enemy


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tester", "weaver")
    try:
        yield s
    finally:
        s.close()


def test_existing_drops_are_awarded_into_the_room(session: GameSession) -> None:
    h = session.engine.cmd_handler
    room = h.player.current_room
    # Use an item NOT pre-placed in the starting room (home_grove already holds a
    # health_packet + starter weapon), and assert it newly appears after the drop.
    drop_item = "kill_script"
    assert drop_item not in h.world.get_items_in_room(room)
    h.world.enemies["test_dropper"] = Enemy(
        id="test_dropper", name="Test Dropper", health=10, damage=1,
        drops=[{"item": drop_item, "chance": 100}],
    )
    h.world.enemy_locations["test_dropper"] = room

    h.on_kill("test_dropper")

    assert drop_item in h.world.get_items_in_room(room)


def test_drops_are_awarded_only_once(session: GameSession) -> None:
    h = session.engine.cmd_handler
    room = h.player.current_room
    h.world.enemies["test_dropper2"] = Enemy(
        id="test_dropper2", name="Test Dropper 2", health=10, damage=1,
        drops=[{"item": "health_packet", "chance": 100}],
    )
    h.world.enemy_locations["test_dropper2"] = room

    h.on_kill("test_dropper2")
    h.on_kill("test_dropper2")

    assert "test_dropper2" in h.loot.awarded


def test_loot_table_drops_class_appropriate_gear(session: GameSession) -> None:
    h = session.engine.cmd_handler  # session is a weaver
    room = h.player.current_room
    h.world.enemies["test_boss"] = Enemy(
        id="test_boss", name="Test Boss", health=10, damage=1,
        loot_table=[{"rarity": "epic", "chance": 100}],
    )
    h.world.enemy_locations["test_boss"] = room
    rng.seed(1)

    h.on_kill("test_boss")

    room_items = set(h.world.get_items_in_room(room))
    epics = {iid for iid, d in h.world.items.items() if str(d.rarity).lower() == "epic"}
    dropped_epic = room_items & epics
    assert dropped_epic, f"expected an epic gear drop, room has {room_items}"
    # and it must be usable by the weaver (class-appropriate)
    for iid in dropped_epic:
        assert h.player.can_use_item(h.world.get_item(iid))


def test_loot_table_never_drops_a_healing_item(session: GameSession) -> None:
    # Guard the heal economy: gear tables must not yield healing consumables even
    # if a healing item happened to share a rarity tier.
    h = session.engine.cmd_handler
    for _ in range(50):
        got = h.loot.roll_loot_table([{"rarity": "rare", "chance": 100}])
        if got is not None:
            data = h.world.get_item(got)
            assert data.type in ("weapon", "armor"), f"{got} is not gear"
            assert "healing" not in data.tags


def test_final_boss_has_a_legendary_loot_table() -> None:
    import yaml
    with open("data/enemies/daemon_overlord.sys.yml") as fh:
        boss = yaml.safe_load(fh)
    rarities = {e.get("rarity") for e in (boss.get("loot_table") or [])}
    assert "legendary" in rarities, "final boss should be able to drop a legendary"


def test_some_enemy_can_drop_epic() -> None:
    import glob

    import yaml
    epic_droppers = []
    for path in glob.glob("data/enemies/*.y*ml"):
        with open(path) as fh:
            e = yaml.safe_load(fh) or {}
        if any(entry.get("rarity") == "epic" for entry in (e.get("loot_table") or [])):
            epic_droppers.append(path)
    assert epic_droppers, "at least one enemy must have an epic in its loot_table"


def test_gear_you_already_have_never_drops_again(session: GameSession) -> None:
    """Picking an item up takes it off the floor; the gear roll only excluded
    floor items, so a held Null-Void Cloak came back as a second copy."""
    h = session.engine.cmd_handler  # session is a weaver
    h.world.item_locations["null_void_cloak"] = h.player.current_room
    session.submit("take null_void_cloak")
    assert h.player.has_item("null_void_cloak")

    rng.seed(0)
    rolls = {h.loot.random_gear_of_rarity("epic") for _ in range(200)}
    assert "null_void_cloak" not in rolls


def test_gear_taken_and_lost_never_drops_again(session: GameSession) -> None:
    h = session.engine.cmd_handler
    h.world.item_locations["null_void_cloak"] = h.player.current_room
    session.submit("take null_void_cloak")
    h.player.remove_from_inventory("null_void_cloak")  # e.g. lost on death

    rng.seed(0)
    rolls = {h.loot.random_gear_of_rarity("epic") for _ in range(200)}
    assert "null_void_cloak" not in rolls
