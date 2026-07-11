"""Content loading + linking. Load into typed models, then enforce id-refs."""
from __future__ import annotations

from .linker import (
    find_broken_references,
    find_dialogue_problems,
    find_reference_warnings,
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
    "find_reference_warnings",
    "load_rooms",
    "load_items",
    "load_enemies",
    "load_npcs",
    "load_classes",
    "load_abilities",
    "load_attacks",
]
