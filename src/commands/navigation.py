#!/usr/bin/env python3
"""Navigation commands: ls, cd.

Bodies moved verbatim from CommandHandler (self -> ctx). ls now checks for the
-a flag anywhere in the arg list; cd resolves the destination from args[0]
(room ids/aliases are single tokens). Shared helpers stay on the handler.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

import config.dev_config as dev_cfg
from src.commands.base import Command
from src.events import EventType, event_bus
from src.room_paths import ROOM_ID_TO_PATH
from src.viewmodels.view_builder import ViewBuilder
from utils.debug_tools import debug_log

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class LsCommand(Command):
    name = "ls"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        room_id = ctx.player.current_room
        output = Text()
        has_content = False
        show_hidden = "-a" in args
        # In-game hints: inline "→ take/cat/talk/cd" affordances (Settings toggle,
        # default on). Read live so the toggle takes effect immediately.
        hints = getattr(dev_cfg, "SHOW_HINTS", True)

        has_enemies, enemy_output = ctx._check_enemies_blocking_exploration(room_id)
        if has_enemies:
            ctx.output.write(enemy_output)
            return

        items = ctx.world.get_items_in_room(room_id) or []
        weapon_found = False
        if items:
            from src.rarity import RaritySystem

            output.append("Files:\n", style="bold green")
            for item_id in items:
                item = ctx.world.get_item(item_id)
                description = ctx.get_formatted_item_description(item)
                # Color the file by rarity so value reads at a glance. Common maps
                # to white in the rarity system, which is invisible against the
                # description text, so give commons a visible green; higher tiers
                # keep their rarity color (rare=blue, legendary=yellow, unique=red).
                rarity = item.get("rarity", "common") if item else "common"
                item_color = RaritySystem.get_rarity_color(rarity)
                if item_color in ("white", "bright_white", "default"):
                    item_color = "green"
                output.append(f"  {item_id}", style=f"bold {item_color}")
                output.append(f" - {description}\n")
                if hints:
                    readable = (
                        item and item.get("type") == "lore"
                        and not item.get("takeable", True)
                    )
                    verb = "cat" if readable else "take"
                    output.append(f"     → {verb} {item_id}\n", style="dim cyan")

                if item and item.get("type") == "weapon":
                    weapon_found = True

            has_content = True

        npcs = ctx.world.get_npcs_in_room(room_id) or []
        if npcs:
            if has_content:
                output.append("\n")
            output.append("Processes:\n", style="bold yellow")
            for npc_id in npcs:
                npc = ctx.world.get_npc(npc_id)
                if npc:
                    description = (
                        npc.get("short_description")
                        or npc.get("description")
                        or npc.get("name")
                        or "No description available"
                    )
                    output.append(f"  {npc_id}", style="yellow")
                    output.append(f" - {description}\n")
                    if hints:
                        output.append(f"     → talk {npc_id}\n", style="dim cyan")
            has_content = True

        enemies = ctx.world.get_enemies_in_room(room_id) or []
        if enemies:
            if has_content:
                output.append("\n")
            output.append("Corrupted Entities:\n", style="bold red")
            for enemy_id in enemies:
                enemy = ctx.world.get_enemy(enemy_id, ctx.player.player_class)
                if enemy:
                    name = enemy.get("name", enemy_id)
                    health = enemy.get("health", "??")
                    damage = enemy.get("damage", "??")
                    output.append(f"  {enemy_id}", style="red")
                    output.append(f" - {name} (HP: {health}, DMG: {damage})\n")
                else:
                    output.append(f"  {enemy_id} - Unknown Enemy\n", style="red")
            has_content = True

        if show_hidden:
            hidden_rooms = ctx._get_discoverable_hidden_rooms(room_id)
            if hidden_rooms:
                if has_content:
                    output.append("\n")
                output.append(
                    "Hidden Directories (discoverable):\n", style="bold yellow"
                )
                for hidden_room_id, hint in hidden_rooms.items():
                    output.append(f"  .{hidden_room_id}", style="dim yellow")
                    output.append(f" - {hint}\n", style="dim")
                has_content = True

                for hidden_room_id in hidden_rooms:
                    if ctx.world.discover_room(hidden_room_id):
                        output.append(
                            f"\n[bold green]Discovered hidden directory: "
                            f"{hidden_room_id}![/bold green]\n"
                        )

        # Where you can go: actionable exit list (fills the screen with the one
        # thing a novice most needs — how to leave). Hints-gated.
        if hints:
            exits = ctx.world.get_exits(room_id) or []
            if exits:
                if has_content:
                    output.append("\n")
                output.append("Where you can go:\n", style="bold cyan")
                for exit_room in exits:
                    # Show the filesystem path (cd /var) — matches the exits strip
                    # and teaches real path navigation. Falls back to the room id.
                    path = ROOM_ID_TO_PATH.get(exit_room, exit_room)
                    output.append(f"  → cd {path}\n", style="dim cyan")
                has_content = True

        if not has_content:
            output.append("No files, processes, or entities found.")

        ctx.output.write(output)

        ts = ctx.player.tutorial_state
        if not ts.get("completed", False):
            if not ts.get("first_ls", False):
                ts["first_ls"] = True
                if weapon_found:
                    ts["found_weapon"] = True
                    weapon_item_id = None
                    for item_id in items:
                        item = ctx.world.get_item(item_id)
                        if item and item.get("type") == "weapon":
                            weapon_item_id = item_id
                            break
                    ctx.show_tutorial_hint("step2", weapon_item_id)
            elif ts.get("combat_typed", False) and not ts.get("navigation_ls", False):
                ts["navigation_ls"] = True
                ctx.show_tutorial_hint("step6b")


class CdCommand(Command):
    name = "cd"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        directory = args[0] if args else ""
        if not directory:
            debug_log("cd called with no directory specified")
            ctx.output.write(
                f"Current directory: [bold]{ctx.player.current_room}[/bold]"
            )
            return

        original_directory = directory
        if directory.lower() in ctx.room_aliases:
            directory = ctx.room_aliases[directory.lower()]
            debug_log(f"Resolved alias '{original_directory}' to '{directory}'")

        current_room = ctx.player.current_room
        debug_log(f"Player attempting to move from {current_room} to {directory}")

        can_move, reason = ctx.world.can_move_to(current_room, directory)
        debug_log(f"Can move to {directory}: {can_move}, reason: {reason}")

        room_state = ctx.world.get_room_state(directory)
        if room_state.get("hidden", False):
            # A key that explicitly unlocks this room also REVEALS it — otherwise
            # a keyed player is told the path doesn't exist (mage with opt_key
            # locked out of the mage tower).
            key_required = room_state.get("key_required")
            key_item = (
                ctx.player.get_item_from_inventory(key_required)
                if key_required and ctx.player.has_item(key_required)
                else None
            )
            resolved_unlocks = [
                ctx.room_aliases.get(r.lower(), r)
                for r in (key_item or {}).get("unlocks", [])
            ]
            if key_item and directory in resolved_unlocks:
                debug_log(f"Hidden room {directory} revealed by key {key_required}")
                ctx.world.discover_room(directory)
                key_name = key_item.get("name", key_required)
                ctx.output.write(
                    f"[yellow]✨ The {key_name} resonates — a hidden path to "
                    f"{directory} reveals itself.[/yellow]"
                )
                can_move, reason = ctx.world.can_move_to(current_room, directory)
            else:
                debug_log(f"Attempt to access hidden room {directory} - access denied")
                hint_message = ctx._get_hidden_room_hint(directory)
                ctx._show_error("[bold red]That path doesn't appear to exist.[/bold red]")
                if hint_message:
                    ctx.output.write(f"[dim yellow]{hint_message}[/dim yellow]")
                return

        if not can_move and "locked" in reason.lower():
            room_state = ctx.world.get_room_state(directory)
            key_required = room_state.get("key_required")
            debug_log(f"Room {directory} is locked, key required: {key_required}")

            if key_required and ctx.player.has_item(key_required):
                debug_log(f"Player has the required key: {key_required}")
                key_item = ctx.player.get_item_from_inventory(key_required)

                resolved_unlocks = [
                    ctx.room_aliases.get(r.lower(), r)
                    for r in key_item.get("unlocks", [])
                ]
                if "unlocks" in key_item and directory in resolved_unlocks:
                    debug_log(f"Using key {key_required} to unlock {directory} (new format)")
                    ctx.world.unlock_room(directory)
                    ctx.output.write(
                        f"[yellow]You automatically use {key_required} to unlock "
                        f"{directory}.[/yellow]"
                    )
                    can_move = True
                    reason = None
                elif key_item.get("usable", False):
                    debug_log(f"Using key {key_required} to unlock {directory} (old format)")
                    ctx.world.unlock_room(directory)
                    ctx.output.write(
                        f"[yellow]You automatically use {key_required} to unlock "
                        f"{directory}.[/yellow]"
                    )
                    can_move = True
                    reason = None

        if not can_move:
            debug_log(f"Movement denied: {reason}")
            ctx._show_error(f"[bold red]{reason}[/bold red]")

            if "locked" in reason.lower():
                room_state = ctx.world.get_room_state(directory)
                key_required = room_state.get("key_required") if room_state else None
                class_restriction = (
                    room_state.get("class_restriction") if room_state else None
                )

                if key_required:
                    ctx.output.write(
                        f"[yellow]💡 Hint: This area requires '{key_required}' to "
                        "unlock.[/yellow]"
                    )
                if class_restriction:
                    ctx.output.write(
                        f"[cyan]⚔ Class Restriction: Only {class_restriction}s can "
                        "enter this area.[/cyan]"
                    )
            return

        debug_log(f"Moving player from {current_room} to {directory}")
        ctx.player.move_to(directory)

        new_room = ctx.world.get_room(directory)
        room_name = new_room.name if new_room else directory
        ctx.output.write(f"[bold cyan]Entering {room_name}...[/bold cyan]")
        debug_log(f"Successfully moved player to {directory}")

        room_view = ViewBuilder.build_room_view(ctx.world, directory)
        event_bus.emit_event(
            EventType.ROOM_ENTERED,
            {"room": room_view.to_dict(), "player_name": ctx.player.name},
            "CommandHandler",
        )

        ctx.display_location()

        ts = ctx.player.tutorial_state
        if not ts.get("completed", False) and ts.get("navigation_ls", False):
            if not ts.get("navigation_moved", False):
                ts["navigation_moved"] = True
                ctx.show_tutorial_hint("completed")
