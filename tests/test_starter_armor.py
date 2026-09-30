"""Each class starts with a junk armor in /home, and the tutorial teaches it:
the scripted fight opens once the starter weapon AND armor are equipped."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.data_loader import load_class_data

STARTERS = {"guardian": ("segfault_shield", "cracked_firewall"),
            "weaver": ("null_pointer", "threadbare_buffer"),
            "shaman": ("daemon_whisper", "frayed_mantra_cloth")}


@pytest.fixture
def guardian() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tess", "guardian")
    try:
        yield s
    finally:
        s.close()


def _hints(s: GameSession) -> list[str]:
    return [h["hint_id"] for h in s.ui.hints]


@pytest.mark.parametrize("klass", sorted(STARTERS))
def test_each_class_finds_its_own_junk_armor_at_home(klass: str) -> None:
    weapon, armor = STARTERS[klass]
    assert load_class_data()[klass].starter_armor == armor
    s = GameSession()
    try:
        s.new_game("T", klass)
        here = s.world.get_items_in_room("home_grove")
        assert weapon in here and armor in here
        item = s.world.items[armor]
        assert item.type == "armor" and item.defense == 2
        assert item.allowed_classes == [klass]
    finally:
        s.close()


def test_the_weapon_alone_asks_for_armor_and_starts_no_fight(guardian: GameSession) -> None:
    guardian.submit("take segfault_shield")
    guardian.submit("equip segfault_shield")
    assert guardian.engine.cmd_handler.current_combat_session is None
    assert _hints(guardian)[-1] == "step_armor"


def test_armor_then_weapon_also_opens_the_fight(guardian: GameSession) -> None:
    guardian.submit("take cracked_firewall")
    guardian.submit("equip cracked_firewall")
    assert guardian.engine.cmd_handler.current_combat_session is None
    assert _hints(guardian)[-1] == "step2"  # the weapon is still on the floor
    guardian.submit("take segfault_shield")
    guardian.submit("equip segfault_shield")
    assert guardian.engine.cmd_handler.current_combat_session is not None
    assert _hints(guardian)[-1] == "step4"


def test_equipping_the_armor_shows_its_defense(guardian: GameSession) -> None:
    guardian.submit("take cracked_firewall")
    out = "\n".join(guardian.submit("equip cracked_firewall"))
    assert "reduced by 3%" in out


def test_a_player_who_skipped_is_never_ambushed(guardian: GameSession) -> None:
    guardian.player.tutorial_state["completed"] = True
    for command in ("take segfault_shield", "equip segfault_shield",
                    "take cracked_firewall", "equip cracked_firewall"):
        guardian.submit(command)
    assert guardian.engine.cmd_handler.current_combat_session is None


def test_an_old_save_past_the_fight_is_not_sent_back_to_armor(guardian: GameSession) -> None:
    ts = guardian.player.tutorial_state
    ts.update({"first_ls": True, "took_weapon": True, "equipped_weapon": True,
               "combat_action_taken": True})
    ts.pop("equipped_armor", None)
    assert guardian.engine.cmd_handler.tutorial.current_step() != "step_armor"
