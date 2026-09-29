"""Tutorial playtest feedback: hint ordering, the flee dead end, the quit crash."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from engine.events import EventType
from engine.view_models import AttackView, StatsView
from src.game_world import TUTORIAL_ENEMY
from src.ui.combat_log import render_combat_output
from src.ui.screens.quit_confirm import QuitConfirmScreen
from src.ui.textual_ui import TextualGameUI


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tess", "guardian")
    try:
        yield s
    finally:
        s.close()


def _text(lines: list[str]) -> str:
    return "\n".join(str(line) for line in lines)


def _weapon_here(s: GameSession) -> str:
    return next(
        i for i in s.world.get_items_in_room(s.player.current_room)
        if s.world.items[i].type == "weapon"
    )


def _into_tutorial_fight(s: GameSession) -> str:
    s.submit("ls")
    weapon = _weapon_here(s)
    s.submit(f"take {weapon}")
    return _text(s.submit(f"equip {weapon}"))


def test_take_lists_the_room_before_echo_speaks(session: GameSession) -> None:
    session.submit("ls")
    out = _text(session.submit(f"take {_weapon_here(session)}"))
    hint = session.ui.hints[-1]
    assert hint["hint_id"] == "step3"
    assert out.index("Files:") < out.index(hint["text"])


def test_combat_hint_arrives_after_the_fight_opens(session: GameSession) -> None:
    handler = session.engine.cmd_handler
    in_combat_when_shown: list[bool] = []
    session.bus.subscribe(
        EventType.TUTORIAL_HINT,
        lambda e: in_combat_when_shown.append(handler.current_combat_session is not None),
    )
    _into_tutorial_fight(session)
    assert session.ui.hints[-1]["hint_id"] == "step4"
    assert in_combat_when_shown[-1]


def test_fleeing_the_tutorial_fight_keeps_it_winnable(session: GameSession) -> None:
    _into_tutorial_fight(session)
    room = session.player.current_room
    session.bus.emit_event(EventType.COMBAT_ACTION_SELECTED, {"choice": "flee"}, "test")

    assert session.engine.cmd_handler.current_combat_session is None
    assert session.player.current_room == room
    assert TUTORIAL_ENEMY in session.world.get_enemies_in_room(room)
    assert session.ui.hints[-1]["hint_id"] == "step4_fled"

    # A stray command re-explains how to continue, not "press 1".
    session.submit("1")
    assert session.ui.hints[-1]["hint_id"] == "step4_fled"

    session.submit("attack")
    assert session.engine.cmd_handler.current_combat_session is not None


def test_fleeing_an_ordinary_fight_still_moves_the_enemy_out(session: GameSession) -> None:
    session.player.tutorial_state["completed"] = True
    _into_tutorial_fight(session)
    room = session.player.current_room
    session.bus.emit_event(EventType.COMBAT_ACTION_SELECTED, {"choice": "flee"}, "test")
    assert TUTORIAL_ENEMY not in session.world.get_enemies_in_room(room)


def test_battle_start_shows_system_lines_and_the_attack_list() -> None:
    player = StatsView("Tess", 100, 100, 18, "guardian")
    attacks = [AttackView("strike", "Strike", 5, 0)]
    opening = [
        {"actor": "system", "message": "Combat initiated"},
        {"actor": "system", "message": "ECHO> press 1"},
    ]
    start = render_combat_output(opening, player, attacks)
    assert "ECHO> press 1" in start and "Strike" in start

    fighting = render_combat_output(
        [*opening, {"actor": "player", "message": "hit"}], player, attacks
    )
    assert "hit" in fighting and "Strike" not in fighting  # log only, no attack list


def test_quit_chooser_survives_a_full_repaint(monkeypatch: pytest.MonkeyPatch) -> None:
    """QuitConfirmScreen once defined _render, shadowing Textual's own
    Widget._render; any repaint of the screen then crashed the app."""
    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            screen = QuitConfirmScreen(lambda choice: None)
            app.push_screen(screen)
            await pilot.pause()
            screen.refresh()
            await pilot.pause()
            assert screen.is_attached

    asyncio.run(scenario())
