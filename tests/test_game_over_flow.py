"""Dying in combat: one clear screen whose choices all work.

The defeat animation appended ~30 frames (the panel scrolled), a `[` particle
broke its markup (a stray `[/red]` showed), the screen said both "press any
key" and "r / n / q", and after a combat death any input went to the menu, so
`r` never restored the last checkpoint.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from rich.markup import render

from engine.api import GameSession
from src.game_states import GameState
from src.save import save_manager
from utils.particle_animation import GameOverAnimation, Particle, ParticleSystem


def test_backslash_particles_do_not_leak_markup() -> None:
    """A `\\` particle made `[red]\\[/red]`, which escapes the closing tag."""
    system = ParticleSystem(10, 3)
    system.particles = [
        Particle(x=1, y=1, vx=0, vy=0, char="\\", color="red", life=1.0, decay=0.1),
        Particle(x=3, y=1, vx=0, vy=0, char="[", color="red", life=1.0, decay=0.1),
    ]
    text = render(system.render_to_string())
    assert "\\" in text.plain and "[" in text.plain
    assert "[/red]" not in text.plain


def test_final_screen_names_the_player_and_offers_only_working_choices() -> None:
    frame = GameOverAnimation(player_name="Mike")._get_final_frame()
    plain = render(frame).plain
    assert "Mike" in plain
    assert "press any key" not in plain.lower()
    for choice in ("r", "m", "q"):
        assert f"{choice} - " in plain or f"{choice} – " in plain
    assert "n - " not in plain  # new game moved to the main menu


class _RecordingUI:
    """Just enough UI for GameEngine._forward_output: which sink got what."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def update_output(self, content: Any) -> None:
        self.calls.append(("replace", content))

    def append_output(self, content: Any) -> None:
        self.calls.append(("append", content))


def test_animation_frames_replace_instead_of_piling_up() -> None:
    from src.game_engine import ImprovedGameEngine

    engine = ImprovedGameEngine.__new__(ImprovedGameEngine)
    engine.ui = _RecordingUI()
    engine._fresh_command_output = False  # mid-command: a plain write appends
    engine._forward_output("frame 1", replace=True)
    engine._forward_output("frame 2", replace=True)
    assert engine.ui.calls == [("replace", "frame 1"), ("replace", "frame 2")]


@pytest.fixture
def dead(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    """A run with a checkpoint on disk, then killed in combat."""
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    s = GameSession()
    s.new_game("Mike", "weaver")
    s.player.tutorial_state["completed"] = True
    s.submit("save")
    h = s.engine.cmd_handler
    room = s.player.current_room
    s.world.enemy_locations["corrupt_process.bin"] = room
    h.check_for_enemies()
    combat = h.current_combat_session
    assert combat is not None
    combat._enemy_turn = lambda: s.player.take_damage(9999)
    combat.enemy_health = 10_000
    s.submit(next(iter(combat.available_attacks)))
    assert s.engine.state_manager.current_state == GameState.GAME_OVER
    try:
        yield s
    finally:
        s.close()


def test_r_after_a_combat_death_restores_the_last_checkpoint(dead: GameSession) -> None:
    dead.submit("r")
    assert dead.engine.state_manager.current_state == GameState.PLAYING
    assert dead.player.is_alive()


def test_n_is_no_longer_a_game_over_choice(dead: GameSession) -> None:
    out = "\n".join(str(x) for x in dead.submit("n"))
    assert dead.engine.state_manager.current_state == GameState.GAME_OVER
    assert "Invalid option" in out and "main menu" in out


def test_r_restores_this_run_even_when_another_run_is_newer(dead: GameSession) -> None:
    this_run = save_manager.active_run_id
    other = GameSession()
    try:
        other.new_game("Other", "shaman")
        save_manager.begin_run()
        save_manager.save_game(other.player, other.world.get_state())
    finally:
        other.close()
    save_manager.resume_run(this_run)

    dead.submit("r")
    assert dead.engine.state_manager.current_state == GameState.PLAYING
    assert dead.player.name == "Mike"


def test_r_with_no_save_for_this_run_goes_to_the_menu(dead: GameSession) -> None:
    save_manager.delete_run(save_manager.active_run_id)
    out = "\n".join(str(x) for x in dead.submit("r"))
    assert dead.engine.state_manager.current_state == GameState.MENU
    assert "No backup for this run" in out


def test_anything_else_keeps_the_choices_on_screen(dead: GameSession) -> None:
    out = "\n".join(str(x) for x in dead.submit("x"))
    assert dead.engine.state_manager.current_state == GameState.GAME_OVER
    assert "r" in out and "Invalid option" in out
