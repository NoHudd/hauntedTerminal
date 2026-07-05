#!/usr/bin/env python3
"""Command registry (rewrite Phase 3).

Verbs are migrated out of CommandHandler into Command subclasses incrementally.
build_registry() returns the migrated verbs keyed by name and alias; the handler
checks this registry before its legacy method dispatch, so un-migrated verbs keep
working unchanged.
"""
from __future__ import annotations

from src.commands.actions import AttackCommand, UseCommand
from src.commands.base import Command
from src.commands.discovery import FindCommand, PsCommand
from src.commands.display import (
    InventoryCommand,
    JournalCommand,
    KeysCommand,
    MapCommand,
)
from src.commands.info import HelpCommand, PwdCommand, ShortcutsCommand
from src.commands.navigation import CdCommand, LsCommand
from src.commands.items import (
    CatCommand,
    DropCommand,
    EquipCommand,
    ExamineCommand,
    TakeCommand,
    TalkCommand,
)
from src.commands.system import QuitCommand, SaveCommand

#: Command classes that have been migrated off CommandHandler. Add to this list
#: as each verb is extracted.
MIGRATED: tuple[type[Command], ...] = (
    HelpCommand,
    ShortcutsCommand,
    PwdCommand,
    JournalCommand,
    InventoryCommand,
    KeysCommand,
    MapCommand,
    FindCommand,
    PsCommand,
    SaveCommand,
    QuitCommand,
    DropCommand,
    EquipCommand,
    ExamineCommand,
    TalkCommand,
    TakeCommand,
    CatCommand,
    LsCommand,
    CdCommand,
    UseCommand,
    AttackCommand,
)


def build_registry() -> dict[str, Command]:
    """Map every migrated verb name/alias to a shared Command instance."""
    registry: dict[str, Command] = {}
    for command_cls in MIGRATED:
        instance = command_cls()
        for name in instance.names:
            if name in registry:
                raise ValueError(f"duplicate command name: {name}")
            registry[name] = instance
    return registry


__all__ = ["Command", "build_registry", "MIGRATED"]
