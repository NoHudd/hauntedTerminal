"""Typed identifier aliases.

These are ``NewType``s over ``str`` — zero runtime cost, but they make function
signatures and model fields self-documenting and let a type checker flag when a
RoomId is used where an ItemId is expected. Ids on disk are the YAML map keys or
filename stems (e.g. ``root``, ``segfault_shield``, ``corrupt_process.bin``).
"""
from __future__ import annotations

from typing import NewType

RoomId = NewType("RoomId", str)
ItemId = NewType("ItemId", str)
EnemyId = NewType("EnemyId", str)
NpcId = NewType("NpcId", str)
AbilityId = NewType("AbilityId", str)
AttackId = NewType("AttackId", str)
ClassId = NewType("ClassId", str)
