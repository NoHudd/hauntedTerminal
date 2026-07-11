"""Content validation CLI.

    python -m engine.validate [data_dir]

Exit 0 == content loads, validates, and links cleanly. Non-zero with a precise
message otherwise. Intended for a pre-commit / CI gate so broken content is
caught at author time, never by a player.
"""
from __future__ import annotations

import sys
from collections import deque

from engine.content import (
    GameContent,
    find_broken_references,
    find_dialogue_problems,
    find_reference_warnings,
    load_all,
)
from engine.schema import ContentError, RoomId

# Where the player begins. Hidden rooms are not reached via exits; see below.
START_ROOM = "home_grove"


def reachable_rooms(content: GameContent, start: str = START_ROOM) -> set[str]:
    """Rooms reachable from start following one-way exits only."""
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        room = content.rooms.get(RoomId(current))
        if not room:
            continue
        for dest in room.exits:
            if dest in content.rooms and dest not in seen:
                seen.add(str(dest))
                queue.append(str(dest))
    return seen


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    data_dir = argv[0] if argv else "data"

    try:
        content = load_all(data_dir)
    except ContentError as exc:
        print(f"CONTENT LOAD FAILED:\n{exc}", file=sys.stderr)
        return 1

    problems = find_broken_references(content) + find_dialogue_problems(content)
    if problems:
        print(f"LINK FAILED — {len(problems)} dangling reference(s):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(
        f"OK: {len(content.rooms)} rooms, {len(content.items)} items, "
        f"{len(content.enemies)} enemies, {len(content.npcs)} npcs, "
        f"{len(content.classes)} classes, {len(content.abilities)} abilities, "
        f"{len(content.attacks)} attacks — all references resolve."
    )

    # Advisory dangling refs (dead content, not crashes) — reported, not fatal.
    for warning in find_reference_warnings(content):
        print(f"WARNING: {warning}", file=sys.stderr)

    # Reachability is a warning, not a failure: hidden rooms are reached via
    # discovery/aliases, not exits. Non-hidden unreachable rooms are real bugs.
    reachable = reachable_rooms(content)
    stranded = [
        rid
        for rid, room in content.rooms.items()
        if rid not in reachable and not room.hidden
    ]
    if stranded:
        print(
            "WARNING: non-hidden rooms unreachable via exits: "
            + ", ".join(sorted(stranded)),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
