"""keys: held keys and their doors; unearned keys as ??? by source."""
from engine.api import GameSession


def _keys(s: GameSession) -> str:
    return "\n".join(str(x) for x in s.submit("keys"))


def test_unearned_keys_are_hidden_by_source() -> None:
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        out = _keys(s)
        assert "/usr" not in out and "/etc" not in out and "/dev" not in out
        assert "lib_key" not in out
        assert "earned by a flag" in out and "dropped by a boss" in out
        s.player.add_to_inventory("lib_key", s.world.get_item("lib_key"))
        s.world.reveal_doors("lib_key")
        assert "/usr" in _keys(s)
    finally:
        s.close()
