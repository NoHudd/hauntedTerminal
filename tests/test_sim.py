"""Simulation harness tests (difficulty-sim Part B).

Fast, low-run checks that the sim is deterministic and directionally sane.
"""
from __future__ import annotations

from sim.gauntlet import main_path_enemy_ids
from sim.simulator import measure


def test_gauntlet_is_ordered_by_threat() -> None:
    from src.data_loader import load_enemy_data

    enemies = load_enemy_data()
    ids = main_path_enemy_ids()
    assert len(ids) >= 8

    def threat(eid: str) -> float:
        e = enemies[eid]
        return (e.get("health", 0) or 0) + (e.get("damage", 0) or 0) * 8

    threats = [threat(e) for e in ids]
    assert threats == sorted(threats), "gauntlet must ramp easy -> hard"


def test_measure_is_deterministic() -> None:
    a = measure("guardian", "medium", runs=8, seed=1)
    b = measure("guardian", "medium", runs=8, seed=1)
    assert a.win_rate == b.win_rate
    assert 0.0 <= a.win_rate <= 1.0


def test_easy_is_not_harder_than_hard() -> None:
    easy = measure("guardian", "easy", runs=12, seed=3)
    hard = measure("guardian", "hard", runs=12, seed=3)
    assert easy.win_rate >= hard.win_rate


def test_class_weapons_excludes_legendary_but_allows_epic() -> None:
    # Legendary never world-places / is a post-win trophy, so the sim must not equip
    # it (that phantom inflated the old tune). Epic IS obtainable via the guaranteed
    # capstone drop, so it belongs in the pool. Pool must be non-empty per class.
    import yaml

    from sim.simulator import _class_weapons

    with open("data/items/weapons.yaml") as fh:
        weapons = (yaml.safe_load(fh) or {})["weapons"]
    legendary = {
        wid for wid, d in weapons.items()
        if str(d.get("rarity", "")).lower() == "legendary"
    }
    assert legendary, "fixture guard: expected some legendary weapons to exist"

    for cls in ("guardian", "weaver", "shaman"):
        pool = {wid for wid, _ in _class_weapons(cls)}
        assert pool, f"{cls} has no obtainable weapons"
        leaked = pool & legendary
        assert not leaked, f"{cls} sim pool includes unobtainable legendary: {leaked}"
