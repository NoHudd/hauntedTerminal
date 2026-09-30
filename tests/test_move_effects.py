"""Players see what each move does: in the fight menu, when HP runs low,
and on the class card before the game starts."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.view_models import AttackView, StatsView
from src.data_loader import load_class_data
from src.move_info import class_move_lines, effect_tags, stat_lines
from src.save import save_manager
from src.ui.combat_log import hotkey_display, render_combat_output
from src.viewmodels.view_builder import ViewBuilder

_PLAYER = StatsView("Tess", 160, 160, 20, "shaman")
_ATTACKS = [
    AttackView("nature_strike", "Nature Strike", 6, 0),
    AttackView("ancient_fury", "Ancient Fury", 17, 2),
    AttackView("healing_strike", "Healing Strike", 8, 3, healing=13),
]
_OPENING = [{"actor": "system", "message": "Combat initiated"}]
_MID_FIGHT = [*_OPENING, {"actor": "enemy", "message": "The Knight hits you"}]


@pytest.fixture(autouse=True)
def _hints_on(monkeypatch: pytest.MonkeyPatch) -> None:
    # The low-HP line is a hint; don't let a developer's saved settings hide it.
    import config.dev_config as dev_cfg

    monkeypatch.setattr(dev_cfg, "SHOW_HINTS", True)


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "shaman")
    try:
        yield session
    finally:
        session.close()


def test_effect_tags_in_plain_words() -> None:
    assert effect_tags(0, 0) == []
    assert effect_tags(13, 0) == ["heals 13 HP"]
    assert effect_tags(3, 0.5) == ["heals 3 HP", "weakens enemy's next hit 50%"]


def test_attack_views_carry_healing_and_weaken(s: GameSession) -> None:
    from src.combat import CombatSystem

    views = {a.id: a for a in ViewBuilder.build_attack_list(s.player, CombatSystem())}
    assert views["healing_strike"].healing == 13
    assert views["nature_strike"].healing == 0

    s.player.player_class = "guardian"  # attack list reads only the class id
    views = {a.id: a for a in ViewBuilder.build_attack_list(s.player, CombatSystem())}
    assert views["shield_bash"].weaken == 0.5


def test_fight_menu_names_the_heal() -> None:
    menu = hotkey_display(_PLAYER, _ATTACKS)
    heal_line = next(line for line in menu.splitlines() if "Healing Strike" in line)
    assert "heals 13 HP" in heal_line
    strike_line = next(line for line in menu.splitlines() if "Nature Strike" in line)
    assert "heals" not in strike_line


def test_low_hp_points_at_the_heal_move() -> None:
    out = render_combat_output(_MID_FIGHT, _PLAYER, _ATTACKS, player_hp=(26, 160))
    assert "Low HP" in out and "[3]" in out and "Healing Strike" in out


def test_low_hp_hint_on_the_opening_screen_too() -> None:
    out = render_combat_output(_OPENING, _PLAYER, _ATTACKS, player_hp=(26, 160))
    assert "Low HP" in out


def test_low_hp_says_when_the_heal_is_ready() -> None:
    cooling = [
        *_ATTACKS[:2],
        AttackView("healing_strike", "Healing Strike", 8, 3, 2, True, healing=13),
    ]
    out = render_combat_output(_MID_FIGHT, _PLAYER, cooling, player_hp=(26, 160))
    assert "Low HP" in out and "2 turns" in out


def test_no_low_hp_hint_when_healthy_or_no_heal_move() -> None:
    healthy = render_combat_output(_MID_FIGHT, _PLAYER, _ATTACKS, player_hp=(150, 160))
    assert "Low HP" not in healthy
    no_heal = render_combat_output(_MID_FIGHT, _PLAYER, _ATTACKS[:2], player_hp=(26, 160))
    assert "Low HP" not in no_heal


def test_low_hp_hint_obeys_the_hints_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    import config.dev_config as dev_cfg

    monkeypatch.setattr(dev_cfg, "SHOW_HINTS", False)
    for log in (_OPENING, _MID_FIGHT):
        out = render_combat_output(log, _PLAYER, _ATTACKS, player_hp=(26, 160))
        assert "Low HP" not in out
    # The menu's own effect tags are facts, not hints: they stay.
    assert "heals 13 HP" in hotkey_display(_PLAYER, _ATTACKS)

    monkeypatch.setattr(dev_cfg, "SHOW_HINTS", True)
    out = render_combat_output(_MID_FIGHT, _PLAYER, _ATTACKS, player_hp=(26, 160))
    assert "Low HP" in out


def test_class_card_lists_every_move_with_its_effect() -> None:
    shaman = load_class_data()["shaman"]
    lines = class_move_lines(shaman)
    assert len(lines) == 3
    heal = next(line for line in lines if "Healing Strike" in line)
    assert "heals 13 HP" in heal
    assert all(len(line) <= 40 for line in lines)  # fits the 40-cell picker card


def test_picker_card_shows_the_moves() -> None:
    from src.ui.textual_ui import TextualGameUI

    cards = {c.title: c for c in TextualGameUI._class_cards()}
    assert "Healing Strike" in cards["Shaman"].subtitle
    assert "heals 13 HP" in cards["Shaman"].subtitle


@pytest.mark.parametrize("class_id", ["guardian", "weaver", "shaman"])
def test_card_stats_come_from_the_real_numbers(class_id: str) -> None:
    cls = load_class_data()[class_id]
    hp, dmg = stat_lines(cls)
    assert f"({cls.base_health} HP)" in hp
    assert f"({cls.base_damage} DMG)" in dmg
    # The words stay hand-written; the numbers never are, so they can't drift.
    assert not any(ch.isdigit() for ch in cls.display.hp_label + cls.display.dmg_label)
