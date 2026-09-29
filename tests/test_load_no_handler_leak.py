"""Loading a game must not leak the previous CommandHandler's subscriptions.

The load paths built a new handler without unsubscribing the old one, so the
dead run's handler kept reacting to events with its stale player — observed
live as a fresh game instantly fighting the previous run's boss.

Assertion is object-identity based (is the OLD handler still subscribed?)
because the module-singleton bus can carry handlers leaked by other tests.
"""
from engine.api import GameSession


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
        old_parts = {id(old_handler), id(old_handler.tutorial)}
        leaked = [
            (event_type, cb)
            for event_type, callbacks in s.bus._listeners.items()
            for cb in callbacks
            if id(getattr(cb, "__self__", None)) in old_parts
        ]
        assert leaked == [], (
            "old CommandHandler still subscribed after load — its stale player "
            "will react to the new run's events"
        )
    finally:
        s.close()
