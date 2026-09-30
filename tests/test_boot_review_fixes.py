"""Phase 3b review fixes a player would feel: old saves explain themselves,
NPCs describe the real /boot gate, `keys` tells the truth, and the recap's
rank ladder matches what a win can actually be."""
import json
from collections.abc import Iterator

import pytest
import yaml

from engine.api import GameSession
from src.save import SaveManager, save_manager
from src.ui.endings import build_recap, rank_for


def _old_save() -> dict:
    return {
        "version": 4, "savedAt": 1.0, "saveDate": "2026-01-01 00:00:00",
        "player": {"name": "Old", "player_class": "guardian", "current_room": "root"},
        "world": {"room_states": {}},
    }


def test_load_game_says_old_saves_are_from_before_flags(tmp_path, monkeypatch) -> None:
    (tmp_path / "old.json").write_text(json.dumps(_old_save()))
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    s = GameSession()
    try:
        s.ui.clear_console()
        s.engine._load_game()
        out = "\n".join(str(x) for x in s.ui.drain())
    finally:
        s.close()
    assert "before room flags" in out
    assert "No save files found" not in out


def test_skipped_count_is_exposed(tmp_path) -> None:
    (tmp_path / "old.json").write_text(json.dumps(_old_save()))
    mgr = SaveManager(save_dir=str(tmp_path))
    assert mgr.get_save_files() == []
    assert mgr.last_skipped == 1


def test_npcs_describe_the_flag_gate() -> None:
    knight = yaml.safe_load(open("data/npcs/firewall_knight.iptables.yml"))
    echo = yaml.safe_load(open("data/npcs/echo.usr.yml"))
    text = json.dumps([knight, echo]).lower()
    assert "chmod key grants passage" not in text
    assert "access granted" not in text
    assert "flags" in json.dumps(knight).lower()


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "guardian")
    try:
        yield session
    finally:
        session.close()


def test_keys_command_tells_the_truth(s: GameSession) -> None:
    out = "\n".join(str(x) for x in s.submit("keys"))
    assert "var_dungeon" not in out and "class-restricted" not in out
    assert "/usr" in out and "11 flags" in out


def test_rank_ladder_matches_real_wins() -> None:
    assert rank_for(12, 13, 0, 5) == "Sysadmin"
    assert rank_for(13, 13, 4, 5) == "Sysadmin Supreme"
    assert rank_for(13, 13, 5, 5) == "root"
    assert rank_for(0, 0, 0, 0) == "—"


def test_all_secrets_earn_a_title_on_any_win() -> None:
    recap = build_recap({"flags": 12, "flags_total": 13, "secrets": 5, "secrets_total": 5})
    assert "Keeper of Secrets" in recap
