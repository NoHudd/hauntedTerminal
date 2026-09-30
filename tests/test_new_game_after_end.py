"""After a win: 'm' returns to the main menu, and the run is marked cleared."""
from engine.api import GameSession
from src.game_states import GameState
from src.save import save_manager


def test_m_after_win_returns_to_the_main_menu():
    s = GameSession()
    s.new_game("t", "shaman")
    s.engine.cmd_handler.flow.win_game()
    s.submit("m")
    assert s.state == GameState.MENU
    s.close()


def test_winning_marks_the_run_cleared():
    s = GameSession()
    s.new_game("t", "shaman")
    s.submit("save")
    s.engine.cmd_handler.flow.win_game()
    assert save_manager.list_runs()[0].cleared is True
    s.close()
