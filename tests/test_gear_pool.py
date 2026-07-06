"""Guard invariants for the findable gear pool (Phase 1: weapons).

Reads the raw YAML rather than the typed Item core, because the balance-
bearing fields (damage, allowed_zones) live in YAML and are ignored by the
pydantic Item model. These tests lock in: wired-stat presence, valid rarity,
class validity, and the rule that no high-rarity weapon leaks into an early
(tuned-tight) zone.
"""
from __future__ import annotations

import yaml

PLACEABLE_RARITIES = {"common", "uncommon", "rare", "epic", "legendary"}
RARE_PLUS = {"rare", "epic", "legendary"}
EARLY_ZONES = {"home", "safe", "var", "tmp"}
VALID_CLASSES = {"guardian", "weaver", "shaman"}


def _weapons() -> dict[str, dict]:
    with open("data/items/weapons.yaml") as fh:
        return yaml.safe_load(fh)["weapons"]


def test_every_weapon_has_wired_positive_damage() -> None:
    for wid, w in _weapons().items():
        dmg = w.get("damage")
        assert isinstance(dmg, int) and dmg > 0, f"{wid} damage must be int > 0, got {dmg!r}"


def test_every_weapon_has_valid_rarity() -> None:
    for wid, w in _weapons().items():
        assert w.get("rarity") in PLACEABLE_RARITIES, f"{wid} rarity {w.get('rarity')!r} not placeable"


def test_every_weapon_has_valid_classes_and_zones() -> None:
    for wid, w in _weapons().items():
        classes = set(w.get("allowed_classes") or [])
        assert classes and classes <= VALID_CLASSES, f"{wid} allowed_classes invalid: {classes}"
        assert w.get("allowed_zones"), f"{wid} must have non-empty allowed_zones"


def test_no_rare_plus_weapon_in_early_zone() -> None:
    for wid, w in _weapons().items():
        if w.get("rarity") in RARE_PLUS:
            zones = set(w.get("allowed_zones") or [])
            assert not (zones & EARLY_ZONES), f"{wid} ({w['rarity']}) leaks into early zone(s): {zones & EARLY_ZONES}"


def test_rare_tier_is_deepened_for_world_placement() -> None:
    # Phase 1 deliverable: rare and below actually spawn via the class-based placer,
    # so deepening the *rare* tier is what adds real run-to-run variety now. (Epic and
    # legendary are gated by _get_allowed_rarities_for_room to boss/multi-enemy rooms
    # plus a directory-depth multiplier, so they never place in this 18-room world —
    # their delivery is Phase 2 drop tables. Verified empirically: 0 placements/900 runs.)
    rare = sum(1 for w in _weapons().values() if w.get("rarity") == "rare")
    assert rare >= 4, f"expected >=4 rare weapons for world-placed variety, got {rare}"


def test_epic_legendary_entries_staged_for_phase2_drops() -> None:
    # Epic/legendary weapons are authored now as Phase 2 drop-table payload (drop tables
    # bypass the room-rarity gate). They must exist and be drop-ready (wired damage),
    # even though the world placer will not scatter them.
    weapons = _weapons()
    epic = [w for w in weapons.values() if w.get("rarity") == "epic"]
    legendary = [w for w in weapons.values() if w.get("rarity") == "legendary"]
    assert len(epic) >= 4, f"expected >=4 epic entries staged for Phase 2, got {len(epic)}"
    assert len(legendary) >= 3, f"expected >=3 legendary entries staged for Phase 2, got {len(legendary)}"
    for w in epic + legendary:
        dmg = w.get("damage")
        assert isinstance(dmg, int) and dmg > 0, f"{w.get('name')} not drop-ready: damage {dmg!r}"
