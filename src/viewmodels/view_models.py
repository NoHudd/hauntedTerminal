#!/usr/bin/env python3
"""
View Models - Data Transfer Objects for UI/Backend separation.

These dataclasses define the exact data the UI needs without coupling to backend implementations.
All view models are immutable and serializable.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass(frozen=True)
class StatsView:
    """Player statistics for the stats panel."""
    player_name: str
    health: int
    max_health: int
    damage: int
    player_class: str
    level: int = 1
    cycles: int = 0
    cycles_to_next: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization."""
        return asdict(self)


@dataclass(frozen=True)
class InventoryItemView:
    """Single inventory item representation."""
    id: str
    name: str
    item_type: str
    rarity: str = "common"
    is_equipped: bool = False
    damage: Optional[int] = None
    healing: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization."""
        return asdict(self)


@dataclass(frozen=True)
class InventoryView:
    """Full inventory representation."""
    items: List[InventoryItemView] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization."""
        return {
            "items": [item.to_dict() for item in self.items]
        }


@dataclass(frozen=True)
class RoomView:
    """Room display data."""
    name: str
    description: str
    id: str = ""
    zone: str = ""
    exits: List[str] = field(default_factory=list)
    enemies: List[str] = field(default_factory=list)      # display names
    npcs: List[str] = field(default_factory=list)         # display names
    enemy_ids: List[str] = field(default_factory=list)    # same order as enemies
    npc_ids: List[str] = field(default_factory=list)      # same order as npcs

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization."""
        return asdict(self)


@dataclass(frozen=True)
class AttackView:
    """Single attack option with cooldown info."""
    id: str
    name: str
    bonus_damage: int
    cooldown: int
    cooldown_remaining: int = 0
    on_cooldown: bool = False
    accuracy: int = 100

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization."""
        return asdict(self)


@dataclass(frozen=True)
class CombatView:
    """Combat UI data bundle."""
    enemy_name: str
    enemy_health: int
    enemy_max_health: int
    player_health: int
    player_max_health: int
    available_attacks: List[AttackView] = field(default_factory=list)
    usable_items: List[InventoryItemView] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization."""
        return {
            "enemy_name": self.enemy_name,
            "enemy_health": self.enemy_health,
            "enemy_max_health": self.enemy_max_health,
            "player_health": self.player_health,
            "player_max_health": self.player_max_health,
            "available_attacks": [attack.to_dict() for attack in self.available_attacks],
            "usable_items": [item.to_dict() for item in self.usable_items]
        }


@dataclass(frozen=True)
class EnemyView:
    """Enemy display data."""
    id: str
    name: str
    health: int
    max_health: int
    damage: int
    description: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization."""
        return asdict(self)
