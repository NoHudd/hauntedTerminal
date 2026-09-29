#!/usr/bin/env python3
"""Room id <-> filesystem path, and the tree operations `cd` needs.

This is game content: how a room id maps to the path a player types (e.g.
``var_dungeon`` -> ``/var``) and which strings navigate to it (``var``,
``dungeon``, ``/var/log``). Both tables are built at load time from each room's
``path`` / ``aliases`` YAML fields, so there is a single source of truth per room.

The rooms form a real directory tree: every room's parent path is itself a room
(``engine.content.linker.find_tree_problems`` enforces this). That lets ``cd``
behave like a shell — absolute paths, relative paths, ``.`` and ``..`` — instead
of hopping between hand-drawn map edges.

``ROOM_ID_TO_PATH`` stays a module-level dict (mutated in place by
``refresh_from_rooms``) so existing importers keep a stable reference.
"""
from __future__ import annotations

from typing import Any

# id -> canonical display path. Populated from room data at load time.
ROOM_ID_TO_PATH: dict[str, str] = {}
# canonical path -> id. The inverse of the above; the tree lookups use it.
PATH_TO_ROOM_ID: dict[str, str] = {}

ROOT_PATH = "/"


def _room_field(room: Any, key: str, default: Any) -> Any:
    """Read a field from a room that may be a dict (tests) or a typed model."""
    if isinstance(room, dict):
        return room.get(key, default) or default
    return getattr(room, key, default) or default


def build_nav_tables(rooms: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """From room data (id -> room dict or model) build (id_to_path, alias_to_id).

    - id_to_path: room id -> its ``path`` (display + tree position).
    - alias_to_id: each entry in a room's ``aliases`` -> that room id. Aliases are
      the extra strings a player may type (legacy paths, bare names); the
      canonical path is registered separately by ``refresh_from_rooms``.
    """
    id_to_path: dict[str, str] = {}
    alias_to_id: dict[str, str] = {}
    for rid, room in rooms.items():
        path = _room_field(room, "path", "")
        aliases = _room_field(room, "aliases", [])
        if path:
            id_to_path[str(rid)] = path
        for alias in aliases:
            alias_to_id[str(alias).lower()] = str(rid)
    return id_to_path, alias_to_id


def refresh_from_rooms(rooms: dict[str, Any]) -> dict[str, str]:
    """Rebuild the path tables in place; return the alias -> id table."""
    id_to_path, alias_to_id = build_nav_tables(rooms)
    ROOM_ID_TO_PATH.clear()
    ROOM_ID_TO_PATH.update(id_to_path)
    PATH_TO_ROOM_ID.clear()
    PATH_TO_ROOM_ID.update({path: rid for rid, path in id_to_path.items()})
    return alias_to_id


def room_path(room_id: str) -> str:
    """Path for a room id, falling back to the id itself."""
    return ROOM_ID_TO_PATH.get(room_id, room_id)


def room_at(path: str) -> str | None:
    """Room id sitting at an exact canonical path, if any."""
    return PATH_TO_ROOM_ID.get(path)


# --- pure path arithmetic ----------------------------------------------------


def normalize(path: str) -> str:
    """Collapse a path the way a shell does: resolve ``.``/``..``, drop empty
    segments and any trailing slash. ``..`` at the root stays at the root."""
    absolute = path.startswith("/")
    parts: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    joined = "/".join(parts)
    return ("/" + joined) if absolute else joined


def resolve_path(typed: str, current_path: str) -> str:
    """Absolutise a typed path against the current directory, then normalize."""
    if typed.startswith("/"):
        return normalize(typed)
    base = current_path if current_path.startswith("/") else ROOT_PATH
    return normalize(f"{base}/{typed}")


def parent_path(path: str) -> str:
    """The containing directory. The root is its own parent, as in a real shell."""
    path = normalize(path)
    if path == ROOT_PATH:
        return ROOT_PATH
    head = path.rsplit("/", 1)[0]
    return head or ROOT_PATH


def ancestors(path: str) -> list[str]:
    """Every directory that must be traversed to reach ``path``, root first,
    excluding ``path`` itself. Traversing a directory needs permission on each
    of these, exactly as a real filesystem needs +x on every ancestor."""
    path = normalize(path)
    if path == ROOT_PATH:
        return []
    out = [ROOT_PATH]
    parts = [p for p in path.split("/") if p]
    for i in range(1, len(parts)):
        out.append("/" + "/".join(parts[:i]))
    return out


def children_of(path: str) -> list[str]:
    """Room ids whose parent path is ``path``, sorted by path."""
    path = normalize(path)
    kids = [
        rid for rid, rpath in ROOM_ID_TO_PATH.items()
        if rpath != path and parent_path(rpath) == path
    ]
    return sorted(kids, key=lambda rid: ROOM_ID_TO_PATH[rid])


def basename(path: str) -> str:
    """Final segment of a path; the root renders as ``/``."""
    path = normalize(path)
    return ROOT_PATH if path == ROOT_PATH else path.rsplit("/", 1)[-1]


def resolve(typed: str, current_path: str, aliases: dict[str, str]) -> str | None:
    """Resolve what a player typed to a room id, or None.

    Tries, in order: an exact alias, then real path arithmetic (absolute or
    relative, honouring ``.`` and ``..``), then a bare room id. Aliases win so
    that established shorthands (``dungeon``, ``/var/log``) keep working even
    when they are not real tree positions.
    """
    typed = (typed or "").strip()
    if not typed:
        return None

    alias_hit = aliases.get(typed.lower())
    if alias_hit:
        return alias_hit

    at_path = room_at(resolve_path(typed, current_path))
    if at_path:
        return at_path

    if typed in ROOM_ID_TO_PATH:
        return typed
    return None
