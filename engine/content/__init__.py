"""Content loading + linking. Load into typed models, then enforce id-refs."""
from __future__ import annotations

from .linker import (
    find_broken_references,
    find_dialogue_problems,
    find_flag_problems,
    find_key_chain_problems,
    find_lock_problems,
    find_nav_problems,
    find_reference_warnings,
    find_tree_problems,
    find_unread_fields,
    link,
)
from .loader import (
    load_abilities,
    load_attacks,
    load_classes,
    load_enemies,
    load_items,
    load_npcs,
    load_rooms,
)
from .world import GameContent, load_all

__all__ = [
    "GameContent",
    "load_all",
    "link",
    "find_broken_references",
    "find_dialogue_problems",
    "find_flag_problems",
    "find_key_chain_problems",
    "find_lock_problems",
    "find_unread_fields",
    "find_reference_warnings",
    "find_nav_problems",
    "find_tree_problems",
    "load_rooms",
    "load_items",
    "load_enemies",
    "load_npcs",
    "load_classes",
    "load_abilities",
    "load_attacks",
]
