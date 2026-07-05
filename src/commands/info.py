#!/usr/bin/env python3
"""Informational commands (no world mutation): help, shortcuts, pwd."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base import Command

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler

_HELP_TEXT = """
        [bold]Available Commands:[/bold]
        - [cyan]help[/cyan]: Display this help message
        - [cyan]shortcuts[/cyan]: Show item shortcuts and typing tips
        - [cyan]ls[/cyan]: List files and directories
        - [cyan]cd [directory][/cyan]: Change to specified directory
        - [cyan]pwd[/cyan]: Show current directory
        - [cyan]cat [file][/cyan]: Read the contents of a file
        - [cyan]map[/cyan]: Show available locations
        - [cyan]keys[/cyan]: Show key progression system
        - [cyan]take [item][/cyan]: Add an item to your inventory
        - [cyan]drop [item][/cyan]: Remove an item from your inventory
        - [cyan]use [item][/cyan]: Use consumables (potions, scrolls)
        - [cyan]equip [weapon][/cyan]: Equip a weapon for combat
        - [cyan]talk [npc][/cyan]: Talk to an NPC
        - [cyan]attack [enemy][/cyan]: Attack an enemy
        - [cyan]ps[/cyan]: Show running processes
        - [cyan]inventory[/cyan]: Show detailed inventory with rarities
        - [cyan]journal[/cyan]: Show story memories you've restored
        - [cyan]save[/cyan]: Save your current progress
        - [cyan]quit[/cyan] or [cyan]exit[/cyan]: Quit the game (offers to save)

        [bold]Navigation Tips:[/bold]
        - Use filesystem paths: [yellow]cd /var[/yellow], [yellow]cd /home[/yellow], [yellow]cd /bin[/yellow]
        - Or simple names: [yellow]cd var[/yellow], [yellow]cd home[/yellow], [yellow]cd bin[/yellow]
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
        ctx.output.write(
            f"Current directory: [bold]{ctx.player.current_room}[/bold]"
        )
