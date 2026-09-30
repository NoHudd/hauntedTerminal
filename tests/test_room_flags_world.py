"""Flag capture is world state: saved with room_states, and part of ✓."""
from engine.api import GameSession
from src.game_world import GameWorld


def _world() -> GameWorld:
    s = GameSession()
    s.new_game("t", "guardian")
    w = s.world
    s.close()
    return w


def test_capture_is_recorded_per_room() -> None:
    w = _world()
    assert not w.flag_captured("root")
    w.mark_flag_captured("root")
    assert w.flag_captured("root")
    assert w.room_states["root"]["flagCaptured"] is True


def test_a_flag_room_is_not_done_until_its_flag_is_captured() -> None:
    w = _world()
    w.set_room_visited("home_grove")  # no enemies, visited
    assert w.is_room_cleared("home_grove") is False
    w.mark_flag_captured("home_grove")
    assert w.is_room_cleared("home_grove") is True


def test_rooms_without_a_flag_keep_the_old_rule() -> None:
    """Every shipped room has a flag now; strip one to keep the rule honest."""
    w = _world()
    w.rooms["proc_secrets"] = w.rooms["proc_secrets"].model_copy(update={"flag": None})
    w.set_room_visited("proc_secrets")
    assert w.is_room_cleared("proc_secrets") is True


def test_captured_flag_survives_a_round_trip() -> None:
    w = _world()
    w.set_room_visited("root")
    w.mark_flag_captured("root")
    fresh = _world()
    fresh.set_state(w.get_state())
    assert fresh.flag_captured("root") and fresh.is_room_cleared("root")


def test_hidden_listed_is_saved_camel_case() -> None:
    w = _world()
    w.mark_hidden_files_listed("home_grove")
    assert w.room_states["home_grove"]["hiddenListed"] is True
    assert "hidden_listed" not in w.room_states["home_grove"]
