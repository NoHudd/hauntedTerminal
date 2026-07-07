"""The combat gauntlet: the main-path enemies a run must survive.

Main-path = enemies in rooms every class can actually reach, ordered easy ->
hard. We order by an enemy-stats difficulty proxy (HP + weighted damage) rather
than the room's zone_level, because zone_level is incomplete/inconsistent in the
content (several main rooms have none, and usr_share_games=15 outranks the final
boss room=10). Ordering by actual threat gives a stable difficulty ramp.

Excluded as optional "xtras" (see docs/DIFFICULTY_SIM_DESIGN.md):
  - hidden rooms (secret detours),
  - locked rooms (gated behind keys),
  - class-restricted rooms (the class tombs/towers — e.g. srv_warrior_tomb is
    guardian-only, opt_mage_tower is weaver-only; a run must never be scored
    against a boss its class could not reach).
None of these gate the win condition (core + Daemon Overlord), so they are side
content, not the gauntlet.
"""
from __future__ import annotations

from src.data_loader import load_enemy_data, load_room_data

# Damage is weighted heavily: over many turns, damage-per-turn drives lethality
# far more than a one-time HP pool.
_DAMAGE_WEIGHT = 8


def _threat(enemy: dict) -> float:
    return (enemy.get("health", 0) or 0) + (enemy.get("damage", 0) or 0) * _DAMAGE_WEIGHT


def main_path_enemy_ids() -> list[str]:
    """Main-path enemy ids for one sampled run, least- to most-threatening.

    Rolls tier rooms via enemy_pools (seeded by the caller), so each call under a
    fresh seed yields a different-but-tier-appropriate run. Boss stays pinned.
    """
    from src.enemy_pools import roll_room_enemies
    from src import rng

    rooms = load_room_data()
    enemies = load_enemy_data()

    # Main path only: skip secret, key-gated, or class-locked side content.
    main_path = {
        rid: room for rid, room in rooms.items()
        if isinstance(room, dict)
        and not room.get("hidden", False)
        and not room.get("locked", False)
        and not room.get("class_restriction")
    }
    rolled = roll_room_enemies(main_path, enemies, rng)

    ids = [eid for rid in main_path for eid in rolled.get(rid, []) if eid in enemies]
    ids.sort(key=lambda eid: _threat(enemies[eid]))
    return ids
