#!/usr/bin/env python3
"""Discovery commands: find, ps (reveal hidden rooms).

find now receives the full argument list. Under the legacy dispatcher it only
got the first token, so `find /dev -name null` silently degraded to `/dev` and
never matched — migrating to the command pattern fixes that.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base import Command

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class FindCommand(Command):
    name = "find"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        if not args:
            ctx.output.write("[yellow]Usage: find <path> -name <pattern>[/yellow]")
            return

        if len(args) >= 3 and args[1] == "-name":
            path = args[0]
            pattern = args[2]

            # /dev exists for find only once the player can see its door: a
            # locked /dev stays hidden until the Sudo Privileges Badge reveals it.
            dev_visible = (
                ctx.world.is_discovered("dev_null_void")
                and ctx.world.door_visible("dev_null_void")
            )
            if path == "/dev" and pattern == "null" and dev_visible:
                ctx.output.write("[bold green]Found: /dev/null[/bold green]")
                ctx.output.write("A mysterious void where deleted data accumulates...")
                ctx.output.write("[yellow]Go there with: [bold]cd /dev[/bold][/yellow]")
            else:
                ctx.output.write(f"[red]find: '{path}': No such file or directory[/red]")
        else:
            ctx.output.write("[yellow]Usage: find <path> -name <pattern>[/yellow]")


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
