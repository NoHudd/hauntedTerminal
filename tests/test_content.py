"""Content integrity suite — the safety net Phase 1 exists to provide.

These tests catch the class of bug the old string-coupled loader shipped
silently (e.g. the ghost_hidden key mismatch): broken id-references, unreachable
rooms, and classes that fail to boot. They run against the real data/ content.
"""
from __future__ import annotations

from collections import deque

import pytest

from engine.content import (
    GameContent,
    find_broken_references,
    find_reference_warnings,
    link,
    load_all,
)
from engine.schema import DanglingReferenceError, Room

START_ROOM = "home_grove"


@pytest.fixture(scope="module")
def content() -> GameContent:
    return load_all("data")


# --- loading & schema -------------------------------------------------------

def test_all_content_loads(content: GameContent) -> None:
    assert len(content.rooms) == 18
    assert len(content.classes) == 3
    assert len(content.enemies) == 24
    assert content.items and content.npcs and content.abilities and content.attacks


# --- load-bearing referential integrity -------------------------------------

def test_no_load_bearing_dangling_references(content: GameContent) -> None:
    problems = find_broken_references(content)
    assert problems == [], "dangling load-bearing refs:\n" + "\n".join(problems)


def test_link_succeeds_on_real_content(content: GameContent) -> None:
    # Should not raise.
    assert link(content) is content


def test_link_raises_on_broken_exit() -> None:
    broken = GameContent(
        rooms={"start": Room(id="start", name="Start", exits=["nowhere"])}  # type: ignore[dict-item]
    )
    with pytest.raises(DanglingReferenceError) as exc:
        link(broken)
    assert "nowhere" in str(exc.value)


def test_link_raises_on_broken_key_required() -> None:
    broken = GameContent(
        rooms={"vault": Room(id="vault", name="Vault", key_required="ghost_key")}  # type: ignore[dict-item]
    )
    with pytest.raises(DanglingReferenceError):
        link(broken)


# --- classes boot -----------------------------------------------------------

def test_all_classes_have_valid_stats(content: GameContent) -> None:
    for cid, klass in content.classes.items():
        assert klass.base_health > 0, f"{cid} base_health"
        assert klass.base_damage > 0, f"{cid} base_damage"


def test_players_boot_for_every_class(content: GameContent) -> None:
    # Integration: the real player code path must build each class from data.
    from src.player import Player

    for cid in content.classes:
        player = Player("Tester", cid, START_ROOM)
        assert player.max_health > 0
        assert player.total_damage > 0


# --- reachability -----------------------------------------------------------

def _reachable(content: GameContent, start: str = START_ROOM) -> set[str]:
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        room = content.rooms.get(queue.popleft())  # type: ignore[arg-type]
        if not room:
            continue
        for dest in room.exits:
            if dest in content.rooms and dest not in seen:
                seen.add(dest)
                queue.append(dest)
    return seen


def test_non_hidden_rooms_reachable_via_exits(content: GameContent) -> None:
    reachable = _reachable(content)
    stranded = sorted(
        rid
        for rid, room in content.rooms.items()
        if rid not in reachable and not room.hidden
    )
    assert stranded == [], f"non-hidden rooms unreachable via exits: {stranded}"


# --- known findings (documented, not yet fixed) -----------------------------

KNOWN_ADVISORY_WARNINGS = {
    # root_key is orphaned content: unlocks a room that doesn't exist and no room
    # requires it. Awaiting a design decision (add room vs. cut key).
    "item 'root_key' unlocks: references unknown room 'root_vault'",
}


def test_advisory_warnings_match_known_findings(content: GameContent) -> None:
    """Regression fence: if a NEW advisory warning appears, this fails so it gets
    triaged; when a known one is fixed, remove it from KNOWN_ADVISORY_WARNINGS.
    """
    current = set(find_reference_warnings(content))
    unexpected = current - KNOWN_ADVISORY_WARNINGS
    assert not unexpected, f"new advisory dangling refs: {sorted(unexpected)}"


@pytest.mark.xfail(
    reason="mirror_sector is hidden but has no exit, discovery rule, or cd alias "
    "into it — genuinely unreachable content. Design decision pending.",
    strict=True,
)
def test_mirror_sector_is_reachable_somehow(content: GameContent) -> None:
    # Documents the known unreachable-content finding. Flips to a real pass once
    # an entry path is added (or delete this test if mirror_sector is cut).
    assert "mirror_sector" in _reachable(content)
