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


def test_inventory_alias_matches(session: GameSession) -> None:
    assert _text(session.submit("inv")) == _text(session.submit("inventory"))


# --- migrated verbs ---------------------------------------------------------

def test_pwd_shows_current_path(session: GameSession) -> None:
    # pwd prints a path, not a room id — that is the whole point of the tree.
    assert "/home" in _text(session.submit("pwd"))
    session.submit("cd /")
    assert _text(session.submit("pwd")).strip().endswith("/[/bold]")


def test_help_lists_commands(session: GameSession) -> None:
    out = _text(session.submit("help"))
    assert "Real Unix commands" in out
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
    session.player.add_to_inventory("lib_key", session.world.get_item("lib_key"))
    out = _text(session.submit("keys"))
    assert "KEYS" in out
    assert "lib_key" in out


def test_tree_renders(session: GameSession) -> None:
    out = _text(session.submit("tree"))
    assert "Discovered filesystem" in out
    assert "home/" in out          # you start there, so it is always discovered
    assert "← you are here" in out


def test_map_is_an_alias_for_tree(session: GameSession) -> None:
    # `map` kept working when it became `tree`; muscle memory should not break.
    assert _text(session.submit("map")) == _text(session.submit("tree"))


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
    # /var/tmp and / are both enemy-free, so no combat swallows the pwd.
    session.submit("cd /var/tmp")
    assert "/var/tmp" in _text(session.submit("pwd"))
    session.submit("cd /home")
    assert "/home" in _text(session.submit("pwd"))
    session.submit("cd ..")           # /home -> /
    assert _text(session.submit("pwd")).strip().endswith("/[/bold]")


def test_tutorial_prescribed_commands_work(session: GameSession) -> None:
    # Following the tutorial's own instructions must never hit an unknown
    # command (regression: step6b once taught bare '/var', which doesn't move).
    for cmd in ("ls", "take segfault_shield", "equip segfault_shield"):
        out = _text(session.submit(cmd))
        assert "Unknown command" not in out and "digital void" not in out, cmd
    # Equipping the starter weapon spawns the tutorial enemy and starts combat
    # (command_handler.py: equip -> spawn_tutorial_enemy + check_for_enemies).
    # A real player must resolve that fight before moving on; flee to get back
    # to free navigation without depending on random damage rolls.
    from src.game_states import GameState
    if session.state == GameState.IN_COMBAT:
        session.submit("flee")
    for cmd in ("ps", "pwd", "cd ..", "ls"):
        out = _text(session.submit(cmd))
        assert "Unknown command" not in out and "digital void" not in out, cmd
    assert session.player.current_room == "root", "cd .. from /home must reach /"
    session.submit("cd bin")
    assert session.player.current_room == "bin_armory", "the tutorial's cd example must move"


def test_ls_hints_toggle(session: GameSession) -> None:
    import config.dev_config as dev_cfg

    dev_cfg.SHOW_HINTS = True
    on = _text(session.submit("ls"))
    assert "→ take" in on or "→ cat" in on

    dev_cfg.SHOW_HINTS = False
    off = _text(session.submit("ls"))
    assert "→ take" not in off and "→ cat" not in off

    dev_cfg.SHOW_HINTS = True  # restore default


def test_cat_reads_room_file(session: GameSession) -> None:
    # home_grove contains readme_txt_corrupt; cat must render it, not error.
    out = _text(session.submit("cat readme_txt_corrupt"))
    assert "Cannot find" not in out
    assert "Error" not in out  # would appear if the command raised
    # Renders "[bold]<name>[/bold]\n\n<content>"
    assert "[bold]" in out and out.strip()


# --- win condition ----------------------------------------------------------

def test_defeating_overlord_in_core_wins(session: GameSession) -> None:
    h = session.engine.cmd_handler
    # Simulate the climax: player stands in /core and the Overlord is dead.
    session.player.current_room = "core"
    session.world.remove_enemy_from_room("daemon_overlord.sys")
    assert "daemon_overlord.sys" not in session.world.get_enemies_in_room("core")

    assert h.flow.check_game_completion() is True
    assert h.flow.game_won is True
    # win_game branches the ending by class and records the choice.
    assert session.player.story_flags["ending_chosen"] in {"restore", "rewrite", "reconcile"}


def test_win_is_not_triggered_early(session: GameSession) -> None:
    h = session.engine.cmd_handler
    # In core but the Overlord still lives -> no win.
    session.player.current_room = "core"
    assert "daemon_overlord.sys" in session.world.get_enemies_in_room("core")
    assert h.flow.check_game_completion() is False
    assert h.flow.game_won is False


def test_win_does_not_double_fire(session: GameSession) -> None:
    h = session.engine.cmd_handler
    session.player.current_room = "core"
    session.world.remove_enemy_from_room("daemon_overlord.sys")
    assert h.flow.check_game_completion() is True
    # Already won: a second check must be a no-op, not a re-trigger.
    assert h.flow.check_game_completion() is False
