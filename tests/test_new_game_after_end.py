"""Post-game 'n' must re-offer difficulty + class, not restart as default guardian."""
from engine.api import GameSession
from src.state_manager import state_manager


def test_n_after_win_lands_in_difficulty_picker():
    s = GameSession()
    s.new_game("t", "shaman")
    s.engine.cmd_handler.win_game()
    s.submit("n")
    assert str(state_manager.current_state) == "waiting_for_difficulty"
    s.close()
