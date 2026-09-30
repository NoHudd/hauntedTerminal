"""The number shown next to an attack is the key that fires it.

The panel numbered every attack but the keys skipped ones on cooldown, so with
Frost Nova cooling down the key shown for Arcane Bolt did nothing and the one
shown for Fireball fired Arcane Bolt. The attack order also came from a set,
so the numbers reshuffled between launches.
"""
from __future__ import annotations

import asyncio

from engine.api import GameSession
from engine.events import EventType
from src.combat import combat_system
from src.game_states import GameState
from src.ui.textual_ui import TextualGameUI


def _attack(attack_id: str, name: str, on_cooldown: bool = False) -> dict:
    return {
        "id": attack_id, "name": name, "bonus_damage": 5, "cooldown": 2,
        "cooldown_remaining": 1 if on_cooldown else 0, "on_cooldown": on_cooldown,
        "accuracy": 90,
    }


# As the panel lists them: [1] Frost Nova (cooling down), [2] Fireball, [3] Arcane Bolt.
_ATTACKS = [
    _attack("frost_nova", "Frost Nova", on_cooldown=True),
    _attack("fireball", "Fireball"),
    _attack("arcane_bolt", "Arcane Bolt"),
]


def _fired_after_pressing(key: str) -> list[str]:
    app = TextualGameUI()
    fired: list[str] = []
    app.bus.subscribe(
        EventType.COMBAT_ACTION_SELECTED, lambda e: fired.append(e.data.get("choice"))
    )

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            app.state_manager.set_state(GameState.PLAYING, emit_event=False)
            app.state_manager.set_state(GameState.IN_COMBAT, emit_event=False)
            app.bus.emit_event(
                EventType.COMBAT_STARTED,
                {
                    "enemy_name": "Mount Daemon", "enemy_health": 50,
                    "enemy_max_health": 50, "player_health": 60,
                    "player_max_health": 90, "available_attacks": _ATTACKS,
                },
                "Test",
            )
            # The bus hands COMBAT_STARTED to the UI thread; wait for the keys
            # to be bound rather than racing it.
            for _ in range(50):
                if key in app._bound_combat_keys:
                    break
                await pilot.pause(0.02)
            await pilot.press(key)
            await pilot.pause()

    asyncio.run(scenario())
    return fired


def test_the_key_shown_next_to_an_attack_fires_it() -> None:
    assert _fired_after_pressing("3") == ["arcane_bolt"]
    assert _fired_after_pressing("2") == ["fireball"]


def test_the_key_of_an_attack_on_cooldown_fires_nothing() -> None:
    assert _fired_after_pressing("1") == []


def test_attacks_keep_the_class_order() -> None:
    s = GameSession()
    try:
        s.new_game("t", "weaver")
        class_order = combat_system.get_attacks_for_class("weaver")
        offered = list(combat_system.get_available_attacks(s.player))
    finally:
        s.close()
    assert offered == list(class_order)
