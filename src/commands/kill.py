"""kill: end a process by its PID (the number ps shows)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.markup import escape

from src.commands.base import Command

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class KillCommand(Command):
    name = "kill"
    SYSTEM_PIDS = {1, 23, 42, 127}

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        target = next((a for a in args if not a.startswith("-")), "")
        if not target:
            ctx.output.write(
                "[yellow]Usage: kill <PID>[/yellow]\n"
                "[dim]Run ps first: the PID column holds the numbers kill needs.[/dim]"
            )
            return
        if not target.isdigit():
            ctx.output.write(
                f"[yellow]kill: {escape(target)}: kill takes a process ID — the "
                "number in ps's PID column, not the name.[/yellow]"
            )
            return
        pid = int(target)
        rogue = ctx.flags.rogue_process()
        if rogue is not None and rogue[0] == pid:
            ctx.flags.release_rogue()
            ctx.output.write(
                f"[bold red]You send SIGTERM to {escape(rogue[1])}… it refuses to "
                "die and lashes out![/bold red]"
            )
            ctx.check_for_enemies()
            return
        if pid in self.SYSTEM_PIDS:
            ctx.output.write(
                f"[red]kill: ({pid}) - Operation not permitted[/red]\n"
                "[dim]That's a system process. Look in ps for the odd one out.[/dim]"
            )
            return
        ctx.output.write(
            f"[red]kill: ({pid}) - No such process[/red]\n"
            "[dim]ps lists the processes running here, with their PIDs.[/dim]"
        )
