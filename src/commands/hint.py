"""hint: escalating help toward the current room's flag."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base import Command

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class HintCommand(Command):
    name = "hint"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        ctx.flags.hint()
