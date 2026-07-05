"""Aggregate container for all loaded content."""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.schema import (
    NPC,
    Ability,
    AbilityId,
    Attack,
    AttackId,
    CharacterClass,
    ClassId,
    Enemy,
    EnemyId,
    Item,
    ItemId,
    NpcId,
    Room,
    RoomId,
)

from . import loader


@dataclass
class GameContent:
    rooms: dict[RoomId, Room] = field(default_factory=dict)
    items: dict[ItemId, Item] = field(default_factory=dict)
    enemies: dict[EnemyId, Enemy] = field(default_factory=dict)
    npcs: dict[NpcId, NPC] = field(default_factory=dict)
    classes: dict[ClassId, CharacterClass] = field(default_factory=dict)
    abilities: dict[AbilityId, Ability] = field(default_factory=dict)
    attacks: dict[AttackId, Attack] = field(default_factory=dict)


def load_all(data_dir: str = loader.DATA_DIR) -> GameContent:
    """Load and validate every content file. Does NOT link — call
    engine.content.linker.link() to resolve and enforce id-references.
    """
    return GameContent(
        rooms=loader.load_rooms(data_dir),
        items=loader.load_items(data_dir),
        enemies=loader.load_enemies(data_dir),
        npcs=loader.load_npcs(data_dir),
        classes=loader.load_classes(data_dir),
        abilities=loader.load_abilities(data_dir),
        attacks=loader.load_attacks(data_dir),
    )
