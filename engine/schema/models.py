"""Pydantic content models — the single source of truth for YAML key names.

Design notes (strangler phase):
- ``extra="allow"`` keeps the large tail of optional content fields (flavor,
  effects, tutorial hooks) without rejecting them, while still typing and
  validating the *critical* fields and every cross-file id-reference.
- Field names are snake_case to match the current YAML exactly. camelCase is
  reserved for serialized *save* JSON (Phase 4), not content files — per
  docs/REWRITE_PLAN.md and ~/.claude/CLAUDE.md.
- ``id`` is injected by the loader from the map key / filename stem; it is not
  present in the YAML body itself.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .ids import (
    AbilityId,
    AttackId,
    ClassId,
    EnemyId,
    ItemId,
    NpcId,
    RoomId,
)


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


def _falsey_to_bool(v: object) -> bool:
    """Coerce the messy 'locked' field to bool.

    Content uses ``locked: true``, ``locked: false``, ``locked: []`` (empty
    list, meaning unlocked), and omits it (None). Treat empty/None/false as
    unlocked; any truthy value as locked.
    """
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (list, dict, str)):
        return bool(v)
    return bool(v)


class Room(_Base):
    id: RoomId = Field(default=RoomId(""))
    name: str
    description: str = ""
    detailed_description: str = ""
    exits: list[RoomId] = Field(default_factory=list)
    items: list[ItemId] = Field(default_factory=list)
    npcs: list[NpcId] = Field(default_factory=list)
    enemies: list[EnemyId] = Field(default_factory=list)
    hidden: bool = False
    locked: bool = False
    key_required: ItemId | None = None
    zone: str = ""
    zone_level: int = 0
    requires_sudo: bool = False
    class_restriction: str = ""
    path: str = ""
    aliases: list[str] = Field(default_factory=list)

    _coerce_locked = field_validator("locked", mode="before")(_falsey_to_bool)
    _coerce_hidden = field_validator("hidden", mode="before")(_falsey_to_bool)
    _coerce_sudo = field_validator("requires_sudo", mode="before")(_falsey_to_bool)


class ClassDisplay(_Base):
    color: str = "white"
    hp_label: str = ""
    hp_color: str = "green"
    dmg_label: str = ""
    dmg_color: str = "red"
    weapon_name: str = ""
    echo_description: str = ""


class CharacterClass(_Base):
    id: ClassId = Field(default=ClassId(""))
    name: str
    description: str = ""
    base_health: int = Field(gt=0)
    base_damage: int = Field(gt=0)
    starter_weapon: ItemId | None = None
    starter_abilities: list[AbilityId] = Field(default_factory=list)
    attacks: list[AttackId] = Field(default_factory=list)
    preferred_zones: list[str] = Field(default_factory=list)
    power_scaling: str = "balanced"
    loot_preference: list[str] = Field(default_factory=list)
    display: ClassDisplay = Field(default_factory=ClassDisplay)


class Drop(_Base):
    item: ItemId
    chance: int = Field(ge=0, le=100)


class Enemy(_Base):
    id: EnemyId = Field(default=EnemyId(""))
    name: str
    short_description: str = ""
    description: str = ""
    health: int = Field(gt=0)
    damage: int = Field(ge=0)
    is_boss: bool = False
    auto_attack: bool = True
    drops: list[Drop] = Field(default_factory=list)
    tier: int | None = None
    experience: int = 0
    dialogue: str = ""
    attack_patterns: list = Field(default_factory=list)
    loot_table: list = Field(default_factory=list)

    @field_validator("dialogue", mode="before")
    @classmethod
    def _dialogue_to_str(cls, v: object) -> str:
        return "" if v is None else str(v)


class Item(_Base):
    id: ItemId = Field(default=ItemId(""))
    name: str
    description: str = ""
    type: str = "misc"
    rarity: str = "common"
    allowed_classes: list[str] = Field(default_factory=list)
    persistence: str = "persistent"
    # key items only:
    unlocks: list[RoomId] = Field(default_factory=list)

    @field_validator("rarity", mode="before")
    @classmethod
    def _rarity_to_str(cls, v: object) -> str:
        # Tolerate malformed scalar rarities in content (e.g. master_key's
        # `rarity: 1`) rather than blocking the whole load on a data typo. The
        # content test suite flags these separately as data-quality findings.
        return "common" if v is None else str(v)


class Ability(_Base):
    id: AbilityId = Field(default=AbilityId(""))
    name: str
    description: str = ""
    # 'class' is a Python keyword — expose as char_class, accept YAML key "class".
    char_class: str = Field(default="all", alias="class")
    cooldown: int = 0
    bonus_damage: int = 0


class Attack(_Base):
    id: AttackId = Field(default=AttackId(""))
    name: str
    description: str = ""
    bonus_damage: int = 0
    cooldown: int = 0
    accuracy: int = 100
    type: str = "physical"


class NPC(_Base):
    id: NpcId = Field(default=NpcId(""))
    name: str
    short_description: str = ""
    description: str = ""
    dialogues: list[str] = Field(default_factory=list)
    location: RoomId | None = None
