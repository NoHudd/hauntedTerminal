"""The save picker screen: list + preview, arrows only, d asks before deleting.
It decides nothing; it sends the same commands a typed player would."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

import src.save as save_mod
from engine.events import EventType
from src.game_engine import ImprovedGameEngine
from src.game_states import GameState
from src.save import SaveManager
from src.ui.screens.save_picker import SavePickerScreen, saved_ago
from src.ui.textual_ui import TextualGameUI

RUNS = [
    {"runId": "aaaa1111", "playerName": "Ada", "playerClass": "guardian",
     "difficulty": "easy", "level": 4, "roomPath": "/var/log", "health": 58,
     "maxHealth": 80, "savedAt": 0.0, "cleared": False},
    {"runId": "bbbb2222", "playerName": "Mo", "playerClass": "shaman",
     "difficulty": "medium", "level": 9, "roomPath": "/boot", "health": 90,
     "maxHealth": 90, "savedAt": 0.0, "cleared": True},
]


def _screen(mode: str = "continue", runs=RUNS, legacy: int = 0):
    sent: list[str] = []
    return SavePickerScreen(mode, list(runs), legacy, sent.append), sent


def test_rows_show_name_class_difficulty_room_level_and_cleared() -> None:
    screen, _ = _screen()
    text = screen.list_text()
    for part in ("Ada", "Guardian", "easy", "/var/log", "L4"):
        assert part in text
    assert "✓" in text.splitlines()[1] and "✓" not in text.splitlines()[0]


def test_arrows_move_and_wrap() -> None:
    screen, _ = _screen()
    screen.action_move(1)
    assert screen._index == 1
    screen.action_move(1)
    assert screen._index == 0


def test_enter_picks_the_highlighted_run() -> None:
    screen, sent = _screen()
    screen.action_move(1)
    screen.action_confirm()
    assert sent == ["pick bbbb2222"]


def test_the_enter_that_opened_the_picker_does_not_answer_it() -> None:
    screen, sent = _screen()
    screen._mounted_at = time.monotonic()
    screen.action_confirm()
    assert sent == []


def test_delete_asks_first() -> None:
    screen, sent = _screen()
    screen.action_delete()
    assert "Delete Ada's run?" in screen.hint_text()
    screen.action_answer_delete(False)
    assert sent == [] and not screen._confirming_delete
    screen.action_delete()
    screen.action_answer_delete(True)
    assert sent == ["delete aaaa1111"]


def test_escape_leaves_a_delete_prompt_before_the_screen() -> None:
    screen, sent = _screen()
    screen.action_delete()
    screen.action_back()
    assert sent == []
    screen.action_back()
    assert sent == ["back"]


def test_the_replace_picker_has_no_delete() -> None:
    screen, _ = _screen("replace")
    screen.action_delete()
    assert not screen._confirming_delete
    assert "d delete" not in screen.hint_text() and "replace" in screen.hint_text()


def test_empty_state() -> None:
    screen, sent = _screen(runs=[], legacy=3)
    text = screen.list_text()
    assert "No saves available" in text and "3 old saves" in text
    assert screen.hint_text() == "esc back"
    screen.action_confirm()
    assert sent == ["back"]


def test_a_second_answer_is_ignored() -> None:
    screen, sent = _screen()
    screen.action_confirm()
    screen.action_back()
    assert sent == ["pick aaaa1111"]


def test_saved_ago() -> None:
    assert saved_ago(1000, now=1030) == "just now"
    assert saved_ago(1000, now=1000 + 5 * 60) == "5m ago"
    assert saved_ago(1000, now=1000 + 2 * 3600) == "2h ago"
    assert saved_ago(1000, now=1000 + 3 * 86400) == "3d ago"


# --- the real app -------------------------------------------------------------

@pytest.fixture
def mgr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SaveManager:
    m = SaveManager(save_dir=str(tmp_path))
    monkeypatch.setattr(save_mod, "save_manager", m)
    monkeypatch.setattr("src.game_engine.save_manager", m)
    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)
    return m


def test_load_game_opens_the_picker_and_enter_continues_the_run(
    mgr: SaveManager, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr("config.dev_config.DISABLE_ANIMATIONS", True)
            engine = ImprovedGameEngine(ui=app)
            assert engine.create_player("Ada", "guardian")
            engine.start_game()
            mgr.save_game(engine.player, engine.world.get_state())
            run_id = mgr.active_run_id
            engine._return_to_menu()  # back at the title (no intro replay), run ended
            await pilot.pause()

            engine.bus.emit_event(EventType.COMMAND_ENTERED, {"command": "2"}, "test")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, SavePickerScreen)

            await asyncio.sleep(0.3)  # past the confirm grace
            await pilot.press("enter")
            await pilot.pause()
            assert engine.state_manager.current_state == GameState.PLAYING
            assert engine.player.name == "Ada" and mgr.active_run_id == run_id
            assert not isinstance(app.screen, SavePickerScreen)
            engine._cleanup()

    asyncio.run(scenario())


def test_empty_picker_escape_returns_to_the_title_without_quitting(
    mgr: SaveManager, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            engine = ImprovedGameEngine(ui=app)
            quits: list[object] = []
            engine.bus.subscribe(EventType.GAME_QUIT, quits.append)
            await pilot.pause()

            engine.bus.emit_event(EventType.COMMAND_ENTERED, {"command": "2"}, "test")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, SavePickerScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert engine.state_manager.current_state == GameState.MENU
            assert not isinstance(app.screen, SavePickerScreen)
            assert app._title_menu.state == "menu_ready"
            assert quits == []
            engine._cleanup()

    asyncio.run(scenario())
