"""Navigation tables and path arithmetic.

Rooms form a real directory tree and `cd` does path arithmetic over it. This
file pins the three properties that keeps true:

1. the tree is well-formed (every room's parent is itself a room),
2. every path players learned before the tree landed still navigates, and
3. `.`, `..` and relative paths resolve the way a shell resolves them.
"""
from __future__ import annotations

import pytest

from src import room_paths
from src.data_loader import load_room_data

# Paths and shorthands the game shipped with. The tree moved several rooms to
# real FHS locations, but everything a player might have learned must keep
# working — these are all preserved as aliases.
LEGACY_NAV = {
    "/home": "home_grove", "/home/grove": "home_grove", "home": "home_grove",
    "grove": "home_grove",
    "/var": "var_dungeon", "/var/dungeon": "var_dungeon", "var": "var_dungeon",
    "dungeon": "var_dungeon",
    "/mnt": "mnt_forest", "mnt": "mnt_forest", "forest": "mnt_forest",
    "/bin": "bin_armory", "bin": "bin_armory", "armory": "bin_armory",
    "/usr": "usr_lib_arcane", "/usr/lib": "usr_lib_arcane",
    "/usr/lib/arcane": "usr_lib_arcane", "usr": "usr_lib_arcane",
    "lib": "usr_lib_arcane", "arcane": "usr_lib_arcane",
    "/usr/share": "usr_share_games", "/usr/share/games": "usr_share_games",
    "share": "usr_share_games", "games": "usr_share_games",
    "/usr/share/games/cowsay": "cowsay_secret", "/cowsay": "cowsay_secret",
    "cowsay": "cowsay_secret",
    "/opt": "opt_mage_tower", "opt": "opt_mage_tower", "tower": "opt_mage_tower",
    "/srv": "srv_warrior_tomb", "srv": "srv_warrior_tomb", "tomb": "srv_warrior_tomb",
    "/proc": "proc_secrets", "/proc/secrets": "proc_secrets", "proc": "proc_secrets",
    "secrets": "proc_secrets",
    "/etc": "etc_hidden_configs", "/etc/configs": "etc_hidden_configs",
    "etc": "etc_hidden_configs", "configs": "etc_hidden_configs",
    "/dev": "dev_null_void", "/dev/null": "dev_null_void", "dev": "dev_null_void",
    "null": "dev_null_void", "void": "dev_null_void",
    "/ghost": "ghost_hidden", "ghost": "ghost_hidden",
    "/archive": "archive", "archive": "archive",
    "/deprecated": "deprecated_dir", "deprecated": "deprecated_dir",
    "/": "root", "root": "root",
    "/core": "core", "core": "core",
    "/mirror": "mirror_sector", "mirror": "mirror_sector",
}


@pytest.fixture(scope="module")
def aliases() -> dict[str, str]:
    return room_paths.refresh_from_rooms(load_room_data())


def test_every_room_parent_is_a_room(aliases: dict[str, str]) -> None:
    """`cd ..` and ancestor permission checks both walk the path upward, so a
    room whose parent path owns no room would be a hole in the filesystem."""
    known = set(room_paths.PATH_TO_ROOM_ID)
    for room_id, path in room_paths.ROOM_ID_TO_PATH.items():
        if path == "/":
            continue
        parent = room_paths.parent_path(path)
        assert parent in known, f"{room_id} at {path}: nothing owns parent {parent}"


def test_root_owns_the_root_path(aliases: dict[str, str]) -> None:
    assert room_paths.room_at("/") == "root"


def test_paths_and_aliases_are_unique(aliases: dict[str, str]) -> None:
    paths = list(room_paths.ROOM_ID_TO_PATH.values())
    assert len(paths) == len(set(paths)), "two rooms claim the same path"


def test_legacy_navigation_still_works(aliases: dict[str, str]) -> None:
    """Anything that navigated before the tree must still navigate."""
    wrong = {
        typed: got for typed, expected in LEGACY_NAV.items()
        if (got := room_paths.resolve(typed, "/", aliases)) != expected
    }
    assert not wrong, f"these no longer reach their room: {wrong}"


PATH_ARITHMETIC = [
    # (typed, current directory, expected room)
    ("/usr/games", "/", "usr_share_games"),
    ("games", "/usr", "usr_share_games"),
    ("self", "/proc", "mirror_sector"),
    ("..", "/usr/games", "usr_lib_arcane"),
    ("..", "/var/tmp", "var_dungeon"),
    ("..", "/", "root"),                       # root is its own parent
    ("../..", "/usr/games/cowsay", "usr_lib_arcane"),
    (".", "/var", "var_dungeon"),
    ("/var/./tmp", "/", "deprecated_dir"),
    ("/var/backups/..", "/", "var_dungeon"),
]


def test_path_arithmetic(aliases: dict[str, str]) -> None:
    wrong = [
        (typed, current, expected, got)
        for typed, current, expected in PATH_ARITHMETIC
        if (got := room_paths.resolve(typed, current, aliases)) != expected
    ]
    assert not wrong, f"(typed, cwd, expected, got): {wrong}"


def test_unknown_paths_do_not_resolve(aliases: dict[str, str]) -> None:
    for typed in ("/nope", "nope", "/usr/nope", "../nope"):
        assert room_paths.resolve(typed, "/usr", aliases) is None


def test_children_and_ancestors(aliases: dict[str, str]) -> None:
    children = {room_paths.room_path(r) for r in room_paths.children_of("/var")}
    assert children == {"/var/backups", "/var/tmp"}
    assert room_paths.ancestors("/usr/games/cowsay") == ["/", "/usr", "/usr/games"]
    assert room_paths.ancestors("/") == []
