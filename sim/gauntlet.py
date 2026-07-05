"""The combat gauntlet: the main-path enemies a run must survive.

Main-path = enemies in non-hidden rooms, ordered easy -> hard. We order by an
enemy-stats difficulty proxy (HP + weighted damage) rather than the room's
zone_level, because zone_level is incomplete/inconsistent in the content (several
main rooms have none, and usr_share_games=15 outranks the final boss room=10).
Ordering by actual threat gives a stable difficulty ramp. Hidden-room / secret
content is excluded (see docs/DIFFICULTY_SIM_DESIGN.md).
"""
from __future__ import annotations

from src.data_loader import load_enemy_data, load_room_data

# Damage is weighted heavily: over many turns, damage-per-turn drives lethality
# far more than a one-time HP pool.
_DAMAGE_WEIGHT = 8


def _threat(enemy: dict) -> float:
    return (enemy.get("health", 0) or 0) + (enemy.get("damage", 0) or 0) * _DAMAGE_WEIGHT


def main_path_enemy_ids() -> list[str]:
    """Main-path enemy ids ordered from least to most threatening."""
    rooms = load_room_data()
    enemies = load_enemy_data()

    ids: list[str] = []
    for room in rooms.values():
        if not isinstance(room, dict) or room.get("hidden", False):
            continue
        for enemy_id in room.get("enemies", []) or []:
            if enemy_id in enemies:
                ids.append(enemy_id)

    ids.sort(key=lambda eid: _threat(enemies[eid]))
    return ids
