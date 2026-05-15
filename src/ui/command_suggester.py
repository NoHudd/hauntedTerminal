"""Context-aware autocomplete for the command Input.

Inline ghost-text suggestions based on what the player can act on right now:
inventory items for use/equip/drop, room items for take/cat/examine,
exits for cd, NPCs for talk, enemies for attack.

Press right-arrow to accept the suggestion (Textual default).
"""
from typing import Optional, Callable, List

from textual.suggester import Suggester


# Map common shorthand -> canonical inventory id prefix
_INVENTORY_SHORTCUTS = {
    "hp": "health_packet",
    "heal": "health_packet",
    "health": "health_packet",
    "packet": "health_packet",
    "potion": "health_packet",
    "buffer": "overflowing_buffer",
    "cache": "stable_cache",
    "backup": "legacy_backup",
    "seed": "sudo_seed",
    "shield": "segfault_shield",
    "pointer": "null_pointer",
    "whisper": "daemon_whisper",
}


# Verb -> candidate-source key. Source is resolved at suggestion time
# against the current player + world state.
_VERB_SOURCE = {
    "use": "inventory",
    "equip": "inventory",
    "drop": "inventory",
    "take": "room_items",
    "cat": "room_items",
    "read": "room_items",
    "examine": "room_items",
    "cd": "exits",
    "talk": "npcs",
    "attack": "enemies",
}


class CommandSuggester(Suggester):
    """Suggest the rest of a command from live game state."""

    def __init__(self, get_player: Callable, get_world: Callable, get_aliases: Callable):
        # Disable cache — suggestions depend on mutable game state.
        super().__init__(use_cache=False, case_sensitive=False)
        self._get_player = get_player
        self._get_world = get_world
        self._get_aliases = get_aliases

    async def get_suggestion(self, value: str) -> Optional[str]:
        if not value:
            return None

        # Suggest the verb itself if user is typing the first word
        if " " not in value:
            verb_match = self._suggest_verb(value)
            return verb_match

        verb, _, partial = value.partition(" ")
        verb_lower = verb.lower()
        source = _VERB_SOURCE.get(verb_lower)
        if source is None:
            return None

        candidates = self._candidates_for(source)
        if not candidates:
            return None

        partial_lower = partial.lower()

        # Shortcut hit: 'hp' -> health_packet -> first inventory match prefix
        if source == "inventory":
            shortcut_target = _INVENTORY_SHORTCUTS.get(partial_lower)
            if shortcut_target:
                for candidate in candidates:
                    if candidate.lower().startswith(shortcut_target):
                        return f"{verb} {candidate}"

        for candidate in candidates:
            if candidate.lower().startswith(partial_lower) and candidate.lower() != partial_lower:
                return f"{verb} {candidate}"
        return None

    def _suggest_verb(self, partial: str) -> Optional[str]:
        partial_lower = partial.lower()
        for verb in sorted(_VERB_SOURCE.keys()):
            if verb.startswith(partial_lower) and verb != partial_lower:
                return verb
        return None

    def _candidates_for(self, source: str) -> List[str]:
        player = self._get_player()
        world = self._get_world()
        if player is None or world is None:
            return []

        try:
            if source == "inventory":
                return self._inventory_candidates(player)
            if source == "room_items":
                return list(world.get_items_in_room(player.current_room))
            if source == "exits":
                return self._exit_candidates(player, world)
            if source == "npcs":
                return list(world.get_npcs_in_room(player.current_room))
            if source == "enemies":
                return list(world.get_enemies_in_room(player.current_room))
        except Exception:
            return []
        return []

    def _inventory_candidates(self, player) -> List[str]:
        # Strip instance suffixes like "_1" so users can type the canonical id
        seen: List[str] = []
        for key in player.inventory.keys():
            base = key
            if "_" in key:
                head, _, tail = key.rpartition("_")
                if tail.isdigit():
                    base = head
            if base not in seen:
                seen.append(base)
            if key not in seen:
                seen.append(key)
        return seen

    def _exit_candidates(self, player, world) -> List[str]:
        try:
            current = world.get_room(player.current_room) or {}
            exits = list(current.get("exits", []))
        except Exception:
            exits = []

        # Map room IDs to filesystem-style aliases for display, keep both forms
        aliases = self._get_aliases() or {}
        # Reverse map: room_id -> preferred path alias (longest path wins)
        path_aliases: dict = {}
        for alias, room_id in aliases.items():
            if not alias.startswith("/"):
                continue
            existing = path_aliases.get(room_id)
            if existing is None or len(alias) > len(existing):
                path_aliases[room_id] = alias

        suggestions: List[str] = []
        for room_id in exits:
            path = path_aliases.get(room_id)
            if path:
                suggestions.append(path)
            suggestions.append(room_id)
        return suggestions
