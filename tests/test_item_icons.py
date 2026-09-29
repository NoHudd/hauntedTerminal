"""Every view names an item's type with the same icon."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.item_icons import ITEM_TYPE_ICONS, UNKNOWN_ICON, item_icon
from src.ui.panels.inventory_panel import InventoryPanel


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Icons", "guardian")
    try:
        yield s
    finally:
        s.close()


def _text(lines: list[str]) -> str:
    return "\n".join(str(x) for x in lines)


def test_every_item_type_in_the_game_has_an_icon(session: GameSession) -> None:
    types = {item.type for item in session.world.items.values()}
    assert types <= set(ITEM_TYPE_ICONS), types - set(ITEM_TYPE_ICONS)
    assert item_icon("nonsense") == UNKNOWN_ICON


def test_ls_take_and_examine_show_the_icon(session: GameSession) -> None:
    session.world.item_locations["health_packet"] = session.player.current_room
    assert "🗡 segfault_shield" in _text(session.submit("ls"))
    assert "💊 health_packet" in _text(session.submit("ls"))
    assert "Added 💊" in _text(session.submit("take health_packet"))
    assert "🗡" in _text(session.submit("examine segfault_shield"))


def test_the_inventory_panel_uses_the_same_icons() -> None:
    panel = InventoryPanel()
    for item_type, icon in ITEM_TYPE_ICONS.items():
        assert panel._get_item_type_icon(item_type) == icon
