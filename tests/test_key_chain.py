"""Keys come from flags in a fixed chain; locked doors stay invisible until
their key reveals them."""
from engine.api import GameSession
from engine.content import find_key_chain_problems, load_all


def test_chain_is_declared_and_valid() -> None:
    content = load_all("data")
    grants = {rid: room.flag.grants for rid, room in content.rooms.items()
              if room.flag is not None and room.flag.grants}
    assert grants == {"mnt_forest": "lib_key", "var_dungeon": "chmod_key",
                      "usr_lib_arcane": "opt_key"}
    assert "chmod_key" not in content.rooms["var_dungeon"].items
    assert find_key_chain_problems(content) == []


def test_validator_catches_a_chain_that_cannot_reach_the_gate() -> None:
    content = load_all("data")
    mnt = content.rooms["mnt_forest"]
    assert mnt.flag is not None
    content.rooms["mnt_forest"] = mnt.model_copy(update={
        "flag": mnt.flag.model_copy(update={"grants": None})
    })
    assert any("core" in p for p in find_key_chain_problems(content))


def _session() -> GameSession:
    s = GameSession()
    s.new_game("t", "guardian")
    return s


def test_locked_door_is_invisible_until_revealed() -> None:
    s = _session()
    try:
        w = s.world
        assert not w.door_visible("usr_lib_arcane")
        assert not w.door_visible("usr_share_games")  # beneath /usr
        assert w.door_visible("core")  # the flag-gated goal stays in view
        allowed, denial = w.check_access("usr_lib_arcane", s.player)
        assert not allowed and denial["reason"] == "missing"
        assert w.reveal_doors("lib_key") == ["usr_lib_arcane"]
        assert w.door_visible("usr_lib_arcane") and w.door_visible("usr_share_games")
        assert w.check_access("usr_lib_arcane", s.player)[1]["reason"] == "locked"
    finally:
        s.close()


def test_no_key_is_placed_at_random() -> None:
    from src.item_placer import ItemPlacer

    s = _session()
    try:
        placer = ItemPlacer(s.world)
        placer.place_items("guardian")
        placed = {k for k in s.world.item_locations if placer.is_key(k)}
        assert placed == set()
    finally:
        s.close()
