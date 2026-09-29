"""Tutorial combat gating: combat_action_taken fires for BOTH typed and
hotkey-simulated attacks, since both paths emit the same COMBAT_ACTION_RESULT
event that CommandHandler now listens for."""
from src.events import EventType


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
        s.bus.emit_event(
            EventType.COMBAT_ACTION_SELECTED, {"choice": attack_id}, "Test"
        )
        s.ui.drain()
        assert s.player.tutorial_state["combat_action_taken"] is True
    finally:
        s.close()


def test_get_current_tutorial_step_moves_past_combat():
    """Regression for the selection_mode_used/combat_selection key mismatch:
    after combat_action_taken flips, the fallback step lookup must move on to
    the post-combat step (ps), not loop on step5 forever."""
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = _start_tutorial_fight(s)
        s.player.tutorial_state["combat_action_taken"] = True
        assert h.tutorial.current_step() == "step5_postcombat"
    finally:
        s.close()


def test_step4_hint_does_not_instruct_typed_attack():
    """The tutorial must never tell the player to type 'attack' — combat has
    never accepted that literal word (playtester got stuck on this)."""
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = s.engine.cmd_handler
        h.world.item_locations["segfault_shield"] = s.player.current_room
        s.submit("take segfault_shield")
        out = "\n".join(s.submit("equip segfault_shield"))
        assert "type: [bold]attack[/bold]" not in out.lower()
    finally:
        s.close()


def test_completed_hint_documents_flee_hotkey():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = s.engine.cmd_handler
        h.tutorial.show_hint("completed")
        out = "\n".join(s.ui.drain())
    finally:
        s.close()
    assert "[bold]0[/bold]" in out
    assert "flee" in out.lower()


def test_post_combat_hint_fires_once_not_doubled():
    """Winning the tutorial fight gives one post-combat hint (which points at
    ps) — the next step must not auto-fire right after it (that was two ECHO
    messages back to back)."""
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = _start_tutorial_fight(s)
        attack_id = next(iter(h.current_combat_session.available_attacks))
        s.ui.hints.clear()
        for _ in range(5):
            if not h.current_combat_session:
                break
            s.bus.emit_event(
                EventType.COMBAT_ACTION_SELECTED, {"choice": attack_id}, "Test"
            )
        fired = [hint["hint_id"] for hint in s.ui.hints]
        assert fired.count("step5_postcombat") == 1
        assert fired[-1] == "step5_postcombat"  # nothing fires right after it
    finally:
        s.close()


def test_skip_then_equip_does_not_force_the_tutorial_fight():
    """Skipping the tutorial sets completed=True but not equipped_weapon, and
    the equip hook only checked the latter: the first equip still spawned the
    scripted enemy and shoved the skipping player into an unexplained fight."""
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        s.player.tutorial_state["completed"] = True  # what the skip path sets
        h = s.engine.cmd_handler
        h.world.item_locations["segfault_shield"] = s.player.current_room
        s.submit("take segfault_shield")
        s.submit("equip segfault_shield")
        assert h.current_combat_session is None
        assert h.world.get_enemies_in_room("home_grove") == []
    finally:
        s.close()
