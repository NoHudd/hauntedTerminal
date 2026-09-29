"""Game-over screens with the real engine and TUI wired together.

A death keeps the fight on screen and drains it straight to black; the room
must not reappear behind it. Only a death shows the GAME OVER card: a restart
(F5) or a post-win "new game" / "restore" is not a death.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

import src.save as save_mod
from engine.events import EventType
from src.game_engine import ImprovedGameEngine
from src.game_world import TUTORIAL_ENEMY
from src.save import SaveManager
from src.ui.textual_ui import TextualGameUI


@pytest.fixture(autouse=True)
def _no_intro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)


def _record(monkeypatch: pytest.MonkeyPatch, obj: object, names: list[str],
            calls: list[str]) -> None:
    for name in names:
        original: Callable[..., object] = getattr(obj, name)

        def wrapper(*args: object, _name: str = name,
                    _original: Callable[..., object] = original, **kwargs: object) -> object:
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(obj, name, wrapper)


def _new_game(app: TextualGameUI, monkeypatch: pytest.MonkeyPatch) -> ImprovedGameEngine:
    # After mount: mounting re-applies the user's settings, which set this flag.
    # With it on, game-over timers fire immediately, so a stray card shows up.
    monkeypatch.setattr("config.dev_config.DISABLE_ANIMATIONS", True)
    engine = ImprovedGameEngine(ui=app)
    assert engine.create_player("Tess", "guardian")
    engine.start_game()
    return engine


def _lose_a_fight(engine: ImprovedGameEngine) -> None:
    handler = engine.cmd_handler
    assert handler is not None and engine.player is not None
    room = engine.player.current_room
    engine.world.spawn_tutorial_enemy(room)
    enemy = engine.world.get_enemy(TUTORIAL_ENEMY, engine.player.player_class)
    enemy.health = 10**6
    enemy.damage = 10**6
    handler.start_combat([(TUTORIAL_ENEMY, enemy)])
    session = handler.current_combat_session
    attack_id = next(iter(session.available_attacks))
    engine.bus.emit_event(EventType.COMBAT_ACTION_SELECTED, {"choice": attack_id}, "test")


def test_death_drains_the_fight_without_showing_the_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            engine = _new_game(app, monkeypatch)
            await pilot.pause()
            calls: list[str] = []
            _record(monkeypatch, app._scene_view, ["end_battle", "play_death"], calls)
            _record(monkeypatch, app, ["display_game_over"], calls)

            _lose_a_fight(engine)
            await pilot.pause()

            assert calls == ["play_death", "display_game_over"]
            engine._cleanup()

    asyncio.run(scenario())


def test_f5_restart_returns_to_the_title_without_a_game_over_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            engine = _new_game(app, monkeypatch)
            await pilot.pause()
            calls: list[str] = []
            _record(monkeypatch, app, ["display_game_over", "_display_title_screen"], calls)

            app.action_restart_game()
            await pilot.pause()

            assert calls == ["_display_title_screen"]
            engine._cleanup()

    asyncio.run(scenario())


@pytest.mark.parametrize("choice", ["n", "r"])
def test_post_win_choices_do_not_show_a_game_over_card(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, choice: str,
) -> None:
    mgr = SaveManager(save_dir=str(tmp_path))
    monkeypatch.setattr(save_mod, "save_manager", mgr)
    monkeypatch.setattr("src.game_engine.save_manager", mgr)
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            engine = _new_game(app, monkeypatch)
            mgr.save_game(engine.player, engine.world.get_state())
            await pilot.pause()
            calls: list[str] = []
            _record(monkeypatch, app, ["display_game_over"], calls)

            engine.cmd_handler.flow.handle_game_over_input(choice)
            await pilot.pause()

            assert calls == []
            engine._cleanup()

    asyncio.run(scenario())
