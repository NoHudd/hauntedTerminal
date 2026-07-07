"""Difficulty-tier enemy pools + per-room rolling.

Pools are derived from a `tier` field on each enemy. roll_room_enemies assigns
each room its enemies: pinned rooms keep their explicit `enemies:` (and their ids
are reserved so pools never collide), tier rooms draw `enemy_count` distinct,
globally-unique enemies of their tier. Pure — no GameWorld/import cycles.
"""
from __future__ import annotations

POOL_TIERS = (1, 2, 3)


def build_tier_pools(enemies: dict) -> dict[int, list[str]]:
    pools: dict[int, list[str]] = {t: [] for t in POOL_TIERS}
    for eid, edata in enemies.items():
        tier = (edata or {}).get("tier")
        if tier in pools:
            pools[tier].append(eid)
    for tier in pools:
        pools[tier].sort()
    return pools


def roll_room_enemies(rooms: dict, enemies: dict, rng_module) -> dict[str, list[str]]:
    pools = build_tier_pools(enemies)
    used: dict[int, set] = {t: set() for t in POOL_TIERS}
    result: dict[str, list[str]] = {}

    # Pass 1: pinned rooms keep their enemies and reserve those ids per tier.
    for room_id, room in rooms.items():
        pinned = (room or {}).get("enemies")
        if pinned:
            result[room_id] = list(pinned)
            for eid in pinned:
                tier = (enemies.get(eid) or {}).get("tier")
                if tier in used:
                    used[tier].add(eid)

    # Pass 2: tier rooms draw distinct, still-available enemies of their tier.
    for room_id, room in rooms.items():
        tier = (room or {}).get("enemy_tier")
        if tier in POOL_TIERS:
            count = (room or {}).get("enemy_count", 1)
            available = [e for e in pools[tier] if e not in used[tier]]
            k = min(count, len(available))
            drawn = rng_module.sample(available, k) if k > 0 else []
            used[tier].update(drawn)
            result[room_id] = drawn

    return result
