#!/usr/bin/env python3
"""
View Models - Data Transfer Objects for UI/Backend separation.

These dataclasses define the exact data the UI needs without coupling to backend implementations.
All view models are immutable and serializable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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
    defense_pct: int = 0    # % damage reduction from equipped armor

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StatsView:
        """Rebuild from an event payload made by to_dict()."""
        return cls(**data)



@dataclass(frozen=True)
class InventoryItemView:
    """Single inventory item representation."""
    id: str
    name: str
    item_type: str
    rarity: str = "common"
    is_equipped: bool = False
    damage: int | None = None
    healing: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InventoryItemView:
        """Rebuild from an event payload made by to_dict()."""
        return cls(**data)



@dataclass(frozen=True)
class InventoryView:
    """Full inventory representation."""
    items: list[InventoryItemView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization."""
        return {
            "items": [item.to_dict() for item in self.items]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InventoryView:
        """Rebuild from an event payload made by to_dict()."""
        return cls(items=[InventoryItemView.from_dict(i) for i in data.get("items", [])])



@dataclass(frozen=True)
class RoomView:
    """Room display data."""
    name: str
    description: str
    id: str = ""
    zone: str = ""
    exits: list[str] = field(default_factory=list)
    enemies: list[str] = field(default_factory=list)      # display names
    npcs: list[str] = field(default_factory=list)         # display names
    enemy_ids: list[str] = field(default_factory=list)    # same order as enemies
    npc_ids: list[str] = field(default_factory=list)      # same order as npcs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomView:
        """Rebuild from an event payload made by to_dict()."""
        return cls(**data)



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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttackView:
        """Rebuild from an event payload made by to_dict()."""
        return cls(**data)



@dataclass(frozen=True)
class CombatView:
    """Combat UI data bundle."""
    enemy_name: str
    enemy_health: int
    enemy_max_health: int
    player_health: int
    player_max_health: int
    enemy_id: str = ""    # for scene sprite lookup
    available_attacks: list[AttackView] = field(default_factory=list)
    usable_items: list[InventoryItemView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization."""
        return {
            "enemy_id": self.enemy_id,
            "enemy_name": self.enemy_name,
            "enemy_health": self.enemy_health,
            "enemy_max_health": self.enemy_max_health,
            "player_health": self.player_health,
            "player_max_health": self.player_max_health,
            "available_attacks": [attack.to_dict() for attack in self.available_attacks],
            "usable_items": [item.to_dict() for item in self.usable_items]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CombatView:
        """Rebuild from an event payload made by to_dict()."""
        return cls(
            enemy_name=data["enemy_name"],
            enemy_health=data["enemy_health"],
            enemy_max_health=data["enemy_max_health"],
            player_health=data["player_health"],
            player_max_health=data["player_max_health"],
            enemy_id=data.get("enemy_id", ""),
            available_attacks=[AttackView.from_dict(a) for a in data.get("available_attacks", [])],
            usable_items=[InventoryItemView.from_dict(i) for i in data.get("usable_items", [])],
        )


