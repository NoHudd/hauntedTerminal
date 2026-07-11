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

from engine.schema import DanglingReferenceError

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


def link(content: GameContent) -> GameContent:
    """Enforce load-bearing referential integrity; raise on any dangling ref."""
    problems = find_broken_references(content) + find_nav_problems(content)
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
    key must be from the known vocabulary (docs/NPC_DIALOGUE_SPEC.md)."""
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
