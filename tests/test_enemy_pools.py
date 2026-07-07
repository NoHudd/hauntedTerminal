"""Pure enemy-pool building + rolling (no GameWorld)."""
from __future__ import annotations

import src.rng as rng
from src.enemy_pools import build_tier_pools, roll_room_enemies

ENEMIES = {
    "a1": {"tier": 1}, "a2": {"tier": 1}, "a3": {"tier": 1},
    "b1": {"tier": 2}, "b2": {"tier": 2},
    "c1": {"tier": 3},
    "boss": {},                      # no tier -> never pooled
    "pinnedC": {"tier": 3},          # tier 3 but pinned in a room below
}


def test_build_tier_pools_groups_and_sorts() -> None:
    pools = build_tier_pools(ENEMIES)
    assert pools[1] == ["a1", "a2", "a3"]
    assert pools[2] == ["b1", "b2"]
    assert set(pools[3]) == {"c1", "pinnedC"}
    assert "boss" not in pools[1] + pools[2] + pools[3]


def test_pinned_rooms_are_preserved_and_reserved() -> None:
    rooms = {
        "core": {"enemies": ["boss"]},
        "tomb": {"enemies": ["pinnedC"]},           # reserves pinnedC (tier3)
        "hall": {"enemy_tier": 3, "enemy_count": 1},
    }
    rng.seed(0)
    result = roll_room_enemies(rooms, ENEMIES, rng)
    assert result["core"] == ["boss"]
    assert result["tomb"] == ["pinnedC"]
    # hall must draw a tier3 that is NOT the reserved pinnedC -> only c1 left
    assert result["hall"] == ["c1"]


def test_rolled_rooms_draw_distinct_in_tier() -> None:
    rooms = {"r": {"enemy_tier": 1, "enemy_count": 2}}
    rng.seed(1)
    drawn = roll_room_enemies(rooms, ENEMIES, rng)["r"]
    assert len(drawn) == 2 and len(set(drawn)) == 2
    assert all(ENEMIES[e]["tier"] == 1 for e in drawn)


def test_count_exceeding_pool_returns_available_without_error() -> None:
    rooms = {"r": {"enemy_tier": 2, "enemy_count": 5}}  # pool2 has only 2
    rng.seed(2)
    drawn = roll_room_enemies(rooms, ENEMIES, rng)["r"]
    assert set(drawn) == {"b1", "b2"}


def test_rolls_are_deterministic_under_seed() -> None:
    rooms = {"r": {"enemy_tier": 1, "enemy_count": 2}}
    rng.seed(7); a = roll_room_enemies(rooms, ENEMIES, rng)["r"]
    rng.seed(7); b = roll_room_enemies(rooms, ENEMIES, rng)["r"]
    assert a == b


def test_live_pools_are_six_each() -> None:
    from src.data_loader import load_enemy_data
    pools = build_tier_pools(load_enemy_data())
    assert len(pools[1]) == 6, pools[1]
    assert len(pools[2]) == 6, pools[2]
    assert len(pools[3]) == 6, pools[3]


def test_bosses_are_not_pooled() -> None:
    from src.data_loader import load_enemy_data
    enemies = load_enemy_data()
    for boss in ("daemon_overlord.sys", "corruption_overlord.exe"):
        assert boss in enemies
        assert enemies[boss].get("tier") is None, f"{boss} must not be pooled"


import glob
import os

import yaml


def _rooms() -> dict[str, dict]:
    out = {}
    for path in glob.glob("data/rooms/*.yml"):
        out[os.path.basename(path)[:-4]] = yaml.safe_load(open(path)) or {}
    return out


def test_rooms_never_declare_both_enemies_and_tier() -> None:
    for rid, r in _rooms().items():
        assert not (r.get("enemies") and r.get("enemy_tier")), f"{rid} has both"


def test_rollable_room_counts_fit_their_tier_pool() -> None:
    from src.data_loader import load_enemy_data
    pools = build_tier_pools(load_enemy_data())
    per_tier_slots = {1: 0, 2: 0, 3: 0}
    for rid, r in _rooms().items():
        t = r.get("enemy_tier")
        if t in per_tier_slots:
            assert r.get("enemy_count", 0) >= 1, f"{rid} needs enemy_count >= 1"
            per_tier_slots[t] += r["enemy_count"]
    for t, slots in per_tier_slots.items():
        assert slots <= len(pools[t]), f"tier {t}: {slots} slots > pool {len(pools[t])}"


def test_core_still_pins_the_boss() -> None:
    assert _rooms()["core"].get("enemies") == ["daemon_overlord.sys"]


def test_ramp_rooms_are_tiered() -> None:
    rooms = _rooms()
    expected = {
        "bin_armory": (1, 2), "archive": (1, 1), "usr_share_games": (2, 1),
        "mnt_forest": (2, 1), "var_dungeon": (2, 2), "usr_lib_arcane": (3, 1),
        "dev_null_void": (3, 1),  # re-tuned from 2 -> 1 (two boss-tier mobs pre-boss was too spiky)
    }
    for rid, (tier, count) in expected.items():
        assert rooms[rid].get("enemy_tier") == tier, rid
        assert rooms[rid].get("enemy_count") == count, rid
        assert not rooms[rid].get("enemies"), f"{rid} must drop its fixed enemies list"


def test_world_rolls_and_persists_enemies() -> None:
    from engine.api import GameSession
    rng.seed(123)
    s = GameSession(); s.new_game("T", "guardian")
    try:
        world = s.engine.cmd_handler.world
        # a tier-2 count-2 room should hold exactly 2 distinct tier-2 enemies
        placed = [e for e, room in world.enemy_locations.items() if room == "var_dungeon"]
        assert len(placed) == 2 and len(set(placed)) == 2
        from src.data_loader import load_enemy_data
        enemies = load_enemy_data()
        assert all(enemies[e].get("tier") == 2 for e in placed)
        # persistence: saved state carries the rolled placement verbatim
        state = world.get_state()
        assert state["enemy_locations"] == world.enemy_locations
    finally:
        s.close()


def test_gauntlet_varies_and_ends_on_the_boss() -> None:
    from sim.gauntlet import main_path_enemy_ids
    rng.seed(1); run_a = main_path_enemy_ids()
    rng.seed(2); run_b = main_path_enemy_ids()
    assert run_a and run_b
    assert run_a[-1] == "daemon_overlord.sys"          # boss stays the finale
    assert run_a != run_b                              # different seeds -> different run
