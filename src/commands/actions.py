#!/usr/bin/env python3
"""Action commands: use (consume/apply an item), attack (start combat).

use fans out to the handler's _handle_* sub-handlers, and attack delegates to
start_combat; those stay on CommandHandler. Bodies moved verbatim (self -> ctx).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base import Command
from utils.debug_tools import debug_log

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class UseCommand(Command):
    name = "use"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        item_id = args[0] if args else ""
        if not item_id:
            debug_log("use command called with no item specified")
            ctx._show_error("[bold red]No item specified. Use 'use [item]'[/bold red]")
            return

        actual_item_id = ctx._resolve_item_shortcut(item_id, "inventory")
        if not actual_item_id:
            debug_log(f"Item {item_id} not found in inventory after shortcut resolution")
            ctx._show_error(
                f"[bold red]You don't have {item_id} in your inventory.[/bold red]"
            )
            return

        debug_log(f"Player attempting to use item: {actual_item_id} (from input: {item_id})")

        if not ctx.player.has_item(actual_item_id):
            debug_log(f"Player doesn't have item {actual_item_id} in inventory")
            ctx._show_error(
                f"[bold red]You don't have {item_id} in your inventory.[/bold red]"
            )
            return

        item = ctx.player.get_item_from_inventory(actual_item_id)
        item_type = item.get("type")
        debug_log(f"Using item {actual_item_id} of type {item_type}")

        is_weapon = (
            item_type == "weapon" or "weapon" in str(item_type) if item_type else False
        )
        if is_weapon:
            debug_log(f"Item {actual_item_id} is a weapon, should be equipped instead of used")
            ctx.output.write(
                f"[bold yellow]{item_id} is a weapon. Use 'equip {item_id}' to "
                "equip it.[/bold yellow]"
            )
            return

        if not item.get("usable", False):
            debug_log(f"Item {actual_item_id} is not usable")
            ctx._show_error(f"[bold red]You cannot use {item_id}.[/bold red]")
            return

        if not ctx.player.can_use_item(item):
            class_restriction = ctx._get_class_restriction_text(item)
            debug_log(
                f"Item {actual_item_id} has class restriction: {class_restriction}, "
                f"player is: {ctx.player.player_class}"
            )
            ctx._show_error(
                f"[bold red]This item can only be used by {class_restriction} "
                "class.[/bold red]"
            )
            return

        if item_type == "key":
            debug_log(f"Handling key item: {actual_item_id}")
            ctx._handle_key_item(actual_item_id, item)
        elif item_type == "lore":
            debug_log(f"Handling lore item: {actual_item_id}")
            ctx._handle_lore_item(actual_item_id, item)
        elif item_type == "consumable" or "heal" in item.get("on_use", {}):
            debug_log(f"Handling consumable item: {actual_item_id}")
            if ctx._handle_consumable_item(actual_item_id, item) is False:
                return  # Item had no effect — don't consume it
        elif "upgrade" in item_type if item_type else False:
            debug_log(f"Handling upgrade item: {actual_item_id}")
            ctx._handle_upgrade_item(actual_item_id, item)
        elif "spell" in item_type if item_type else False:
            debug_log(f"Handling spell item: {actual_item_id}")
            ctx._handle_spell_item(actual_item_id, item)
        else:
            if "on_use" in item:
                debug_log(f"Executing generic on_use effect for item: {actual_item_id}")
                ctx.execute_effect(item["on_use"])
                item_name = item.get("name", item_id)
                ctx.output.write(f"You used [green]{item_name}[/green].")
            else:
                debug_log(f"Item {actual_item_id} has no on_use effect")
                ctx.output.write(f"Nothing happens when you try to use {item_id}.")

        if item.get("consumed_on_use", False):
            debug_log(f"Item {actual_item_id} was consumed on use")
            ctx.player.remove_from_inventory(actual_item_id)
            item_name = item.get("name", item_id)
            ctx.output.write(f"The [green]{item_name}[/green] was consumed.")


class AttackCommand(Command):
    name = "attack"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        enemy_id = args[0] if args else ""
        current_room = ctx.player.current_room
        enemies_in_room = ctx.world.get_enemies_in_room(current_room) or []

        if not enemy_id:
            if not enemies_in_room:
                ctx._show_error("[bold red]Nothing to attack here.[/bold red]")
                return
            enemy_id = enemies_in_room[0]

        if enemy_id not in enemies_in_room:
            ctx._show_error(
                f"[bold red]Cannot find {enemy_id} in this directory.[/bold red]"
            )
            return

        enemy = ctx.world.get_enemy(enemy_id, ctx.player.player_class)
        if not enemy:
            ctx._show_error(
                f"[bold red]Error: Enemy data not found for {enemy_id}[/bold red]"
            )
            return

        ctx.start_combat([(enemy_id, enemy)])
