"""Per-verb command tests (rewrite Phase 3).

As each verb migrates from CommandHandler into a Command class, it gets a test
here asserting its behaviour through the headless GameSession — the safety net
for the command-pattern split.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.commands import build_registry


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tester", "guardian")
    try:
        yield s
    finally:
        s.close()


def _text(lines: list[str]) -> str:
    return "\n".join(lines)


# --- registry ---------------------------------------------------------------

ALL_VERBS = (
    "help", "shortcuts", "pwd", "journal", "inventory", "inv", "keys", "map",
    "find", "ps", "save", "quit", "exit", "drop", "equip", "examine", "talk",
    "take", "cat", "ls", "cd", "use", "attack",
)


def test_registry_covers_every_verb() -> None:
    registry = build_registry()
    for name in ALL_VERBS:
        assert name in registry


def test_legacy_dispatch_is_empty() -> None:
    # Phase 3 complete: no verb should remain on the legacy dict.
    from src.commands import build_registry  # noqa: F401
    s = GameSession()
    try:
        s.new_game("T", "guardian")
        assert s.engine.cmd_handler.commands == {}
    finally:
        s.close()


def test_inventory_alias_matches(session: GameSession) -> None:
    assert _text(session.submit("inv")) == _text(session.submit("inventory"))


# --- migrated verbs ---------------------------------------------------------

def test_pwd_shows_current_room(session: GameSession) -> None:
    out = _text(session.submit("pwd"))
    assert "home_grove" in out
    session.submit("cd root")
    assert "root" in _text(session.submit("pwd"))


def test_help_lists_commands(session: GameSession) -> None:
    out = _text(session.submit("help"))
    assert "Available Commands" in out
    for verb in ("cd", "ls", "attack", "inventory"):
        assert verb in out


def test_shortcuts_shows_tips(session: GameSession) -> None:
    out = _text(session.submit("shortcuts"))
    assert "Item Shortcuts" in out
    assert "health_packet" in out


def test_journal_empty_at_start(session: GameSession) -> None:
    out = _text(session.submit("journal"))
    assert "JOURNAL" in out
    assert "No memories restored" in out


def test_inventory_shows_starter_items(session: GameSession) -> None:
    out = _text(session.submit("inventory"))
    assert "Inventory" in out


def test_keys_shows_progression(session: GameSession) -> None:
    out = _text(session.submit("keys"))
    assert "KEY PROGRESSION" in out
    assert "lib_key" in out


def test_map_renders(session: GameSession) -> None:
    out = _text(session.submit("map"))
    # Either the empty-map hint or the system map header; must not error.
    assert "MAP" in out or "map is empty" in out


def test_ps_lists_processes(session: GameSession) -> None:
    out = _text(session.submit("ps"))
    assert "PID" in out


def test_find_usage_and_full_args(session: GameSession) -> None:
    # Bare find -> usage.
    assert "Usage" in _text(session.submit("find"))
    # Multi-token args must reach the command: the "-name" branch requires 3
    # tokens, so reaching "No such file" (not the usage message) proves the full
    # arg list arrived. The legacy dispatcher truncated to the first token, which
    # would have produced the usage message instead.
    out = _text(session.submit("find /dev -name null"))
    assert "No such file" in out


def test_save_writes_success(session: GameSession) -> None:
    out = _text(session.submit("save"))
    assert "saved successfully" in out


def test_quit_with_progress_prompts_and_cancels(session: GameSession) -> None:
    # Make progress so quit asks to confirm (no-progress quit calls exit()).
    session.submit("cd root")
    prompt = _text(session.submit("quit"))
    assert "unsaved progress" in prompt
    cancelled = _text(session.submit("c"))
    assert "cancelled" in cancelled.lower()


def test_drop_without_item_errors(session: GameSession) -> None:
    assert "No item specified" in _text(session.submit("drop"))


def test_equip_without_weapon_errors(session: GameSession) -> None:
    assert "No weapon specified" in _text(session.submit("equip"))


def test_examine_missing_item_errors(session: GameSession) -> None:
    assert "Cannot find" in _text(session.submit("examine ghost_item_xyz"))


def test_talk_missing_npc_errors(session: GameSession) -> None:
    assert "Cannot find" in _text(session.submit("talk ghost_npc_xyz"))


def test_take_without_item_errors(session: GameSession) -> None:
    assert "No item specified" in _text(session.submit("take"))


def test_take_missing_item_errors(session: GameSession) -> None:
    assert "Cannot find" in _text(session.submit("take ghost_item_xyz"))


def test_cat_without_file_errors(session: GameSession) -> None:
    assert "No file specified" in _text(session.submit("cat"))


def test_use_without_item_errors(session: GameSession) -> None:
    assert "No item specified" in _text(session.submit("use"))


def test_attack_nothing_here_errors(session: GameSession) -> None:
    # home_grove has no enemies at start.
    assert "Nothing to attack" in _text(session.submit("attack"))


def test_ls_lists_room_contents(session: GameSession) -> None:
    out = _text(session.submit("ls"))
    # home_grove has files; must render a section header, not error.
    assert "Error" not in out
    assert "Files:" in out or "No files" in out


def test_cd_and_pwd_track_room(session: GameSession) -> None:
    session.submit("cd root")
    assert "root" in _text(session.submit("pwd"))


def test_cat_reads_room_file(session: GameSession) -> None:
    # home_grove contains readme_txt_corrupt; cat must render it, not error.
    out = _text(session.submit("cat readme_txt_corrupt"))
    assert "Cannot find" not in out
    assert "Error" not in out  # would appear if the command raised
    # Renders "[bold]<name>[/bold]\n\n<content>"
    assert "[bold]" in out and out.strip()
