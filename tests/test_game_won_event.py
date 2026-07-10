"""GAME_WON: emitted with sections + stats; headless UI logs the text."""
from engine.api import GameSession
from src.events import EventType, event_bus


def test_win_game_emits_sections_and_stats():
    s = GameSession()
    s.new_game("t", "guardian")
    got = []

    def on_won(event):
        got.append(event.data)

    event_bus.subscribe(EventType.GAME_WON, on_won)
    try:
        s.engine.cmd_handler.win_game()
    finally:
        event_bus.unsubscribe(EventType.GAME_WON, on_won)
    assert len(got) == 1
    data = got[0]
    assert data["ending_id"] == "restore"
    assert len(data["sections"]) >= 3
    stats = data["stats"]
    for key in ("level", "cycles", "kills", "items_found", "difficulty",
                "ending", "player_name", "player_class"):
        assert key in stats
    s.close()


def test_headless_ui_receives_ending_text():
    s = GameSession()
    s.new_game("t", "guardian")
    s.ui.drain()
    s.engine.cmd_handler.win_game()
    text = "\n".join(str(x) for x in s.ui.drain())
    assert "THANK YOU FOR PLAYING" in text
    s.close()
