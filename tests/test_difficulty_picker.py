"""Picking difficulty at start sets the run's mode and advances to class selection."""
from __future__ import annotations

import pytest

from engine.headless import HeadlessUI
from src import difficulty
from src.game_engine import ImprovedGameEngine
from src.game_states import GameState
from src.state_manager import state_manager


@pytest.mark.parametrize("choice,expected", [("1", "easy"), ("2", "medium"), ("3", "hard")])
def test_difficulty_pick_sets_mode_and_advances(choice, expected):
    eng = ImprovedGameEngine(ui=HeadlessUI())
    eng._handle_difficulty_input(choice)
    assert difficulty.current_mode() == expected
    assert state_manager.current_state == GameState.WAITING_FOR_CLASS


def test_invalid_difficulty_choice_reprompts():
    eng = ImprovedGameEngine(ui=HeadlessUI())
    before = difficulty.current_mode()
    eng._handle_difficulty_input("9")   # invalid
    assert difficulty.current_mode() == before  # unchanged
    assert state_manager.current_state == GameState.WAITING_FOR_DIFFICULTY
