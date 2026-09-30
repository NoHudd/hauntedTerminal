"""/opt and /srv are trials any class may enter; their own class gets a bonus."""
from engine.api import GameSession


def _session(cls: str) -> GameSession:
    s = GameSession()
    s.new_game("t", cls)
    s.player.tutorial_state["completed"] = True
    s.player.add_to_inventory("opt_key", s.world.get_item("opt_key"))
    s.world.discover_room("opt_mage_tower")  # /opt is hidden until found
    # Holding a key is not an open door; unlock both so only class could deny.
    s.world.unlock_room("opt_mage_tower")
    s.world.unlock_room("srv_warrior_tomb")
    return s


def test_any_class_can_enter_both_trials() -> None:
    for cls in ("guardian", "weaver", "shaman"):
        s = _session(cls)
        try:
            allowed, _ = s.world.check_access("opt_mage_tower", s.player)
            assert allowed, cls
            allowed, _ = s.world.check_access("srv_warrior_tomb", s.player)
            assert allowed, cls
        finally:
            s.close()


def test_the_trial_class_is_empowered_on_entry() -> None:
    s = _session("weaver")
    try:
        s.engine.cmd_handler.flags.on_room_entered("opt_mage_tower")
        effect = s.player.status_effects["trial_resonance"]["effect"]
        assert effect["damage_bonus"] == 4
    finally:
        s.close()


def test_other_classes_get_no_bonus() -> None:
    s = _session("guardian")
    try:
        s.engine.cmd_handler.flags.on_room_entered("opt_mage_tower")
        assert "trial_resonance" not in s.player.status_effects
    finally:
        s.close()
