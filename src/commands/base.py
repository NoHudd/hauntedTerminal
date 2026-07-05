#!/usr/bin/env python3
"""Command pattern base (rewrite Phase 3).

Each player verb becomes a small Command subclass instead of a method on the
2,400-line CommandHandler. During the strangler migration the execution context
passed to ``execute`` is the CommandHandler itself, so extracted commands can
reuse its shared helpers (item resolution, room aliases, execute_effect, event
emission) without moving everything at once.

Unlike the legacy dispatcher, ``execute`` receives the full argument list, fixing
the old bug where only the first token was passed (multi-word args were dropped).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.command_handler import CommandHandler


class Command:
    """Base class for a single player verb."""

    #: Primary verb name (e.g. "cd").
    name: str = ""
    #: Alternate names that dispatch to this same command (e.g. "inv" -> inventory).
    aliases: tuple[str, ...] = ()

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        raise NotImplementedError

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)
