"""Everything about a run survives save and load.

The player is serialized by hand, so a new Player field is lost on load unless
someone also adds it to to_dict/from_dict. That is how armor and status effects
went missing. This test walks every attribute instead of listing them, so the
next forgotten field fails here.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from engine.api import GameSession
from src import difficulty
from src.player import Player
from src.save import SaveManager

# Recomputed from class data by Player.__init__, so they need no saving.
DERIVED_FROM_CLASS = {"class_description", "starter_abilities"}


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Saver", "guardian")
    try:
        yield s
    finally:
        s.close()


def _load_up(s: GameSession) -> Player:
    """A player with every kind of state a run can accumulate."""
    p = s.player
    armor = next(
        iid for iid, it in s.world.items.items()
        if it.type == "armor" and p.can_use_item(it)
    )
    p.add_to_inventory(armor, s.world.get_item(armor))
    assert p.equip_armor(armor)
    p.add_status_effect("stable_cache_hot", {"type": "heal_over_time", "heal_per_turn": 2,
                                             "name": "Stable Cache"}, 3)
    p.move_to("root")
    p.set_story_flag("identity_retrieved")
    p.met_npcs.add("echo")
    p.run_stats["kills"] = 3
    p.harvest_cycles(40)
    p.health = p.max_health - 7
    p.tutorial_state["completed"] = True
    return p


def test_every_player_field_survives_a_round_trip(session: GameSession) -> None:
    player = _load_up(session)
    restored = Player.from_dict(json.loads(json.dumps(player.to_dict())))

    lost = {
        name: (value, getattr(restored, name, "<missing>"))
        for name, value in vars(player).items()
        if name not in DERIVED_FROM_CLASS and getattr(restored, name, "<missing>") != value
    }
    assert lost == {}


def test_difficulty_is_saved_with_the_run(session: GameSession, tmp_path: Path) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    difficulty.set_mode("hard")
    try:
        mgr.save_game(session.player, session.world.get_state(), "hard.json")
        difficulty.set_mode("medium")

        loaded = mgr.load_game("hard.json")
        assert loaded["difficulty"] == "hard"
    finally:
        difficulty.set_mode(difficulty.DEFAULT_MODE)


def test_loading_a_hard_run_plays_it_on_hard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.save as save_mod

    mgr = SaveManager(save_dir=str(tmp_path))
    monkeypatch.setattr(save_mod, "save_manager", mgr)
    monkeypatch.setattr("src.game_engine.save_manager", mgr)

    first = GameSession()
    try:
        first.new_game("Hardy", "guardian")
        difficulty.set_mode("hard")
        mgr.save_game(first.player, first.world.get_state())
    finally:
        first.close()

    difficulty.set_mode("medium")  # a fresh process, or another run in this one
    second = GameSession()
    try:
        second.engine._load_game()
        assert second.player.name == "Hardy"
        assert difficulty.current_mode() == "hard"
    finally:
        second.close()
        difficulty.set_mode(difficulty.DEFAULT_MODE)


def test_a_v3_save_without_difficulty_still_loads(session: GameSession, tmp_path: Path) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    mgr.save_game(session.player, session.world.get_state(), "v3.json")
    raw = json.loads((tmp_path / "v3.json").read_text())
    raw["version"] = 3
    raw.pop("difficulty", None)
    for key in ("equipped_armor", "status_effects"):
        raw["player"].pop(key, None)
    (tmp_path / "v3.json").write_text(json.dumps(raw))

    loaded = mgr.load_game("v3.json")
    restored = Player.from_dict(loaded["player"])
    assert restored.equipped_armor is None
    assert restored.status_effects == {}


def test_starting_the_ui_does_not_change_the_difficulty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Difficulty belongs to the run (picked at new game, restored from a save).
    Mounting the UI used to reset it from user settings, so a loaded Hard run
    reverted to the settings value."""
    import asyncio

    from src.ui.textual_ui import TextualGameUI

    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)
    difficulty.set_mode("hard")
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert difficulty.current_mode() == "hard"

    try:
        asyncio.run(scenario())
    finally:
        difficulty.set_mode(difficulty.DEFAULT_MODE)
