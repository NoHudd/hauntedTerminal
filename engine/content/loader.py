"""Parse-then-validate content loading.

Loads every YAML content file into a typed model (engine.schema). A malformed
document raises ContentValidationError naming the file and id — the failure is
loud and at load time, not a silent ``None`` surfacing mid-play.

Id conventions (preserved from the current game):
- rooms:    filename stem                (root.yml         -> "root")
- enemies:  filename stem, dots kept      (corrupt_process.bin.yml -> "corrupt_process.bin")
- npcs:     filename stem, dots kept      (helper_script.bin.yml   -> "helper_script.bin")
- items:    map key under a category      (weapons.yaml: weapons: {segfault_shield: ...})
- classes:  map key under "classes"
- abilities/attacks: map key under "abilities"/"attacks"
"""
from __future__ import annotations

import glob
import os
from collections.abc import Callable
from typing import TypeVar

import yaml
from pydantic import ValidationError

from engine.schema import (
    NPC,
    Ability,
    AbilityId,
    Attack,
    AttackId,
    CharacterClass,
    ClassId,
    ContentValidationError,
    Enemy,
    EnemyId,
    Item,
    ItemId,
    NpcId,
    Room,
    RoomId,
)

DATA_DIR = "data"

M = TypeVar("M")


def _read_yaml(path: str) -> dict[str, object]:
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def _build(
    model: Callable[..., M], id_value: str, body: dict[str, object], source: str
) -> M:
    try:
        return model(id=id_value, **body)
    except ValidationError as exc:
        raise ContentValidationError(
            f"{source}: '{id_value}' failed {model.__name__} validation:\n{exc}"
        ) from exc


def _stem(filename: str) -> str:
    """Filename stem with dots preserved (only the final extension stripped)."""
    base = os.path.basename(filename)
    for ext in (".yaml", ".yml"):
        if base.endswith(ext):
            return base[: -len(ext)]
    return base


def load_rooms(data_dir: str = DATA_DIR) -> dict[RoomId, Room]:
    out: dict[RoomId, Room] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "rooms", "*.y*ml"))):
        rid = RoomId(_stem(path))
        out[rid] = _build(Room, rid, _read_yaml(path), path)
    return out


def load_enemies(data_dir: str = DATA_DIR) -> dict[EnemyId, Enemy]:
    out: dict[EnemyId, Enemy] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "enemies", "*.y*ml"))):
        eid = EnemyId(_stem(path))
        out[eid] = _build(Enemy, eid, _read_yaml(path), path)
    return out


def load_npcs(data_dir: str = DATA_DIR) -> dict[NpcId, NPC]:
    out: dict[NpcId, NPC] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "npcs", "*.y*ml"))):
        nid = NpcId(_stem(path))
        out[nid] = _build(NPC, nid, _read_yaml(path), path)
    return out


def load_items(data_dir: str = DATA_DIR) -> dict[ItemId, Item]:
    out: dict[ItemId, Item] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.y*ml"))):
        doc = _read_yaml(path)
        # each file is a flat map {item_id: {def}}; type carries the category.
        for item_id, body in doc.items():
            if not isinstance(body, dict):
                continue
            if "type" not in body:
                raise ContentValidationError(f"{path}: item '{item_id}' missing 'type'")
            iid = ItemId(item_id)
            if iid in out:
                raise ContentValidationError(
                    f"{path}: duplicate item id '{item_id}' (already defined elsewhere)"
                )
            out[iid] = _build(Item, iid, body, path)
    return out


def _section(doc: dict[str, object], key: str) -> dict[str, dict[str, object]]:
    """Return a top-level mapping section (e.g. ``classes:``) as id -> body,
    keeping only dict-valued entries. Empty dict if the section is absent."""
    raw = doc.get(key)
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, dict)}


def load_classes(data_dir: str = DATA_DIR) -> dict[ClassId, CharacterClass]:
    doc = _read_yaml(os.path.join(data_dir, "classes.yaml"))
    out: dict[ClassId, CharacterClass] = {}
    for class_id, body in _section(doc, "classes").items():
        cid = ClassId(class_id)
        out[cid] = _build(CharacterClass, cid, body or {}, "classes.yaml")
    return out


def load_abilities(data_dir: str = DATA_DIR) -> dict[AbilityId, Ability]:
    doc = _read_yaml(os.path.join(data_dir, "abilities.yaml"))
    out: dict[AbilityId, Ability] = {}
    for ability_id, body in _section(doc, "abilities").items():
        aid = AbilityId(ability_id)
        out[aid] = _build(Ability, aid, body or {}, "abilities.yaml")
    return out


def load_attacks(data_dir: str = DATA_DIR) -> dict[AttackId, Attack]:
    doc = _read_yaml(os.path.join(data_dir, "attacks.yml"))
    out: dict[AttackId, Attack] = {}
    for attack_id, body in _section(doc, "attacks").items():
        aid = AttackId(attack_id)
        out[aid] = _build(Attack, aid, body or {}, "attacks.yml")
    return out
