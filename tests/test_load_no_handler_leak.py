"""Loading a game must not leak the previous CommandHandler's subscriptions.

The load paths built a new handler without unsubscribing the old one, so the
dead run's handler kept reacting to ROOM_ENTERED with its stale player —
observed live as a fresh game instantly fighting the previous run's boss.

Assertion is object-identity based (is the OLD handler still subscribed?)
because the module-singleton bus can carry handlers leaked by other tests.
"""
from engine.api import GameSession
from src.events import EventType, event_bus


def test_load_game_unsubscribes_old_handler():
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        old_handler = s.engine.cmd_handler
        assert old_handler is not None

        from src.save import save_manager
        save_manager.save_game(s.player, s.world.get_state())

        # Call the load path directly (bypasses the bus, so engines leaked by
        # other tests can't distort the result).
        s.engine._load_game()

        assert s.engine.cmd_handler is not old_handler, "load did not build a new handler"
        subs = event_bus._listeners.get(EventType.ROOM_ENTERED, [])
        assert all(getattr(cb, "__self__", None) is not old_handler for cb in subs), (
            "old CommandHandler still subscribed after load — its stale player "
            "will re-trigger fights from the previous run"
        )
        # And the new handler must be live.
        assert any(getattr(cb, "__self__", None) is s.engine.cmd_handler for cb in subs)
    finally:
        s.close()
