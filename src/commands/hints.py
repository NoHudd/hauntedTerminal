"""Follow-up lines for not-found errors.

A bare "Cannot find X" leaves the player guessing whether the mechanic failed
or their spelling did. These helpers add one line after the error: the close
match they probably meant, or, failing that, what is actually available.
"""
from __future__ import annotations

import difflib
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.command_handler import CommandHandler

_CUTOFF = 0.6


def not_found_hint(typed: str, candidates: Iterable[str], *, label: str) -> str:
    """One markup line to show after a not-found error, or "" if nothing to say.

    Close match (case-insensitive) -> "Did you mean <name>?"
    Otherwise -> "<label>: a, b, c"
    No candidates -> "".
    """
    names = list(dict.fromkeys(c for c in candidates if c))
    if not names:
        return ""

    lowered = [n.lower() for n in names]
    match = difflib.get_close_matches(typed.lower(), lowered, n=1, cutoff=_CUTOFF)
    if match:
        canonical = names[lowered.index(match[0])]
        return f"[yellow]Did you mean [bold]{canonical}[/bold]?[/yellow]"

    return f"[dim]{label}: {', '.join(names)}[/dim]"


def show_not_found(
    ctx: "CommandHandler",
    message: str,
    typed: str,
    candidates: Iterable[str],
    *,
    label: str,
) -> None:
    """Write the error the command already produces, then the hint line."""
    ctx.output.error(message)
    hint = not_found_hint(typed, candidates, label=label)
    if hint:
        # In a fight Tab toggles Selection Mode instead, so the tip would lie.
        if ctx.current_combat_session is None:
            hint += "  [dim](Tab finishes names)[/dim]"
        ctx.output.write(hint)


def visible_room_items(ctx: "CommandHandler", room_id: str) -> list[str]:
    """Room items a suggestion may name: hidden files only show up via `ls -a`,
    so a typo must not reveal them either."""
    return [
        item_id for item_id in ctx.world.get_items_in_room(room_id) or []
        if not getattr(ctx.world.get_item(item_id), "hidden", False)
    ]


def inventory_names(player) -> list[str]:
    """Canonical inventory ids: instance suffixes like ``_2`` stripped, deduped."""
    names: list[str] = []
    for key in player.inventory.keys():
        base = key
        head, _, tail = key.rpartition("_")
        if tail.isdigit():
            base = head
        if base not in names:
            names.append(base)
    return names
