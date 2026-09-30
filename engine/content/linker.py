"""Referential-integrity linker.

Resolves every cross-file id-reference in loaded content and raises
DanglingReferenceError if any points at something that does not exist. This is
the enforced, fail-loud replacement for the old log-only
``_validate_data_references`` (src/game_engine.py:170) — and unlike it, this runs
on both fresh-start and save-load paths and actually stops the game.

All problems are collected and reported together, so a content author sees every
broken reference in one run rather than fixing them one crash at a time.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from engine.schema import DanglingReferenceError, RoomId

from .world import GameContent


def find_broken_references(content: GameContent) -> list[str]:
    """Load-bearing dangling references (empty == clean).

    These refs are used to move the player, spawn entities, gate progression, or
    build a character. A dangling one can crash the game or soft-lock a
    playthrough, so ``link()`` raises on any of them.
    """
    problems: list[str] = []
    rooms: set[str] = {str(k) for k in content.rooms}
    items: set[str] = {str(k) for k in content.items}
    enemies: set[str] = {str(k) for k in content.enemies}
    npcs: set[str] = {str(k) for k in content.npcs}
    abilities: set[str] = {str(k) for k in content.abilities}
    attacks: set[str] = {str(k) for k in content.attacks}

    def check(ref: str | None, universe: set[str], where: str, kind: str) -> None:
        if ref and ref not in universe:
            problems.append(f"{where}: references unknown {kind} '{ref}'")

    for rid, room in content.rooms.items():
        for exit_ref in room.exits:
            check(exit_ref, rooms, f"room '{rid}' exit", "room")
        for item_ref in room.items:
            check(item_ref, items, f"room '{rid}' items", "item")
        for npc_ref in room.npcs:
            check(npc_ref, npcs, f"room '{rid}' npcs", "npc")
        for enemy_ref in room.enemies:
            check(enemy_ref, enemies, f"room '{rid}' enemies", "enemy")
        check(room.key_required, items, f"room '{rid}' key_required", "item")

    for cid, klass in content.classes.items():
        check(klass.starter_weapon, items, f"class '{cid}' starter_weapon", "item")
        check(klass.starter_armor, items, f"class '{cid}' starter_armor", "item")
        for ability_ref in klass.starter_abilities:
            check(ability_ref, abilities, f"class '{cid}' starter_abilities", "ability")
        for attack_ref in klass.attacks:
            check(attack_ref, attacks, f"class '{cid}' attacks", "attack")

    for eid, enemy in content.enemies.items():
        for drop in enemy.drops:
            check(drop.item, items, f"enemy '{eid}' drops", "item")

    return problems


def find_nav_problems(content: GameContent) -> list[str]:
    """Room path/alias integrity (empty == clean).

    Every room needs a canonical ``path``; paths must be unique; and no alias may
    resolve to two different rooms. A collision here means ``cd`` would silently
    send the player to the wrong room, so ``link()`` treats these as fatal.
    """
    problems: list[str] = []
    path_owner: dict[str, str] = {}
    alias_owner: dict[str, str] = {}
    for rid, room in content.rooms.items():
        if not room.path:
            problems.append(f"room '{rid}': missing 'path'")
        elif room.path in path_owner:
            problems.append(
                f"room '{rid}': path '{room.path}' already used by '{path_owner[room.path]}'"
            )
        else:
            path_owner[room.path] = str(rid)
        for alias in room.aliases:
            if alias in alias_owner and alias_owner[alias] != str(rid):
                problems.append(
                    f"alias '{alias}' maps to both '{alias_owner[alias]}' and '{rid}'"
                )
            else:
                alias_owner[alias] = str(rid)
    return problems


def _parent_of(path: str) -> str:
    """Containing directory of a canonical room path; the root is its own parent."""
    if path == "/":
        return "/"
    head = path.rsplit("/", 1)[0]
    return head or "/"


def find_tree_problems(content: GameContent) -> list[str]:
    """Directory-tree integrity (empty == clean).

    Rooms form a real filesystem tree, and ``cd`` does path arithmetic over it:
    ``cd ..`` walks to the parent, and entering a room requires permission on
    every ancestor. Both break if a room's parent path is not itself a room, so a
    gap here is fatal rather than cosmetic.
    """
    problems: list[str] = []
    by_path: dict[str, str] = {}
    for rid, room in content.rooms.items():
        if room.path:
            by_path[room.path] = str(rid)

    if "/" not in by_path:
        problems.append("no room owns the root path '/'")

    for rid, room in content.rooms.items():
        if not room.path:
            continue  # missing-path is reported by find_nav_problems
        if not room.path.startswith("/"):
            problems.append(f"room '{rid}': path '{room.path}' is not absolute")
            continue
        if room.path == "/":
            continue
        parent = _parent_of(room.path)
        if parent not in by_path:
            problems.append(
                f"room '{rid}': path '{room.path}' has no parent directory — "
                f"nothing owns '{parent}'"
            )
    return problems


def find_reference_warnings(content: GameContent) -> list[str]:
    """Advisory dangling references (empty == clean).

    These refs are secondary — a dangling one is dead content (a key that
    unlocks nothing, an NPC pointed at no room) rather than a crash. Reported,
    but not fatal, so a single content typo does not block the whole game.
    """
    warnings: list[str] = []
    rooms = set(content.rooms)

    for iid, item in content.items.items():
        for room_id in item.unlocks:
            if room_id not in rooms:
                warnings.append(
                    f"item '{iid}' unlocks: references unknown room '{room_id}'"
                )
    for nid, npc in content.npcs.items():
        if npc.location and npc.location not in rooms:
            warnings.append(
                f"npc '{nid}' location: references unknown room '{npc.location}'"
            )
    return warnings


def _room_lookup(content: GameContent) -> dict[str, str]:
    """Every string a key may use for a room (id, path, alias) -> room id."""
    table: dict[str, str] = {}
    for rid, room in content.rooms.items():
        table[str(rid).lower()] = str(rid)
        if room.path:
            table[room.path.lower()] = str(rid)
        for alias in room.aliases:
            table[alias.lower()] = str(rid)
    return table


def find_lock_problems(content: GameContent) -> list[str]:
    """Keys and locks must agree (empty == clean).

    A lock with no key can never open; a key whose ``unlocks`` misses the room
    that asks for it opens nothing on ``use``; a key that claims a room guarded
    by a different key is lying to the player. The reference checks above only
    prove these ids exist, not that they point at each other.
    """
    problems: list[str] = []
    lookup = _room_lookup(content)
    for rid, room in content.rooms.items():
        if room.locked and not room.key_required:
            problems.append(f"room '{rid}': locked, but names no key_required")
        if room.key_required and not room.locked:
            problems.append(
                f"room '{rid}': key_required '{room.key_required}', but it is not locked"
            )
        key = content.items.get(room.key_required) if room.key_required else None
        if key is None:
            continue  # a dangling key_required is find_broken_references' job
        if key.type != "key":
            problems.append(
                f"room '{rid}': key_required '{room.key_required}' is a {key.type}, not a key"
            )
        opens = {lookup.get(str(target).lower(), str(target)) for target in key.unlocks}
        if str(rid) not in opens:
            problems.append(
                f"room '{rid}': needs '{room.key_required}', but that key's unlocks "
                "does not list it"
            )
    for iid, item in content.items.items():
        for target in item.unlocks:
            target_id = lookup.get(str(target).lower())
            if target_id is None:
                continue  # an unknown room is reported by find_reference_warnings
            guard = content.rooms[RoomId(target_id)].key_required
            if guard != iid:
                problems.append(
                    f"item '{iid}': unlocks '{target}', which "
                    + (f"requires '{guard}' instead" if guard else "has no lock")
                )
    return problems


# Content fields no code reads yet. The schema declares every field the game
# reads, so an undeclared field is authored intent the game ignores — the
# "phantom reward" bug class. These are known and accepted for now; anything
# else undeclared fails validation, as does an entry here that no content uses.
UNIMPLEMENTED_FIELDS: dict[str, frozenset[str]] = {
    "room": frozenset({
        "boss_room", "class_affinity", "easter_egg_trigger", "easter_egg_zone",
        "final_confrontation", "gate_guardian", "level_requirement",
        "special_event", "story_beats", "story_location", "visibility_requirement",
    }),
    "item": frozenset({
        "auto_trigger", "consumed_on_take", "max_uses_per_run",
        "only_in_unlocked", "readable", "trigger_condition", "triggers_npc_spawn",
    }),
    "enemy": frozenset({
        "level_requirement", "loot", "on_defeat", "resistances", "weaknesses",
    }),
    "npc": frozenset({
        "awakening_guide", "detailed_description", "easter_egg_npc", "gate_guardian",
        "grants_unique_item", "helpful_guide", "hostile", "interaction_hints",
        "lore_guide", "merchant", "requires_key", "story_npc", "unlocks_room",
    }),
}


def find_flag_problems(content: GameContent) -> list[str]:
    """Room flags must be findable (empty == clean): the flag file must be an
    item placed in that room, the text must carry FLAG{...}, and a beginner
    must be told what to type."""
    problems: list[str] = []
    for rid, room in content.rooms.items():
        flag = room.flag
        if flag is None:
            continue
        if flag.via in ("cat", "grep"):
            if flag.file is None:
                problems.append(f"room '{rid}': a {flag.via} flag needs a file")
            elif flag.file not in content.items:
                problems.append(f"room '{rid}': flag file '{flag.file}' is not an item")
            elif flag.file not in room.items:
                problems.append(
                    f"room '{rid}': flag file '{flag.file}' is not in this room's items"
                )
        if flag.via in ("kill", "defeat"):
            enemy = content.enemies.get(flag.enemy) if flag.enemy else None
            if enemy is None:
                problems.append(f"room '{rid}': {flag.via} flag names no known enemy")
            elif flag.via == "defeat" and flag.enemy not in room.enemies:
                problems.append(
                    f"room '{rid}': defeat flag enemy '{flag.enemy}' is not in its enemies"
                )
            elif flag.via == "kill":
                if flag.pid <= 1 or not flag.process.strip():
                    problems.append(f"room '{rid}': kill flag needs a pid > 1 and a process")
                if flag.enemy in room.enemies or not enemy.pool_excluded:
                    problems.append(
                        f"room '{rid}': rogue '{flag.enemy}' must be pool_excluded and "
                        "not already in the room's enemies"
                    )
        if "FLAG{" not in flag.text:
            problems.append(f"room '{rid}': flag text has no FLAG{{...}}")
        if not flag.nudge.strip() or not flag.command.strip():
            problems.append(f"room '{rid}': flag needs both a nudge and a command")
        if flag.via not in ("cat", "grep", "kill", "defeat"):
            problems.append(
                f"room '{rid}': flag via '{flag.via}' is not cat, grep, kill or defeat"
            )
        if flag.via == "grep":
            item = content.items.get(flag.file) if flag.file else None
            if item is None or item.log is None:
                problems.append(f"room '{rid}': grep flag file '{flag.file}' has no log")
            elif flag.text not in item.log.flag_line:
                problems.append(
                    f"room '{rid}': flag text is not in '{flag.file}''s log flag_line"
                )
    return problems


def find_unread_fields(content: GameContent) -> list[str]:
    """Undeclared content fields outside UNIMPLEMENTED_FIELDS (empty == clean)."""
    sections: list[tuple[str, Mapping[Any, BaseModel]]] = [
        ("room", content.rooms),
        ("item", content.items),
        ("enemy", content.enemies),
        ("npc", content.npcs),
        ("class", content.classes),
        ("ability", content.abilities),
        ("attack", content.attacks),
    ]
    problems: list[str] = []
    for kind, entries in sections:
        accepted = UNIMPLEMENTED_FIELDS.get(kind, frozenset())
        used: set[str] = set()
        for eid, model in entries.items():
            for name in model.model_extra or {}:
                used.add(name)
                if name not in accepted:
                    problems.append(
                        f"{kind} '{eid}': field '{name}' is not in the schema, so no "
                        "code reads it (declare it in engine/schema/models.py when "
                        "the game uses it)"
                    )
        for stale in sorted(accepted - used):
            problems.append(
                f"UNIMPLEMENTED_FIELDS['{kind}'] lists '{stale}', but no {kind} uses it"
            )
    return problems


def link(content: GameContent) -> GameContent:
    """Enforce load-bearing referential integrity; raise on any dangling ref."""
    problems = (
        find_broken_references(content)
        + find_nav_problems(content)
        + find_tree_problems(content)
    )
    if problems:
        raise DanglingReferenceError(
            f"{len(problems)} content problem(s):\n  - "
            + "\n  - ".join(problems)
        )
    return content


DIALOGUE_WHEN_KEYS = {"story_flag", "not_story_flag", "has_item", "first_meeting", "game_won"}


def find_dialogue_problems(content: GameContent) -> list[str]:
    """Dangling dialogue-rule references: every rule bank must exist as a
    non-empty list of strings in that NPC's dialogue mapping, and every `when`
    key must be from the known vocabulary (see DIALOGUE_WHEN_KEYS below)."""
    problems: list[str] = []
    for npc_id, npc in content.npcs.items():
        rules = npc.dialogue_rules
        if not rules:
            continue
        banks = npc.dialogue
        for i, rule in enumerate(rules):
            raw_banks = rule.get("banks")
            names: list[object] = (
                list(raw_banks) if isinstance(raw_banks, list)
                else [rule["bank"]] if rule.get("bank") else []
            )
            if not names:
                problems.append(f"npc {npc_id}: dialogue rule {i} names no bank")
            for name in names:
                lines = banks.get(str(name)) if isinstance(banks, dict) else None
                ok = isinstance(lines, list) and bool(lines) and all(
                    isinstance(x, str) for x in lines
                )
                if not ok:
                    problems.append(
                        f"npc {npc_id}: dialogue rule {i} -> bank {name!r} "
                        "missing or not a list of strings"
                    )
            when = rule.get("when")
            for key in (when if isinstance(when, dict) else {}):
                if key not in DIALOGUE_WHEN_KEYS:
                    problems.append(f"npc {npc_id}: dialogue rule {i} unknown condition {key!r}")
    return problems
