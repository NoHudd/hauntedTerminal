#!/usr/bin/env python3
"""Item/NPC interaction commands: drop, equip, examine, talk.

Each takes a single identifier token (item/npc id). To preserve the original
behaviour these read args[0]; item ids are single tokens, so nothing is lost.
Bodies moved verbatim from CommandHandler (self -> ctx); shared helpers
(_show_error, execute_effect, _get_class_restriction_text, _show_damage_change,
show_tutorial_hint, check_for_enemies) remain on the handler.
"""
from __future__ import annotations

import random
from src import rng
from typing import TYPE_CHECKING

from src.commands.base import Command
from src.events import EventType, event_bus
from src.ui.view_builder import ViewBuilder
from utils.debug_tools import debug_log
from utils.typewriter import TypewriterPresets, create_typewriter_output_func

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


def _first(args: list[str]) -> str:
    return args[0] if args else ""


class TakeCommand(Command):
    name = "take"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        item_id = _first(args)
        if not item_id:
            debug_log("take command called with no item specified")
            ctx._show_error("[bold red]No item specified. Use 'take [item]'[/bold red]")
            return

        current_room = ctx.player.current_room

        has_enemies, enemy_output = ctx._check_enemies_blocking_exploration(current_room)
        if has_enemies:
            ctx.output.write(enemy_output)
            return

        actual_item_id = ctx._resolve_item_shortcut(item_id, "room")
        if not actual_item_id:
            debug_log(f"Item {item_id} not found in room after shortcut resolution")
            ctx._show_error(
                f"[bold red]Cannot find {item_id} in this directory.[/bold red]"
            )
            return

        debug_log(
            f"Player attempting to take item: {actual_item_id} (from input: {item_id})"
        )
        items_in_room = ctx.world.get_items_in_room(current_room)

        if actual_item_id not in items_in_room:
            debug_log(f"Item {actual_item_id} not found in room {current_room}")
            ctx._show_error(
                f"[bold red]Cannot find {item_id} in this directory.[/bold red]"
            )
            return

        item = ctx.world.get_item(actual_item_id)
        if not item:
            debug_log(f"Error: Item data not found for {actual_item_id}")
            ctx._show_error(
                f"[bold red]Error: Item data not found for {item_id}[/bold red]"
            )
            return

        if not item.get("takeable", True):
            debug_log(f"Item {actual_item_id} is not takeable")
            ctx._show_error(f"[bold red]You cannot take {item_id}.[/bold red]")
            return

        if not ctx.player.can_use_item(item):
            class_restriction = ctx._get_class_restriction_text(item)
            debug_log(
                f"Item {actual_item_id} is class-restricted, player class "
                f"{ctx.player.player_class} not allowed"
            )
            ctx._show_error(
                f"[bold red]Only {class_restriction} spirits can wield {item_id}. "
                "Your essence is incompatible.[/bold red]"
            )
            return

        success = ctx.player.add_to_inventory(actual_item_id, item)
        if success:
            debug_log(f"Player took item {actual_item_id} from room {current_room}")
            ctx.world.remove_item_from_room(actual_item_id)

            from src.rarity import RaritySystem

            item_name = item.get("name", actual_item_id)
            rarity = item.get("rarity", "common")
            formatted_name = RaritySystem.format_item_name_with_rarity(
                item_name, rarity, show_emoji=False
            )
            ctx.output.write(f"Added {formatted_name} to your inventory.")

            inventory_view = ViewBuilder.build_inventory_view(ctx.player)
            event_bus.emit_event(
                EventType.PLAYER_INVENTORY_CHANGED,
                inventory_view.to_dict(),
                "CommandHandler",
            )

            if "on_take" in item:
                debug_log(f"Executing on_take effect for {item_id}")
                ctx.execute_effect(item["on_take"])

            if (
                not ctx.player.tutorial_state.get("took_weapon", False)
                and item.get("type") == "weapon"
            ):
                ctx.player.tutorial_state["took_weapon"] = True
                ctx.show_tutorial_hint("step3", actual_item_id)
        else:
            debug_log(f"Failed to add {actual_item_id} to inventory")
            ctx._show_error(
                f"[bold red]Could not add {item_id} to inventory.[/bold red]"
            )


class CatCommand(Command):
    name = "cat"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        filename = _first(args)
        if not filename:
            ctx._show_error("[bold red]No file specified. Use 'cat [filename]'[/bold red]")
            return

        current_room = ctx.player.current_room
        items_in_room = ctx.world.get_items_in_room(current_room)

        item_id = ctx._find_item_by_name_or_id(filename, items_in_room)

        if item_id:
            item = ctx.world.get_item(item_id)
            if item:
                self._render(ctx, item, item_id)
            else:
                ctx._show_error(f"[bold red]Error: Could not read {filename}[/bold red]")
        elif ctx.player.has_item(filename) or ctx._find_item_in_inventory_by_name(filename):
            item_id_inv = ctx._find_item_in_inventory_by_name(filename) or filename
            item = ctx.player.get_item_from_inventory(item_id_inv)
            if item:
                self._render(ctx, item, item_id_inv)
            else:
                ctx._show_error(f"[bold red]Error: Could not read {filename}[/bold red]")
        else:
            ctx._show_error(
                f"[bold red]Cannot find {filename} in this directory or your "
                "inventory.[/bold red]"
            )

    @staticmethod
    def _render(ctx: "CommandHandler", item: dict, item_id: str) -> None:
        item_name = item.get("name", item_id)
        content = item.get(
            "content",
            item.get("description", "This file appears to be empty or corrupted."),
        )
        ctx.output.write(f"[bold]{item_name}[/bold]\n\n{content}")
        if "on_read" in item:
            ctx.execute_effect(item["on_read"])
        ctx._trigger_story_flag(item)


class DropCommand(Command):
    name = "drop"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        item_id = _first(args)
        if not item_id:
            ctx._show_error("[bold red]No item specified. Use 'drop [item]'[/bold red]")
            return

        if not ctx.player.has_item(item_id):
            ctx._show_error(
                f"[bold red]You don't have {item_id} in your inventory.[/bold red]"
            )
            return

        item = ctx.player.get_item_from_inventory(item_id)

        if item.get("droppable", True) == False:  # noqa: E712 (preserve original)
            ctx._show_error(
                f"[bold red]You cannot drop {item_id}. It's too important.[/bold red]"
            )
            return

        success = ctx.player.remove_from_inventory(item_id)
        if success:
            current_room = ctx.player.current_room
            ctx.world.add_item_to_room(item_id, current_room)
            ctx.output.write(
                f"Dropped [green]{item_id}[/green] in the current directory."
            )
            if "on_drop" in item:
                ctx.execute_effect(item["on_drop"])
        else:
            ctx._show_error(f"[bold red]Could not drop {item_id}.[/bold red]")


class ExamineCommand(Command):
    name = "examine"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        item_id = _first(args)
        if not item_id:
            ctx._show_error("[bold red]No item specified. Use 'examine [item]'[/bold red]")
            return

        if ctx.player.has_item(item_id):
            item = ctx.player.get_item_from_inventory(item_id)
        else:
            current_room = ctx.player.current_room
            items_in_room = ctx.world.get_items_in_room(current_room)
            if item_id in items_in_room:
                item = ctx.world.get_item(item_id)
            else:
                ctx._show_error(
                    f"[bold red]Cannot find {item_id} in this directory or your "
                    "inventory.[/bold red]"
                )
                return

        from src.rarity import RaritySystem

        item_name = item.get("name", item_id)
        rarity = item.get("rarity", "common")
        formatted_name = RaritySystem.format_item_name_with_rarity(
            item_name, rarity, show_emoji=False
        )

        title = f"Examining: {formatted_name}"
        description = item.get("description", "No detailed description available.")

        details = []
        color = RaritySystem.get_rarity_color(rarity)
        details.append(f"[bold]Rarity:[/bold] [{color}]{rarity.title()}[/{color}]")

        item_type = item.get("type", "unknown")
        details.append(f"[bold]Type:[/bold] {item_type.title()}")

        if item_type == "weapon":
            damage = item.get("damage", 0)
            if damage > 0:
                details.append(f"[bold]Damage:[/bold] {damage}")
        elif item_type == "consumable":
            healing = item.get("healing", 0)
            if healing > 0:
                details.append(f"[bold]Healing:[/bold] {healing} HP")

        if item.get("usable", False):
            details.append("[green]This item can be used.[/green]")
        if item.get("consumed_on_use", False) or item.get("consumable", False):
            details.append("[yellow]This item will be consumed when used.[/yellow]")
        if not item.get("takeable", True):
            details.append("[red]This item cannot be taken.[/red]")
        if not item.get("droppable", True):
            details.append("[red]This item cannot be dropped once taken.[/red]")

        if "class_restriction" in item:
            allowed_classes = item["class_restriction"]
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            details.append(
                f"[bold]Class Restriction:[/bold] {', '.join(allowed_classes).title()}"
            )
        elif "allowed_classes" in item:
            allowed_classes = item["allowed_classes"]
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            details.append(
                f"[bold]Allowed Classes:[/bold] {', '.join(allowed_classes).title()}"
            )

        content = f"{description}\n"
        if details:
            content += "\n" + "\n".join(details)

        ctx.output.write(f"[bold cyan]── {title} ──[/bold cyan]\n{content}")

        if "on_examine" in item:
            ctx.execute_effect(item["on_examine"])


class TalkCommand(Command):
    name = "talk"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        npc_id = _first(args)
        if not npc_id:
            ctx._show_error("[bold red]No NPC specified. Use 'talk [npc]'[/bold red]")
            return

        current_room = ctx.player.current_room
        npcs_in_room = ctx.world.get_npcs_in_room(current_room)

        if npc_id not in npcs_in_room:
            ctx._show_error(
                f"[bold red]Cannot find {npc_id} in this directory.[/bold red]"
            )
            return

        npc = ctx.world.get_npc(npc_id)
        if not npc:
            ctx._show_error(
                f"[bold red]Error: NPC data not found for {npc_id}[/bold red]"
            )
            return

        npc_name = npc.get("name", npc_id)

        dialogues = npc.get("dialogues", [])
        if not dialogues:
            ctx.output.write(
                f"[bold cyan]🗨️  {npc_name}[/bold cyan]\n"
                f'[italic dim]"..."[/italic dim]\n'
                f"[dim]({npc_name} has nothing to say right now.)[/dim]"
            )
            return

        dialogue = rng.choice(dialogues)
        dialogue_text = (
            f"[bold cyan]🗨️  {npc_name}[/bold cyan]\n"
            f'[italic yellow]"{dialogue}"[/italic yellow]'
        )

        output_callback = create_typewriter_output_func(
            lambda text: ctx.output.write(text)
        )

        try:
            TypewriterPresets.DIALOGUE.type_text_sync(dialogue_text, output_callback)
            ctx.output.write(dialogue_text)
        except Exception as e:
            debug_log(f"Typewriter effect failed for NPC {npc_id}: {e}")
            ctx.output.write(dialogue_text)

        if "on_talk" in npc:
            ctx.execute_effect(npc["on_talk"])


class EquipCommand(Command):
    name = "equip"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        weapon_id = _first(args)
        if not weapon_id:
            debug_log("equip command called with no weapon specified")
            ctx.output.write(
                "[bold red]No weapon specified. Use 'equip [weapon]'[/bold red]"
            )
            return

        original_input = weapon_id
        resolved = ctx.player.resolve_inventory_item(weapon_id)
        if resolved:
            weapon_id = resolved

        debug_log(
            f"Player attempting to equip weapon: {weapon_id} (from input: {original_input})"
        )

        if not ctx.player.has_item(weapon_id):
            debug_log(f"Player doesn't have weapon {original_input} in inventory")
            ctx.output.write(
                f"[bold red]You don't have {original_input} in your inventory.[/bold red]"
            )
            return

        weapon = ctx.player.get_item_from_inventory(weapon_id)
        weapon_type = weapon.get("type")

        is_weapon = (
            weapon_type == "weapon" or "weapon" in str(weapon_type)
            if weapon_type
            else False
        )
        if not is_weapon:
            debug_log(f"Item {weapon_id} is not a weapon")
            ctx.output.write(f"[bold red]{weapon_id} is not a weapon.[/bold red]")
            return

        if not ctx.player.can_use_item(weapon):
            class_restriction = ctx._get_class_restriction_text(weapon)
            debug_log(
                f"Weapon {weapon_id} has class restriction: {class_restriction}, "
                f"player is: {ctx.player.player_class}"
            )
            ctx.output.write(
                f"[bold red]This weapon can only be used by {class_restriction} "
                "class.[/bold red]"
            )
            return

        old_damage = ctx.player.calculate_damage()

        success = ctx.player.equip_weapon(weapon_id)
        if success:
            weapon_name = weapon.get("name", weapon_id)
            ctx.output.write(f"You have equipped [green]{weapon_name}[/green].")
            ctx._show_damage_change(old_damage, ctx.player.calculate_damage())

            if not ctx.player.tutorial_state.get("equipped_weapon", False):
                ctx.player.tutorial_state["equipped_weapon"] = True
                ctx.world.spawn_tutorial_enemy("home_grove")
                ctx.show_tutorial_hint("step4")
                ctx.check_for_enemies()

            stats_view = ViewBuilder.build_stats_view(ctx.player)
            event_bus.emit_event(
                EventType.PLAYER_STATS_CHANGED,
                stats_view.to_dict(),
                "CommandHandler",
            )
        else:
            debug_log(f"Failed to equip weapon {weapon_id}")
            ctx.output.write(f"[bold red]Failed to equip {weapon_id}.[/bold red]")
