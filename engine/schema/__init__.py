"""Typed content schema for HFSE. See models.py for design notes."""
from __future__ import annotations

from .errors import (
    ContentError,
    ContentValidationError,
    DanglingReferenceError,
)
from .ids import (
    AbilityId,
    AttackId,
    ClassId,
    EnemyId,
    ItemId,
    NpcId,
    RoomId,
)
from .models import (
    NPC,
    Ability,
    Attack,
    CharacterClass,
    ClassDisplay,
    Drop,
    Enemy,
    Item,
    Room,
)

__all__ = [
    "ContentError",
    "ContentValidationError",
    "DanglingReferenceError",
    "RoomId",
    "ItemId",
    "EnemyId",
    "NpcId",
    "AbilityId",
    "AttackId",
    "ClassId",
    "Room",
    "CharacterClass",
    "ClassDisplay",
    "Drop",
    "Enemy",
    "Item",
    "Ability",
    "Attack",
    "NPC",
]
