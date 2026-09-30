"""The Character panel under Stats: the player's model outside battle, plus the
weapon and armor they have on, with the numbers that matter."""
from __future__ import annotations

import asyncio
import io

import pytest
from rich.console import Console
from textual.app import App, ComposeResult

from engine.view_models import InventoryItemView, InventoryView, StatsView
from src.ui.panels.character_panel import CharacterPanel, gear_lines

_PLAYER = StatsView("Eli", 26, 160, 42, "shaman", defense_pct=18)
_GEAR = InventoryView(items=[
    InventoryItemView("pike", "Privilege Escalation Pike", "weapon", "epic",
                      is_equipped=True, damage=24),
    InventoryItemView("cloak", "Null-Void Cloak", "armor", "epic", is_equipped=True),
    InventoryItemView("fang", "Recursion Fang", "weapon", "rare", damage=17),
])


def test_gear_lines_name_the_equipped_weapon_and_armor() -> None:
    text = "\n".join(gear_lines(_PLAYER, _GEAR))
    assert "Privilege Escalation Pike" in text and "+24 DMG" in text
    assert "Null-Void Cloak" in text and "-18% dmg taken" in text
    assert "Recursion Fang" not in text  # carried, not equipped


def test_empty_slots_teach_equip() -> None:
    bare = StatsView("Eli", 100, 100, 10, "shaman")
    text = "\n".join(gear_lines(bare, InventoryView(items=[])))
    assert text.count("equip <name>") == 2


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield CharacterPanel(id="character-panel")


def test_panel_renders_sprite_and_gear() -> None:
    async def scenario() -> None:
        app = _Host()
        async with app.run_test(size=(80, 30)) as pilot:
            panel = app.query_one(CharacterPanel)
            panel.update_character(_PLAYER, _GEAR, reduce_motion=True)
            await pilot.pause()
            console = Console(width=60, record=True, file=io.StringIO())
            console.print(panel.content)
            shown = console.export_text()
            assert "Privilege" in shown and "Null-Void Cloak" in shown
            assert "▀" in shown or "▄" in shown  # the half-block sprite drew

    asyncio.run(scenario())


def test_panel_is_in_the_sidebar_below_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.ui.textual_ui import TextualGameUI

    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)):
            ids = [w.id for w in app.query_one("#sidebar").children]
            assert ids == ["inventory-panel", "stats-panel", "character-panel"]

    asyncio.run(scenario())


class _NarrowHost(App[None]):
    CSS = "CharacterPanel { width: 34; }"

    def compose(self) -> ComposeResult:
        yield CharacterPanel(id="character-panel")


def test_narrow_panel_puts_gear_under_the_sprite_uncut() -> None:
    """Too narrow for side by side: gear goes below the sprite, names whole."""
    async def scenario() -> None:
        app = _NarrowHost()
        async with app.run_test(size=(80, 40)) as pilot:
            panel = app.query_one(CharacterPanel)
            panel.update_character(_PLAYER, _GEAR, reduce_motion=True)
            await pilot.pause()
            console = Console(width=34, record=True, file=io.StringIO())
            console.print(panel.content)
            shown = console.export_text()
            assert "Privilege Escalation Pike" in shown and "…" not in shown

    asyncio.run(scenario())
