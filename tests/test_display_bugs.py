"""Two display gaps: the inventory panel showed no heal amount for healing
items, and every attack in the fight menu got the same plain bullet."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.view_models import AttackView, InventoryItemView, StatsView
from src.ui.combat_log import hotkey_display
from src.ui.panels.inventory_panel import InventoryPanel
from src.viewmodels.view_builder import ViewBuilder


@pytest.fixture
def s() -> Iterator[GameSession]:
    session = GameSession()
    session.new_game("t", "shaman")
    try:
        yield session
    finally:
        session.close()


def _view(s: GameSession, item_id: str) -> InventoryItemView:
    s.player.add_to_inventory(item_id, s.world.get_item(item_id))
    items = ViewBuilder.build_inventory_view(s.player).items
    return next(i for i in items if i.id == item_id)


def test_health_packet_view_carries_its_heal(s: GameSession) -> None:
    view = _view(s, "health_packet")
    assert view.healing == 30 and view.healTurns == 0


def test_heal_over_time_view_carries_total_and_turns(s: GameSession) -> None:
    view = _view(s, "stable_cache")
    assert view.healing == 39 and view.healTurns == 3  # 13 a turn, 3 turns


def test_panel_shows_heal_amounts() -> None:
    panel = InventoryPanel()
    packet = InventoryItemView("health_packet", "Health Packet", "consumable", healing=30)
    cache = InventoryItemView(
        "stable_cache", "Stable Cache", "consumable", healing=39, healTurns=3
    )
    assert "+30 HP" in panel._format_enhanced_inventory_item("health_packet", packet)
    assert "+39 HP over 3 turns" in panel._format_enhanced_inventory_item(
        "stable_cache", cache
    )


def test_attack_views_carry_their_kind(s: GameSession) -> None:
    from src.combat import CombatSystem

    views = {a.id: a for a in ViewBuilder.build_attack_list(s.player, CombatSystem())}
    assert views["nature_strike"].kind == "nature"


def test_fight_menu_shows_a_kind_icon_per_attack() -> None:
    player = StatsView("Tess", 100, 100, 10, "weaver")
    menu = hotkey_display(player, [
        AttackView("strike", "Strike", 5, 0, kind="physical"),
        AttackView("fireball", "Fireball", 18, 2, kind="magical"),
        AttackView("nature_strike", "Nature Strike", 6, 0, kind="nature"),
    ])
    lines = menu.splitlines()[1:]
    assert "⚔" in lines[0] and "✨" in lines[1] and "🌿" in lines[2]
