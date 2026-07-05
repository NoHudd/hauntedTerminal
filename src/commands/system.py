#!/usr/bin/env python3
"""System commands: save, quit/exit.

quit sets confirmation state handled by CommandHandler's mode-gate helpers
(_handle_quit_confirmation / _perform_quit), which remain on the handler. The
quit-confirmation flow re-invokes the save command through the registry.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base import Command
from utils.debug_tools import debug_log

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class SaveCommand(Command):
    name = "save"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        try:
            from src.save import save_manager

            world_state = ctx.world.get_state()
            save_path = save_manager.save_game(ctx.player, world_state)

            ctx.output.write("[bold green]✓ Game saved successfully![/bold green]")
            ctx.output.write(f"[dim]Save location: {save_path}[/dim]")
            debug_log(f"Game saved to: {save_path}")
        except Exception as e:
            debug_log(f"Failed to save game: {e}")
            ctx.output.write(f"[bold red]✗ Failed to save game: {e}[/bold red]")


class QuitCommand(Command):
    name = "quit"
    aliases = ("exit",)

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        has_progress = (
            ctx.player.health != ctx.player.max_health
            or ctx.player.current_room != "home_grove"
            or len(ctx.player.inventory) > 0
            or ctx.player.equipped_weapon is not None
        )

        if has_progress:
            ctx.output.write("[bold yellow]You have unsaved progress![/bold yellow]")
            ctx.output.write("Would you like to save before quitting?")
            ctx.output.write(
                "[bold white]Options:[/bold white] [green]y[/green] (save & quit), "
                "[yellow]n[/yellow] (quit without saving), [red]c[/red] (cancel)"
            )
            ctx._in_quit_confirmation = True
        else:
            ctx._perform_quit()
