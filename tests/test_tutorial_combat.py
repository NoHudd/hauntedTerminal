"""Tutorial combat gating: combat_action_taken fires for BOTH typed and
hotkey-simulated attacks, since both paths emit the same COMBAT_ACTION_RESULT
event that CommandHandler now listens for."""
from src.events import EventType, event_bus


def _start_tutorial_fight(s):
    """Equip the guardian's starter weapon (spawns the tutorial enemy as a
    side effect, same as the real game) and return the live CombatSession."""
    h = s.engine.cmd_handler
    h.world.item_locations["segfault_shield"] = s.player.current_room
    s.submit("take segfault_shield")
    s.submit("equip segfault_shield")
    assert h.current_combat_session is not None
    assert h.current_combat_session.awaiting_action
    return h


def test_typed_attack_sets_combat_action_taken():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = _start_tutorial_fight(s)
        attack_id = next(iter(h.current_combat_session.available_attacks))
        s.submit(attack_id)
        assert s.player.tutorial_state["combat_action_taken"] is True
    finally:
        s.close()


def test_hotkey_simulated_attack_sets_combat_action_taken():
    """The hotkey path never calls CommandHandler.handle_command — it emits
    COMBAT_ACTION_SELECTED directly (see TextualGameUI._execute_combat_hotkey).
    Simulate that exact event to prove the gate no longer depends on typed
    input."""
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = _start_tutorial_fight(s)
        attack_id = next(iter(h.current_combat_session.available_attacks))
        assert s.player.tutorial_state["combat_action_taken"] is False
        s.ui.clear_console()
        event_bus.emit_event(
            EventType.COMBAT_ACTION_SELECTED, {"choice": attack_id}, "Test"
        )
        s.ui.drain()
        assert s.player.tutorial_state["combat_action_taken"] is True
    finally:
        s.close()


def test_get_current_tutorial_step_reaches_step6_after_combat():
    """Regression for the selection_mode_used/combat_selection key mismatch:
    after combat_action_taken flips, the fallback step lookup must reach
    step6, not loop on step5 forever."""
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = _start_tutorial_fight(s)
        s.player.tutorial_state["combat_action_taken"] = True
        assert h._get_current_tutorial_step() == "step6"
    finally:
        s.close()
