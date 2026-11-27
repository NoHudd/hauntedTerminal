#!/usr/bin/env python3
"""Discovery commands: find, ps (reveal hidden rooms).

find walks the room tree the way the real one walks a filesystem: it prints
every directory and file under the start path that the player could know
about, optionally filtered by ``-name <glob>``. A sealed directory is listed
but answers ``Permission denied`` instead of showing its contents; a hidden
room, or a locked door its key has not revealed, does not exist to it — the
same rules ``ls`` and ``cd`` follow.
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from rich.text import Text

from src import room_paths
from src.commands.base import Command
from src.commands.navigation import listed_name

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class FindCommand(Command):
    name = "find"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        paths: list[str] = []
        pattern: str | None = None
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-name":
                if i + 1 >= len(args):
                    ctx.output.write(Text("find: missing argument to '-name'", style="red"))
                    return
                # The shell would strip these quotes before find saw them.
                pattern = args[i + 1].strip("'\"")
                i += 2
            elif arg.startswith("-"):
                ctx.output.write(Text(f"find: unknown predicate '{arg}'", style="red"))
                return
            else:
                paths.append(arg)
                i += 1

        out = Text()
        here = room_paths.room_path(ctx.player.current_room)
        for typed in paths or ["."]:
            room_id = room_paths.resolve(typed, here, ctx.room_aliases)
            if room_id is None or not self._exists(ctx, room_id):
                self._line(out, f"find: '{typed}': No such file or directory", "red")
                continue
            self._walk(ctx, out, room_id, room_paths.room_path(room_id), typed, pattern)
        if not out:
            out.append("find: nothing matched", style="dim")
        ctx.output.write(out)

    @staticmethod
    def _exists(ctx: "CommandHandler", room_id: str) -> bool:
        """Whether the player could know this directory is there: discovered,
        its door revealed, and no hidden directory above it."""
        allowed, denial = ctx.world.check_access(room_id, ctx.player)
        return allowed or (denial is not None and denial["reason"] != "missing")

    @staticmethod
    def _line(out: Text, line: str, style: str = "") -> None:
        if out:
            out.append("\n")
        out.append(line, style=style)

    def _walk(
        self, ctx: "CommandHandler", out: Text, room_id: str,
        start: str, typed: str, pattern: str | None,
    ) -> None:
        path = room_paths.room_path(room_id)

        def shown(full: str) -> str:
            # Paths read back the way the player typed the start, like find(1):
            # `find .` prints ./x, `find /var` prints /var/x.
            if full == path and path == start:
                return typed
            rel = full[len(start):].lstrip("/")
            base = typed.rstrip("/")
            return f"{base}/{rel}" if base else f"/{rel}"

        def emit(full: str, name: str, style: str) -> None:
            if pattern is None or fnmatchcase(name, pattern):
                self._line(out, shown(full), style)

        emit(path, room_paths.basename(path), "bold blue")
        if path == "/dev" and ctx.world.door_visible(room_id):
            # The device the room is named for, there for anyone who can see /dev.
            emit("/dev/null", "null", "")
        allowed, _ = ctx.world.check_access(room_id, ctx.player)
        if not allowed:
            self._line(out, f"find: '{shown(path)}': Permission denied", "red")
            return

        files = [
            listed_name(item_id, ctx.world.get_item(item_id))
            for item_id in ctx.world.get_items_in_room(room_id) or []
        ]
        for name in sorted(files):
            emit(f"{path.rstrip('/')}/{name}", name, "")
        for child in room_paths.children_of(path):
            if ctx.world.is_discovered(child) and ctx.world.door_visible(child):
                self._walk(ctx, out, child, start, typed, pattern)


class PsCommand(Command):
    name = "ps"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        if ctx.player.current_room == "mnt_forest":
            lines = [
                "PID  PPID  CMD",
                "  1     0  /sbin/init",
                " 42     1  \\[mount_daemon]",
                "127     1  /proc/secrets_handler",
                "...",
            ]
            if ctx.world.discover_room("proc_secrets"):
                lines += [
                    "\n[bold green]Discovered hidden process chamber: proc_secrets[/bold green]",
                    "The secrets_handler process reveals a hidden chamber...",
                    "[yellow]You can now access it with: cd proc_secrets[/yellow]",
                ]
            else:
                lines.append("\n[dim]Process chamber already discovered: proc_secrets[/dim]")
        else:
            lines = [
                "PID  PPID  CMD",
                "  1     0  /sbin/init",
                " 23     1  \\[kthreadd]",
                " 42     1  \\[ksoftirqd/0]",
            ]
        rogue = ctx.flags.rogue_process()
        if rogue is not None:
            pid, process = rogue
            lines.append(
                f"{pid:>5}     1  {process}   [bold red]← 99.9% CPU[/bold red]"
            )
        ctx.output.write("\n".join(lines))
        ctx.tutorial.after_ps()
