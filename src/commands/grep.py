"""grep: search a file for a word and print only the matching lines."""
from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from rich.markup import escape

from src.commands.base import Command
from src.commands.hints import show_not_found, visible_room_items
from src.logs import log_lines

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler

USAGE = (
    "[yellow]Usage: grep <word> <file>[/yellow]\n"
    "[dim]Example: grep FLAG kern_log   (add -i to ignore case, -n to number lines)[/dim]"
)


def _shown(ctx: "CommandHandler", item_id: str) -> str:
    """The name as ls -a shows it: hidden files keep their leading dot."""
    item = ctx.world.get_item(item_id)
    return f".{item_id}" if item is not None and item.hidden else item_id


class GrepCommand(Command):
    name = "grep"
    MAX_SHOWN = 40

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        try:
            # The command line arrives split on spaces; rejoin quoted phrases.
            tokens = shlex.split(" ".join(args))
        except ValueError:  # an unclosed quote
            tokens = list(args)
        opts = "".join(a[1:] for a in tokens if a.startswith("-") and len(a) > 1)
        rest = [a for a in tokens if not (a.startswith("-") and len(a) > 1)]
        if len(rest) < 2:
            ctx.output.write(USAGE)
            return
        pattern = rest[0].strip("'\"")
        name = " ".join(rest[1:])

        room_id = ctx.player.current_room
        item_id = ctx.resolver.find_in_list(name, ctx.world.get_items_in_room(room_id))
        item = ctx.world.get_item(item_id) if item_id else None
        if item is None:
            inv_id = ctx.resolver.find_in_inventory(name)
            if inv_id:
                item_id, item = inv_id, ctx.player.get_item_from_inventory(inv_id)
        if item is None or item_id is None:
            swapped = ctx.resolver.find_in_list(
                rest[0], ctx.world.get_items_in_room(room_id)
            )
            if swapped:
                ctx.output.write(
                    "[yellow]grep takes the word first, then the file. Try "
                    f"[bold]grep {escape(name)} {escape(_shown(ctx, swapped))}[/bold]"
                    "[/yellow]"
                )
                return
            show_not_found(
                ctx,
                f"[bold red]grep: {escape(name)}: No such file[/bold red]",
                name,
                visible_room_items(ctx, room_id),
                label="Files here",
            )
            return

        lines = log_lines(item) if item.log is not None else (item.content or "").splitlines()
        if not lines:
            ctx.output.write(f"[yellow]grep: {escape(item_id)}: nothing to search[/yellow]")
            return

        ignore_case = "i" in opts
        numbered = "n" in opts
        needle = pattern.lower() if ignore_case else pattern
        hits = [
            (i + 1, line) for i, line in enumerate(lines)
            if needle in (line.lower() if ignore_case else line)
        ]
        if not hits:
            msg = f"[dim](no lines contain '{escape(pattern)}')[/dim]"
            if not ignore_case and any(pattern.lower() in line.lower() for line in lines):
                msg += (
                    "\n[yellow]grep is case-sensitive: that word is in there in "
                    "different capitals. Try "
                    f"[bold]grep -i {escape(pattern)} {escape(_shown(ctx, item_id))}[/bold]"
                    "[/yellow]"
                )
            ctx.output.write(msg)
            return

        shown = hits[: self.MAX_SHOWN]
        body = "\n".join(
            f"{n}:{escape(line)}" if numbered else escape(line) for n, line in shown
        )
        if len(hits) > self.MAX_SHOWN:
            body += f"\n[dim]… {len(hits) - self.MAX_SHOWN} more matching lines[/dim]"
        ctx.output.write(body)
        # Only lines actually on screen count: a capped listing that hides the
        # flag line has not shown the player the flag.
        ctx.flags.on_grep(item_id, [line for _, line in shown])
