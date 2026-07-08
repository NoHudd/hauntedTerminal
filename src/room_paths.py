#!/usr/bin/env python3
"""Room id <-> filesystem path / navigation aliases.

This is game content: how a room id maps to the path a player types (e.g.
``var_dungeon`` -> ``/var``) and which strings navigate to it (``var``,
``dungeon``, ``/var/dungeon``). Both tables are now built at load time from each
room's ``path`` / ``aliases`` fields in its YAML, so there is a single source of
truth per room instead of two hand-maintained dicts.

``ROOM_ID_TO_PATH`` stays a module-level dict (mutated in place by
``refresh_from_rooms``) so existing importers — notably the UI's
``view_builder`` — keep a stable reference.
"""
from __future__ import annotations

# id -> canonical display path. Populated from room data at load time.
ROOM_ID_TO_PATH: dict[str, str] = {}


def build_nav_tables(rooms: dict) -> tuple[dict[str, str], dict[str, str]]:
    """From room data (id -> room dict or model) build (id_to_path, alias_to_id).

    - id_to_path: room id -> its ``path`` (display only; empty paths skipped).
    - alias_to_id: each entry in a room's ``aliases`` -> that room id. Nothing is
      auto-added (not the path, not the id) — the aliases list is authoritative,
      matching the game's historical navigation table exactly.
    """
    id_to_path: dict[str, str] = {}
    alias_to_id: dict[str, str] = {}
    for rid, room in rooms.items():
        if isinstance(room, dict):
            path = room.get("path", "") or ""
            aliases = room.get("aliases", []) or []
        else:
            path = getattr(room, "path", "") or ""
            aliases = getattr(room, "aliases", []) or []
        if path:
            id_to_path[str(rid)] = path
        for alias in aliases:
            alias_to_id[str(alias)] = str(rid)
    return id_to_path, alias_to_id


def refresh_from_rooms(rooms: dict) -> dict[str, str]:
    """Rebuild ROOM_ID_TO_PATH in place; return the alias -> id table."""
    id_to_path, alias_to_id = build_nav_tables(rooms)
    ROOM_ID_TO_PATH.clear()
    ROOM_ID_TO_PATH.update(id_to_path)
    return alias_to_id


def room_path(room_id: str) -> str:
    """Path for a room id, falling back to the id itself."""
    return ROOM_ID_TO_PATH.get(room_id, room_id)
