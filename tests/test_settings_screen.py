"""The settings screen: one row per setting, arrows only, Esc saves.

Driven through the screen's actions without an App, like the quit chooser's
tests; the live-app path (title menu → Settings → Esc) is in
test_title_and_finale.py.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

import config.dev_config as dev_cfg
from config.settings_manager import SettingsManager
from src.ui.screens.settings_screen import ROWS, SettingsScreen


@pytest.fixture
def manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SettingsManager]:
    # The setters flip module-level flags; restore them after each test.
    for name in ("DISABLE_ANIMATIONS", "SKIP_INTRO", "SHOW_HINTS"):
        monkeypatch.setattr(dev_cfg, name, getattr(dev_cfg, name))
    m = SettingsManager(settings_path=str(tmp_path / "user_settings.json"))
    m.load()
    yield m


def _screen(manager: SettingsManager, on_close=None) -> SettingsScreen:
    screen = SettingsScreen(manager, on_close=on_close)
    screen.dismiss = lambda *a, **k: None  # no running app in a unit test
    return screen


def test_rows_are_the_four_settings() -> None:
    assert [row.label for row in ROWS] == [
        "Color palette", "Text speed", "Reduce motion", "In-game hints",
    ]


def test_right_applies_the_next_palette(manager: SettingsManager) -> None:
    screen = _screen(manager)
    screen.action_change(1)
    assert manager.settings["theme"] == "neon"


def test_left_on_the_first_palette_wraps_to_the_last(manager: SettingsManager) -> None:
    screen = _screen(manager)
    screen.action_change(-1)
    assert manager.settings["theme"] == "yonce"


def test_down_down_right_turns_reduce_motion_on(manager: SettingsManager) -> None:
    screen = _screen(manager)
    screen.action_move(1)
    screen.action_move(1)
    screen.action_change(1)
    assert manager.settings["reduce_motion"] is True
    assert dev_cfg.DISABLE_ANIMATIONS is True


def test_up_from_the_top_wraps_to_hints(manager: SettingsManager) -> None:
    screen = _screen(manager)
    screen.action_move(-1)
    assert ROWS[screen._index].label == "In-game hints"
    screen.action_change(1)
    assert manager.settings["hints"] is False


def test_escape_saves_and_calls_on_close(manager: SettingsManager, tmp_path: Path) -> None:
    closed: list[bool] = []
    screen = _screen(manager, on_close=lambda: closed.append(True))
    screen.action_change(1)
    screen.action_close()
    saved = json.loads((tmp_path / "user_settings.json").read_text())
    assert saved["theme"] == "neon"
    assert closed == [True]


def test_enter_is_not_bound() -> None:
    """An Enter leaking from the title menu must not change a setting."""
    assert "enter" not in {binding.key for binding in SettingsScreen.BINDINGS}
