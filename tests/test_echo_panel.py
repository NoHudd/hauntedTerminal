"""Echo panel: tutorial hints are pinned above the input, not buried in the output."""
from __future__ import annotations

import asyncio

import pytest

from engine.events import EventType
from src.ui.textual_ui import TextualGameUI


@pytest.fixture(autouse=True)
def _no_intro_on_mount(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)


def _hint(
    app: TextualGameUI, hint_id: str, text: str, step: int | None, final: bool = False
) -> None:
    app.bus.emit_event(
        EventType.TUTORIAL_HINT,
        {"hint_id": hint_id, "text": text, "step": step, "total": 6, "final": final},
        "test",
    )


def test_hint_is_pinned_in_the_echo_panel() -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            panel = app._echo_panel
            assert panel.display is False
            before = str(app.output_content)

            _hint(app, "step2", "[bold green]ECHO>[/bold green] Type: take it", 2)
            await pilot.pause()

            assert panel.display is True
            assert panel.border_title == "🗨 ECHO · step 2 of 6"
            assert str(panel.content) == "Type: take it"
            assert str(app.output_content) == before

    asyncio.run(scenario())


def test_the_closing_hint_goes_to_the_output_and_hides_the_panel() -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            app.remove_class("intro-mode")
            _hint(app, "step6", "go somewhere", 6)
            await pilot.pause()
            _hint(app, "completed", "Tutorial complete, Tess.", None, final=True)
            await pilot.pause()

            assert app._echo_panel.display is False
            assert "Tutorial complete, Tess." in str(app.output_content)

    asyncio.run(scenario())


def test_a_new_game_clears_a_stale_hint() -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            _hint(app, "step4", "press 1", 4)
            await pilot.pause()
            app.bus.emit_event(EventType.GAME_STARTED, {}, "test")
            await pilot.pause()
            assert app._echo_panel.display is False

    asyncio.run(scenario())


def test_the_panel_flashes_when_the_tutorial_starts() -> None:
    """The first hint draws the eye to the panel: it pulses, then settles."""
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            panel = app._echo_panel
            _hint(app, "step1", "Type: ls", 1)
            await pilot.pause()
            assert panel.has_class("echo-flash")

            await pilot.pause(panel.FLASH_SECONDS * (2 * panel.FLASH_PULSES + 2))
            assert not panel.has_class("echo-flash"), "the flash must settle"

            _hint(app, "step2", "Type: take it", 2)
            await pilot.pause()
            assert not panel.has_class("echo-flash"), "later steps don't flash"

    asyncio.run(scenario())


def test_reduce_motion_highlights_once_instead_of_flashing() -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            app._settings_manager.settings["reduce_motion"] = True
            panel = app._echo_panel
            toggles: list[bool] = []
            original = panel.set_class

            def record(add: bool, *names: str) -> object:
                toggles.append(add)
                return original(add, *names)

            panel.set_class = record  # type: ignore[method-assign]
            _hint(app, "step1", "Type: ls", 1)
            await pilot.pause(panel.FLASH_SECONDS * (2 * panel.FLASH_PULSES + 2))
            assert toggles == [True, False], toggles

    asyncio.run(scenario())


def test_saying_yes_to_the_tutorial_flashes_the_panel() -> None:
    from src.game_engine import ImprovedGameEngine

    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            engine = ImprovedGameEngine(ui=app)
            assert engine.create_player("Tess", "guardian")
            engine._handle_skip_response("yes")  # the tutorial offer's answer
            await pilot.pause()

            panel = app._echo_panel
            assert panel.display is True
            assert "step 1" in str(panel.border_title)
            assert panel.has_class("echo-flash")
            engine._cleanup()

    asyncio.run(scenario())
