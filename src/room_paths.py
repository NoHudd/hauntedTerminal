#!/usr/bin/env python3
"""Room id → filesystem path mapping.

This is game content (how a room id maps to the path a player types, e.g.
``var_dungeon`` -> ``/var``), not view logic. It lives in the domain so both the
command layer (LsCommand's "where you can go" hints) and the UI (exits strip)
can use it without the domain importing the UI layer.
"""
from __future__ import annotations

# The shortest, most intuitive path a user types to reach each room.
ROOM_ID_TO_PATH: dict[str, str] = {
    "home_grove": "/home",
    "var_dungeon": "/var",
    "mnt_forest": "/mnt",
    "bin_armory": "/bin",
    "usr_lib_arcane": "/usr",
    "opt_mage_tower": "/opt",
    "srv_warrior_tomb": "/srv",
    "proc_secrets": "/proc",
    "etc_hidden_configs": "/etc",
    "dev_null_void": "/dev",
    "ghost_hidden": "/ghost",
    "archive": "/archive",
    "deprecated_dir": "/deprecated",
    "root": "/",
    "core": "/core",
    "cowsay_secret": "/cowsay",
    "mirror_sector": "/mirror",
    "usr_share_games": "/usr/share/games",
}


def room_path(room_id: str) -> str:
    """Path for a room id, falling back to the id itself."""
    return ROOM_ID_TO_PATH.get(room_id, room_id)
