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
from src import room_paths

START_ROOM = "home_grove"


@pytest.fixture(scope="module")
def content() -> GameContent:
    return load_all("data")


# --- loading & schema -------------------------------------------------------

def test_all_content_loads(content: GameContent) -> None:
    assert len(content.rooms) == 18
    assert len(content.classes) == 3
    assert len(content.enemies) == 27
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


def test_hidden_rooms_reachable_via_path_tree(content: GameContent) -> None:
    """Hidden rooms are not entered through `exits` — `cd` walks the path tree.

    A hidden room is reachable when its parent directory is itself reachable,
    since `ls -a` in the parent reveals the child. Guarding the parent link is
    what catches a reparented or orphaned room.
    """
    reachable = _reachable(content)
    by_path = {room.path: rid for rid, room in content.rooms.items()}

    stranded = []
    for rid, room in content.rooms.items():
        if not room.hidden or rid in reachable:
            continue
        parent = by_path.get(room_paths.parent_path(room.path))
        if parent is None or (parent not in reachable and not content.rooms[parent].hidden):
            stranded.append(rid)

    assert stranded == [], f"hidden rooms with no reachable parent directory: {stranded}"


def test_discovery_requirements_are_granted_by_a_reachable_npc(
    content: GameContent,
) -> None:
    """A `discovery_requirement` flag must be grantable, or the room is sealed.

    mirror_sector (/proc/self, the Sudo Trial) is the live case: `ls -a` hides it
    until `sudo_quest_active` is set, and only the Process Scheduler in /proc
    sets it. If that NPC loses the flag or moves somewhere unreachable, the room
    becomes permanently unenterable — which is what this fences.
    """
    reachable = _reachable(content)
    granted: set[str] = set()
    for rid, room in content.rooms.items():
        if rid not in reachable:
            continue
        for npc_id in room.npcs or []:
            npc = content.npcs.get(npc_id)
            on_talk = getattr(npc, "on_talk", None) if npc else None
            flag = (on_talk or {}).get("story_flag") if on_talk else None
            if flag:
                granted.add(flag)

    ungrantable = sorted(
        f"{rid} needs '{req}'"
        for rid, room in content.rooms.items()
        if (req := getattr(room, "discovery_requirement", None)) and req not in granted
    )
    assert ungrantable == [], f"discovery_requirement never granted: {ungrantable}"


# --- C1: flat item files ----------------------------------------------------

def test_items_load_flat_and_count_54() -> None:
    from engine.content.loader import load_items

    items = load_items("data")
    assert len(items) == 54, len(items)  # 44 + motd/.flag + 5 logs + 3 notes
    # every item carries an explicit type (no wrapper-derived category)
    assert all(getattr(i, "type", None) for i in items.values())


def test_duplicate_item_id_raises(tmp_path) -> None:
    from engine.content.loader import load_items
    from engine.schema import ContentValidationError

    d = tmp_path / "items"
    d.mkdir()
    (d / "a.yaml").write_text("sword:\n  name: A\n  type: weapon\n")
    (d / "b.yaml").write_text("sword:\n  name: B\n  type: weapon\n")
    with pytest.raises(ContentValidationError):
        load_items(str(tmp_path))


# --- C2: room path/aliases integrity ----------------------------------------

def test_live_rooms_have_unique_paths_and_no_alias_collisions() -> None:
    from engine.content.linker import find_nav_problems
    from engine.content.loader import load_rooms
    from engine.content.world import GameContent

    rooms = load_rooms("data")
    content = GameContent(
        rooms=rooms, items={}, enemies={}, npcs={},
        classes={}, abilities={}, attacks={},
    )
    assert find_nav_problems(content) == []
    assert all(r.path for r in rooms.values()), "every room needs a path"
