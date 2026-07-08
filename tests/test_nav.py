"""Navigation tables are built from room YAML and must match the legacy hardcoded maps.

The two dicts below are the exact tables the game shipped with (src/room_paths.py's
ROOM_ID_TO_PATH and command_handler's room_aliases). build_nav_tables must reproduce them
byte-for-byte from the rooms' path/aliases fields, guaranteeing navigation is unchanged.
"""
from __future__ import annotations

from src.data_loader import load_room_data
from src.room_paths import build_nav_tables

LEGACY_ID_TO_PATH = {
    "home_grove": "/home", "var_dungeon": "/var", "mnt_forest": "/mnt",
    "bin_armory": "/bin", "usr_lib_arcane": "/usr", "opt_mage_tower": "/opt",
    "srv_warrior_tomb": "/srv", "proc_secrets": "/proc", "etc_hidden_configs": "/etc",
    "dev_null_void": "/dev", "ghost_hidden": "/ghost", "archive": "/archive",
    "deprecated_dir": "/deprecated", "root": "/", "core": "/core",
    "cowsay_secret": "/cowsay", "mirror_sector": "/mirror",
    "usr_share_games": "/usr/share/games",
}

LEGACY_ALIAS_TO_ID = {
    "/home": "home_grove", "/home/grove": "home_grove", "/var": "var_dungeon",
    "/var/dungeon": "var_dungeon", "/mnt": "mnt_forest", "/mnt/forest": "mnt_forest",
    "/bin": "bin_armory", "/bin/armory": "bin_armory", "/usr": "usr_lib_arcane",
    "/usr/lib": "usr_lib_arcane", "/usr/lib/arcane": "usr_lib_arcane",
    "/usr/share": "usr_share_games", "/usr/share/games": "usr_share_games",
    "/usr/share/games/cowsay": "cowsay_secret", "/cowsay": "cowsay_secret",
    "/opt": "opt_mage_tower", "/opt/tower": "opt_mage_tower",
    "/opt/mage_tower": "opt_mage_tower", "/srv": "srv_warrior_tomb",
    "/srv/tomb": "srv_warrior_tomb", "/srv/warrior_tomb": "srv_warrior_tomb",
    "/proc": "proc_secrets", "/proc/secrets": "proc_secrets",
    "/etc": "etc_hidden_configs", "/etc/configs": "etc_hidden_configs",
    "/dev": "dev_null_void", "/dev/null": "dev_null_void", "/ghost": "ghost_hidden",
    "/archive": "archive", "/deprecated": "deprecated_dir", "/": "root",
    "/root": "root", "/core": "core",
    "home": "home_grove", "grove": "home_grove", "var": "var_dungeon",
    "dungeon": "var_dungeon", "mnt": "mnt_forest", "forest": "mnt_forest",
    "bin": "bin_armory", "armory": "bin_armory", "usr": "usr_lib_arcane",
    "lib": "usr_lib_arcane", "arcane": "usr_lib_arcane", "share": "usr_share_games",
    "games": "usr_share_games", "cowsay": "cowsay_secret", "opt": "opt_mage_tower",
    "tower": "opt_mage_tower", "srv": "srv_warrior_tomb", "tomb": "srv_warrior_tomb",
    "proc": "proc_secrets", "secrets": "proc_secrets", "etc": "etc_hidden_configs",
    "configs": "etc_hidden_configs", "dev": "dev_null_void", "null": "dev_null_void",
    "void": "dev_null_void", "ghost": "ghost_hidden", "deprecated": "deprecated_dir",
    "archive": "archive", "root": "root", "core": "core",
}


def test_built_tables_match_legacy() -> None:
    id_to_path, alias_to_id = build_nav_tables(load_room_data())
    assert id_to_path == LEGACY_ID_TO_PATH
    assert alias_to_id == LEGACY_ALIAS_TO_ID
