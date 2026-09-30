"""Title-menu navigation and the paced victory finale, driven through the real app."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from engine.events import EventType
from src.ui.endings import FinaleReveal, build_recap
from src.ui.screens.settings_screen import SettingsScreen
from src.ui.textual_ui import TextualGameUI


def _run(coro: Any) -> None:
    asyncio.run(coro)


@pytest.fixture(autouse=True)
def _no_intro_on_mount(monkeypatch: pytest.MonkeyPatch) -> None:
    """on_mount would start its own typewriter thread and outlive the test."""
    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)


def test_menu_arrows_move_the_highlight_and_enter_emits_the_choice() -> None:
    commands: list[str] = []
    app = TextualGameUI()
    app.bus.subscribe(EventType.COMMAND_ENTERED, lambda e: commands.append(e.data["command"]))

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            menu = app._title_menu
            menu.show(skip_typewriter=True)
            await pilot.pause()
            assert menu.state == "menu_ready"
            assert menu.handle_key("down") and menu.index == 1
            assert menu.handle_key("up") and menu.handle_key("up") and menu.index == 3
            assert "▶  EXIT  ◀" in str(app.output_content)
            assert not menu.handle_key("x")  # unrelated keys fall through
            assert menu.handle_key("enter")
            assert commands == ["3"]
            assert menu.state == "idle"
            assert not menu.handle_key("down")  # menu is closed

    _run(scenario())


def test_any_key_while_typing_skips_the_typewriter() -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            menu = app._title_menu
            menu.show(skip_typewriter=False)
            assert menu.state == "typing"
            assert menu.handle_key("q")
            for _ in range(50):
                if menu.state == "menu_ready" and "NEW GAME" in str(app.output_content):
                    break
                await pilot.pause(0.05)
            assert menu.state == "menu_ready"
            assert "NEW GAME" in str(app.output_content)
            # The typewriter runs on a thread; exiting before it finishes makes its
            # last call_from_thread land on a closed loop.
            for _ in range(100):
                if not any("run_typewriter" in t.name for t in threading.enumerate()):
                    break
                await pilot.pause(0.05)

    _run(scenario())


class _FakeTimer:
    def __init__(self, delay: float, callback: Any) -> None:
        self.delay, self.callback, self.stopped = delay, callback, False

    def stop(self) -> None:
        self.stopped = True


class _FakeOut:
    def __init__(self) -> None:
        self.shown: list[str] = []
        self.timers: list[_FakeTimer] = []

    def update_output(self, content: str) -> None:
        self.shown = [content]

    def append_output(self, content: Any) -> None:
        self.shown.append(content)

    def set_timer(self, delay: float, callback: Any) -> _FakeTimer:
        timer = _FakeTimer(delay, callback)
        self.timers.append(timer)
        return timer


_DATA = {"sections": ["one", "two", "three"], "stats": {"player_name": "Ada", "level": 3}}


def test_skipping_the_finale_dumps_the_rest_and_stops_the_timers() -> None:
    out = _FakeOut()
    finale = FinaleReveal(out)
    finale.start(_DATA, reduce_motion=False)
    out.timers[0].callback()
    finale.skip()
    assert out.shown == ["one", "two", "three", build_recap(_DATA["stats"])]
    assert all(t.stopped for t in out.timers)
    assert not finale.revealing
    finale.skip()  # a second key is a no-op
    assert len(out.shown) == 4


def test_settings_opens_from_the_menu_and_esc_returns_to_it(tmp_path: Path) -> None:
    commands: list[str] = []
    app = TextualGameUI()
    app._settings_manager._path = str(tmp_path / "user_settings.json")  # never the real file
    app.bus.subscribe(EventType.COMMAND_ENTERED, lambda e: commands.append(e.data["command"]))

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            menu = app._title_menu
            menu.show(skip_typewriter=True)
            await pilot.pause()
            menu.handle_key("down")
            menu.handle_key("down")
            assert "▶  SETTINGS  ◀" in str(app.output_content)

            assert menu.handle_key("enter")
            await pilot.pause()
            assert isinstance(app.screen, SettingsScreen)
            assert commands == []  # SETTINGS is UI-only

            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, SettingsScreen)
            assert menu.state == "menu_ready" and menu.index == 2
            assert "▶  SETTINGS  ◀" in str(app.output_content)
            assert commands == []  # the Esc that closed Settings did not quit

    _run(scenario())
