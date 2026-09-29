"""Post-game 'n' must re-offer difficulty + class, not restart as default guardian."""
from engine.api import GameSession


def test_n_after_win_lands_in_difficulty_picker():
    s = GameSession()
    s.new_game("t", "shaman")
    s.engine.cmd_handler.flow.win_game()
    s.submit("n")
    assert str(s.state) == "waiting_for_difficulty"
    s.close()
