"""What a move does, in plain words — shared by the fight menu and the class
card, so both always describe a move the same way."""
from __future__ import annotations

from functools import lru_cache

from engine.schema.models import Attack, CharacterClass


def effect_tags(healing: int, weaken: float) -> list[str]:
    """The side effects a player can't guess from the damage number."""
    tags = []
    if healing > 0:
        tags.append(f"heals {healing} HP")
    if weaken > 0:
        tags.append(f"weakens enemy's next hit {round(weaken * 100)}%")
    return tags


@lru_cache(maxsize=1)
def _attacks() -> dict[str, Attack]:
    from engine.content.loader import load_attacks

    return {str(k): v for k, v in load_attacks("data").items()}


def _move_line(attack: Attack) -> str:
    tags = effect_tags(attack.healing, attack.enemy_damage_reduction)
    if attack.healing > 0:
        # Short form: the card is 40 cells wide and the heal is what matters.
        what = tags[0] + (", weakens foe" if attack.enemy_damage_reduction else "")
    elif attack.cooldown == 0:
        what = "quick hit, any turn"
    else:
        what = "big hit, every few turns"
    return f"• {attack.name}: {what}"


def class_move_lines(cls: CharacterClass) -> list[str]:
    """One short line per starting move, for the class card."""
    attacks = _attacks()
    return [_move_line(attacks[str(a)]) for a in cls.attacks if str(a) in attacks]


def stat_lines(cls: CharacterClass) -> tuple[str, str]:
    """Card stat lines. The numbers come from the class's real base stats, so
    a balance change can never leave the card showing the old ones."""
    return (
        f"{cls.display.hp_label} ({cls.base_health} HP)",
        f"{cls.display.dmg_label} ({cls.base_damage} DMG)",
    )
