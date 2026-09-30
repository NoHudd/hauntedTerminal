"""Not-found errors should say what the player probably meant, or what is here."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.commands.hints import not_found_hint


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tester", "guardian")
    try:
        yield s
    finally:
        s.close()


def _text(lines: list[str]) -> str:
    return "\n".join(lines)


# --- unit: the hint builder --------------------------------------------------

def test_hint_suggests_close_match() -> None:
    hint = not_found_hint(
        "segfault_sheld", ["health_packet", "segfault_shield"], label="Items here"
    )
    assert "Did you mean" in hint and "segfault_shield" in hint


def test_hint_is_case_insensitive_and_returns_canonical_name() -> None:
    hint = not_found_hint("SEGFAULT_SHIELd", ["segfault_shield"], label="Items here")
    assert "segfault_shield" in hint


def test_hint_lists_candidates_when_nothing_is_close() -> None:
    hint = not_found_hint("zzzz", ["health_packet", "segfault_shield"], label="Items here")
    assert "Did you mean" not in hint
    assert "Items here" in hint and "health_packet" in hint and "segfault_shield" in hint


def test_hint_is_empty_when_no_candidates() -> None:
    assert not_found_hint("anything", [], label="Items here") == ""


def test_hint_dedupes_candidates() -> None:
    hint = not_found_hint("zzzz", ["a_thing", "a_thing", "b_thing"], label="Here")
    assert hint.count("a_thing") == 1


# --- integration: through the real commands ----------------------------------

def test_take_typo_gets_did_you_mean(session: GameSession) -> None:
    out = _text(session.submit("take segfault_sheld"))
    assert "Cannot find segfault_sheld" in out
    assert "Did you mean" in out and "segfault_shield" in out


def test_take_unknown_lists_room_items(session: GameSession) -> None:
    out = _text(session.submit("take zzzz"))
    assert "Cannot find zzzz" in out
    assert "Items here" in out and "segfault_shield" in out


def test_cat_typo_gets_did_you_mean(session: GameSession) -> None:
    out = _text(session.submit("cat segfault_sheld"))
    assert "Did you mean" in out and "segfault_shield" in out


def test_a_typo_never_reveals_a_hidden_file(session: GameSession) -> None:
    out = _text(session.submit("cat bash_profil"))
    assert "Cannot find" in out
    assert "bash_profile" not in out


def test_examine_typo_gets_did_you_mean(session: GameSession) -> None:
    out = _text(session.submit("examine segfault_sheld"))
    assert "Did you mean" in out and "segfault_shield" in out


def test_cd_typo_gets_did_you_mean(session: GameSession) -> None:
    out = _text(session.submit("cd mnt_forst"))
    assert "No such file or directory" in out
    assert "Did you mean" in out and "mnt_forest" in out


def test_equip_typo_gets_did_you_mean(session: GameSession) -> None:
    session.submit("take segfault_shield")
    out = _text(session.submit("equip segfault_sheld"))
    assert "Did you mean" in out and "segfault_shield" in out


def test_drop_typo_gets_did_you_mean(session: GameSession) -> None:
    session.submit("take segfault_shield")
    out = _text(session.submit("drop segfault_sheld"))
    assert "Did you mean" in out and "segfault_shield" in out
