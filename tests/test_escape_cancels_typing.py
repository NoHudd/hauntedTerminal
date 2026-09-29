"""Esc while typing cancels the line, like a shell. Only an Esc on an empty
prompt means "quit"."""
from __future__ import annotations

import asyncio

from textual.widgets import Input

from src.events import EventType
from src.ui.textual_ui import TextualGameUI


def _run(coro) -> None:
    asyncio.run(coro)


def _commands_emitted(recorder: list) :
    def on_command(event) -> None:
        recorder.append(event.data.get("command"))
    return on_command


def test_escape_with_text_clears_input_and_does_not_quit() -> None:
    commands: list[str] = []
    app = TextualGameUI()
    app.bus.subscribe(EventType.COMMAND_ENTERED, _commands_emitted(commands))

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            field = app.query_one("#input-field", Input)
            field.focus()
            await pilot.press("t", "a", "k", "e", " ", "s")
            assert field.value == "take s"
            await pilot.press("escape")
            await pilot.pause()
            assert field.value == ""
            assert "quit" not in commands

    _run(scenario())


def test_escape_on_empty_input_still_asks_to_quit() -> None:
    commands: list[str] = []
    app = TextualGameUI()
    app.bus.subscribe(EventType.COMMAND_ENTERED, _commands_emitted(commands))

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#input-field", Input).focus()
            await pilot.press("escape")
            await pilot.pause()
            assert commands == ["quit"]

    _run(scenario())
