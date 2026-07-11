"""
NPC dialogue-bank resolution (pure; headless-testable).

An NPC's `dialogue_rules` is an ORDERED list evaluated against a snapshot of game
state; the first rule whose `when` fully matches supplies the lines. See
docs/NPC_DIALOGUE_SPEC.md for the condition vocabulary.
"""
from __future__ import annotations


def _when_matches(when: dict, state: dict) -> bool:
    for key, expected in when.items():
        if key == "story_flag":
            if not state["flags"].get(expected):
                return False
        elif key == "not_story_flag":
            if state["flags"].get(expected):
                return False
        elif key == "has_item":
            if expected not in state["items"]:
                return False
        elif key == "first_meeting":
            if bool(expected) != (state["npc_id"] not in state["met"]):
                return False
        elif key == "game_won":
            if bool(expected) != bool(state["game_won"]):
                return False
        else:
            # Unknown condition key: never matches (validation flags it at load).
            return False
    return True


def resolve_dialogue_bank(rules, banks, state):
    """Return the matched rule's lines (pooled across `banks:` lists), or None."""
    for rule in rules or []:
        when = rule.get("when") or {}
        if not _when_matches(when, state):
            continue
        names = rule.get("banks") or ([rule["bank"]] if rule.get("bank") else [])
        lines: list[str] = []
        for name in names:
            lines.extend(banks.get(name) or [])
        if lines:
            return lines
    return None
