"""Epic and legendary gear is earned: it never starts in a room a new player can
walk into without a key.

Root (/) sits one `cd ..` above /home, the tutorial sends players there, and it
used to hold 2-3 legendary weapons most runs: the placer's rules were written
for /root (the superuser's home) before the room id "root" became the hub."""
from __future__ import annotations

import pytest

from engine.api import GameSession
from src import rng
from src.item_placer import ItemPlacer

SEEDS = range(6)
LEGENDARY_ROOMS = {"etc_hidden_configs", "core"}  # /etc and /boot


def _new_run(klass: str, seed: int) -> GameSession:
    rng.seed(seed)
    s = GameSession()
    s.new_game("T", klass)
    s.engine.initialize_special_items(klass)  # the real new-game loot pass
    return s


@pytest.mark.parametrize("klass", ["guardian", "weaver", "shaman"])
def test_no_top_tier_gear_starts_in_an_open_room(klass: str) -> None:
    for seed in SEEDS:
        s = _new_run(klass, seed)
        try:
            placer = ItemPlacer(s.world)
            for iid, room in s.world.item_locations.items():
                rarity = str(s.world.items[iid].rarity)
                if rarity in ("epic", "legendary"):
                    assert not placer._starts_open(room), (seed, iid, room)
                if rarity == "legendary":
                    assert room in LEGENDARY_ROOMS, (seed, iid, room)
        finally:
            s.close()


@pytest.mark.parametrize("klass", ["guardian", "weaver", "shaman"])
def test_root_is_a_low_tier_hub(klass: str) -> None:
    for seed in SEEDS:
        s = _new_run(klass, seed)
        try:
            for iid in s.world.get_items_in_room("root"):
                assert str(s.world.items[iid].rarity) in ("common", "uncommon"), (seed, iid)
        finally:
            s.close()


def test_the_legendaries_still_exist_somewhere() -> None:
    placed = set()
    for seed in SEEDS:
        s = _new_run("guardian", seed)
        try:
            placed |= {
                iid for iid in s.world.item_locations
                if str(s.world.items[iid].rarity) == "legendary"
            }
        finally:
            s.close()
    assert placed, "no legendary was placed in any run"
