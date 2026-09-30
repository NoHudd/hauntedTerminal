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


def test_old_pool_saves_are_set_aside_not_offered(tmp_path) -> None:
    (tmp_path / "save_old.json").write_text(json.dumps(_old_save()))
    mgr = SaveManager(save_dir=str(tmp_path))
    assert mgr.list_runs() == []
    assert mgr.legacy_count() == 1


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
    s.player.add_to_inventory("lib_key", s.world.get_item("lib_key"))
    out = "\n".join(str(x) for x in s.submit("keys"))
    assert "var_dungeon" not in out and "class-restricted" not in out
    assert "/usr" in out and "11 flags" in out


def test_keys_does_not_spoil_undiscovered_secret_rooms(s: GameSession) -> None:
    s.player.add_to_inventory("opt_key", s.world.get_item("opt_key"))
    out = "\n".join(str(x) for x in s.submit("keys"))
    assert "/opt" not in out and "/root" not in out
    s.world.discover_room("opt_mage_tower")
    assert "/opt" in "\n".join(str(x) for x in s.submit("keys"))


def test_tree_is_described_truthfully(s: GameSession) -> None:
    """tree marks flags you hold; it cannot show where uncaptured ones hide."""
    s.player.tutorial_state["completed"] = True
    texts = [
        "\n".join(str(x) for x in s.submit("cd /boot")),
        "\n".join(str(x) for x in s.submit("keys")),
        open("data/npcs/echo.usr.yml").read(),
    ]
    for text in texts:
        assert "still hide one" not in text and "where they hide" not in text


def test_rank_ladder_matches_real_wins() -> None:
    assert rank_for(12, 13, 0, 5) == "Sysadmin"
    assert rank_for(13, 13, 4, 5) == "Sysadmin Supreme"
    assert rank_for(13, 13, 5, 5) == "root"
    assert rank_for(0, 0, 0, 0) == "—"


def test_all_secrets_earn_a_title_on_any_win() -> None:
    recap = build_recap({"flags": 12, "flags_total": 13, "secrets": 5, "secrets_total": 5})
    assert "Keeper of Secrets" in recap
