#!/usr/bin/env python3
"""Informational commands (no world mutation): help, shortcuts, pwd."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base import Command

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler

_HELP_TEXT = """
        [bold]Real Unix commands[/bold] — these work the same way in any terminal.
        Type [cyan]man <command>[/cyan] to read what one actually does.
        - [cyan]ls[/cyan] / [cyan]ls -a[/cyan] / [cyan]ls -l[/cyan]: List this directory (-a shows hidden, -l shows permissions)
        - [cyan]cd <path>[/cyan]: Change directory. Try [yellow]cd /var[/yellow], [yellow]cd ..[/yellow], or [yellow]cd[/yellow] alone for home
        - [cyan]pwd[/cyan]: Print the directory you are in
        - [cyan]cat <file>[/cyan]: Read a file
        - [cyan]grep <word> <file>[/cyan]: Show only the lines of a file that contain a word
        - [cyan]tree[/cyan]: Show the filesystem you have discovered
        - [cyan]find <path> -name <x>[/cyan]: Search for a file
        - [cyan]ps[/cyan]: List running processes
        - [cyan]whoami[/cyan]: Who you currently are
        - [cyan]echo <text>[/cyan] · [cyan]clear[/cyan] · [cyan]man <command>[/cyan]

        [bold]Commands of this world:[/bold]
        - [cyan]take <item>[/cyan] / [cyan]drop <item>[/cyan]: Pick up or put down an item
        - [cyan]use <item>[/cyan]: Use a consumable
        - [cyan]equip <weapon>[/cyan]: Ready a weapon or armor
        - [cyan]examine <item>[/cyan]: Inspect something closely
        - [cyan]talk <npc>[/cyan]: Speak with a process
        - [cyan]attack <enemy>[/cyan]: Start a fight
        - [cyan]inventory[/cyan] / [cyan]inv[/cyan]: What you are carrying
        - [cyan]journal[/cyan]: Story memories you have restored
        - [cyan]hint[/cyan]: Help finding this directory's flag (ask twice for the exact command)
        - [cyan]keys[/cyan]: Key progression
        - [cyan]shortcuts[/cyan]: Item shortcuts and typing tips
        - [cyan]save[/cyan] · [cyan]quit[/cyan] / [cyan]exit[/cyan]

        [bold]Navigation:[/bold]
        - Directories are real paths: [yellow]/home[/yellow], [yellow]/var[/yellow], [yellow]/usr/games[/yellow]
        - You may cd anywhere you have permission to reach, not just next door
        - Sealed directories need a key — and you need permission on every
          directory above them too
        """

_SHORTCUTS_TEXT = """[bold cyan]Item Shortcuts & Typing Tips:[/bold cyan]

[bold]Health & Healing:[/bold]
- [yellow]hp[/yellow] or [yellow]heal[/yellow] → health_packet
- [yellow]health[/yellow] or [yellow]packet[/yellow] → health_packet
- [yellow]cache[/yellow] → stable_cache
- [yellow]buffer[/yellow] → overflowing_buffer

[bold]Weapons:[/bold]
- [yellow]shield[/yellow] → segfault_shield (Guardian)
- [yellow]pointer[/yellow] → null_pointer (Weaver)
- [yellow]whisper[/yellow] → daemon_whisper (Shaman)

[bold]Other Items:[/bold]
- [yellow]backup[/yellow] → legacy_backup
- [yellow]seed[/yellow] → sudo_seed

[bold]Partial Matching:[/bold]
You can type just the beginning of an item name:
- [yellow]health_p[/yellow] → health_packet
- [yellow]segfault[/yellow] → segfault_shield

[bold cyan]Usage Examples:[/bold cyan]
- [green]take hp[/green] (instead of take health_packet)
- [green]use heal[/green] (instead of use health_packet)
- [green]take shield[/green] (instead of take segfault_shield)"""


class HelpCommand(Command):
    name = "help"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        ctx.output.write(f"[bold]Help[/bold]\n\n{_HELP_TEXT}")


class ShortcutsCommand(Command):
    name = "shortcuts"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        ctx.output.write(_SHORTCUTS_TEXT)


class PwdCommand(Command):
    name = "pwd"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        # Print the working directory, not the room id. A real pwd emits a path,
        # and the whole point of the room tree is that those paths are real.
        from src.room_paths import room_path

        ctx.output.write(f"[bold]{room_path(ctx.player.current_room)}[/bold]")
        ctx.tutorial.after_pwd()
