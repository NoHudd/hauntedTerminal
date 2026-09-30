"""Players type item names however they like: case, `_`, `-`, spaces and
camelCase must all find the same item, and item commands read the whole name,
not just its first word."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("t", "guardian")
    s.player.tutorial_state["completed"] = True
    try:
        yield s
    finally:
        s.close()


def _out(session: GameSession, cmd: str) -> str:
    return "\n".join(str(line) for line in session.submit(cmd))


SPELLINGS = [
    "health_packet", "healthpacket", "health-packet", "health packet",
    "healthPacket", "HEALTH_PACKET", "Health Packet",
]


@pytest.mark.parametrize("typed", SPELLINGS)
def test_take_accepts_any_spelling(session: GameSession, typed: str) -> None:
    session.submit(f"take {typed}")
    assert session.player.has_item("health_packet")


def test_take_matches_every_word_not_just_the_first(session: GameSession) -> None:
    """'stable cache' must not be read as 'stable' and grab whatever starts
    with it — the whole name decides."""
    h = session.engine.cmd_handler
    h.world.item_locations["stable_cache"] = session.player.current_room
    session.submit("take stable cache")
    assert session.player.has_item("stable_cache")
    assert not session.player.has_item("health_packet")


def test_separator_only_input_matches_nothing(session: GameSession) -> None:
    before = set(session.player.inventory)
    session.submit("take _")
    assert set(session.player.inventory) == before


def test_cat_accepts_spaced_and_camel_names(session: GameSession) -> None:
    assert "Sysadmin Spirit" in _out(session, "cat bash profile")
    assert "Sysadmin Spirit" in _out(session, "cat bashProfile")


def test_drop_resolves_the_name(session: GameSession) -> None:
    """The guardian also starts with a numbered packet (health_packet_1); the
    exact id wins over a copy that only shares the display name."""
    session.submit("take health_packet")
    session.submit("drop health packet")
    assert not session.player.has_item("health_packet")
    assert "health_packet" in session.world.get_items_in_room(session.player.current_room)


def test_examine_resolves_the_name(session: GameSession) -> None:
    out = _out(session, "examine health packet")
    assert "Cannot find" not in out
    assert "Health Packet" in out


def test_equip_resolves_a_spaced_name(session: GameSession) -> None:
    h = session.engine.cmd_handler
    h.world.item_locations["segfault_shield"] = session.player.current_room
    session.submit("take segfault_shield")
    session.submit("equip segfault shield")
    assert session.player.equipped_weapon == "segfault_shield"


def test_use_resolves_a_spaced_name(session: GameSession) -> None:
    session.submit("take health_packet")
    session.player.health = 10
    session.submit("use health packet")
    assert session.player.health > 10


def test_a_misspelled_name_points_at_tab_completion(session: GameSession) -> None:
    out = _out(session, "take helth")
    assert "Cannot find" in out
    assert "Tab" in out
