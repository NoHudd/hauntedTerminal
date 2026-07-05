"""Optimal-play policy for the simulation bot.

Deterministic given the game state. Models a skilled player: heal when low if a
heal is available, otherwise use the highest expected-damage attack that is off
cooldown. (In the gauntlet, fleeing = failing the run, so the bot always fights.)
"""
from __future__ import annotations

HEAL_THRESHOLD = 0.40  # heal when HP drops below 40% of max, if a heal is on hand


def choose_action(
    player_base_damage: int,
    hp_ratio: float,
    available_attacks: dict,
    has_heal: bool,
) -> tuple[str, str | None]:
    """Return the bot's action: ('heal', None) or ('attack', attack_id)."""
    if has_heal and hp_ratio < HEAL_THRESHOLD:
        return ("heal", None)

    best_id: str | None = None
    best_expected = -1.0
    for attack_id, attack in available_attacks.items():
        if not isinstance(attack, dict) or attack.get("on_cooldown", False):
            continue
        bonus = attack.get("bonus_damage", attack.get("damage", 0)) or 0
        accuracy = attack.get("accuracy", 100) or 100
        expected = (player_base_damage + bonus) * (accuracy / 100.0)
        if expected > best_expected:
            best_expected = expected
            best_id = attack_id

    # Fallback: a basic strike if nothing is available (shouldn't normally happen).
    return ("attack", best_id if best_id is not None else "strike")
