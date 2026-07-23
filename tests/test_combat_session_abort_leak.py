"""Tearing down a CommandHandler mid-combat must not leak the CombatSession's
COMBAT_ACTION_SELECTED subscription.

CombatSession only unsubscribes itself in _end_combat, reached exclusively via
a real victory/defeat/flee outcome. If the owning session is closed while
combat is still active (restart, save/load mid-fight, or — as found while
writing a tutorial-copy test — simply closing a test's GameSession before the
fight resolves), the stale CombatSession stayed subscribed and started
double-processing the NEXT combat's actions: its own leftover enemy_health hit
0 too, so it independently reached victory and emitted a second, phantom
COMBAT_ENDED that the live CommandHandler (a different instance, but the same
event type) also reacted to.

Assertion is object-identity based (matching test_load_no_handler_leak.py's
pattern) because the module-singleton bus can carry handlers leaked by other
tests.
"""
from engine.api import GameSession
from src import rng
from src.events import EventType, event_bus


def _start_unresolved_fight(s):
    h = s.engine.cmd_handler
    h.world.item_locations["segfault_shield"] = s.player.current_room
    s.submit("take segfault_shield")
    s.submit("equip segfault_shield")
    assert h.current_combat_session is not None
    assert h.current_combat_session.is_active
    return h


def test_closing_mid_combat_unsubscribes_the_session():
    s = GameSession()
    old_session = None
    try:
        s.new_game("t", "guardian")
        h = _start_unresolved_fight(s)
        old_session = h.current_combat_session
    finally:
        s.close()

    assert old_session is not None
    subs = event_bus._listeners.get(EventType.COMBAT_ACTION_SELECTED, [])
    assert all(getattr(cb, "__self__", None) is not old_session for cb in subs), (
        "old CombatSession still subscribed after teardown — it will "
        "double-process the next combat's actions"
    )
    assert old_session.is_active is False


def test_next_combat_after_unresolved_close_gets_single_ended_event():
    """End-to-end: an unresolved fight from a prior (closed) session must not
    cause the NEXT session's combat to emit COMBAT_ENDED twice."""
    leaked = GameSession()
    leaked.new_game("t", "guardian")
    _start_unresolved_fight(leaked)
    leaked.close()

    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = _start_unresolved_fight(s)
        attack_id = next(iter(h.current_combat_session.available_attacks))
        # Force a guaranteed one-shot kill on the next landed hit, and force
        # the accuracy roll (src.rng, same module combat.py's attacks use) to
        # always hit — this test is about the COMBAT_ENDED event count, not
        # combat math, so remove RNG as a flake source entirely.
        h.current_combat_session.enemy_health = 1
        original_randint = rng.randint
        rng.randint = lambda a, b: a

        ended_count = {"n": 0}

        def counter(_ev):
            ended_count["n"] += 1

        event_bus.subscribe(EventType.COMBAT_ENDED, counter)
        try:
            event_bus.emit_event(
                EventType.COMBAT_ACTION_SELECTED, {"choice": attack_id}, "Test"
            )
        finally:
            event_bus.unsubscribe(EventType.COMBAT_ENDED, counter)
            rng.randint = original_randint

        assert ended_count["n"] == 1, f"COMBAT_ENDED fired {ended_count['n']} times, expected 1"
    finally:
        s.close()
