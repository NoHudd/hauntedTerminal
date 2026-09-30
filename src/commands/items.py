#!/usr/bin/env python3
"""Item/NPC interaction commands: drop, equip, examine, talk.

Item commands read the whole argument ("health packet" is one name) and
resolve it spelling-blind through ctx.resolver / Player.resolve_inventory_item;
talk still reads a single npc-id token.
Item behaviour comes from ctx.effects, lookups from ctx.resolver and hints
from ctx.tutorial; starting a fight is still the handler's check_for_enemies.
"""
from __future__ import annotations

from src import rng
from typing import TYPE_CHECKING

from src.commands.base import Command
from src.commands.hints import inventory_names, show_not_found, visible_room_items
from src.item_effects import class_restriction_text
from src.item_icons import item_icon
from utils.debug_tools import debug_log

if TYPE_CHECKING:  # pragma: no cover
    from engine.schema import Item
    from src.command_handler import CommandHandler


def _first(args: list[str]) -> str:
    return args[0] if args else ""


def _name(args: list[str]) -> str:
    """The whole argument as one item name: `take health packet`."""
    return " ".join(args)


def _tutorial_gear_equipped(ctx: "CommandHandler", kind: str) -> None:
    """Tutorial only: once the first weapon AND first armor are on, the scripted
    fight opens. A player who skipped (completed=True) is never ambushed."""
    if ctx.tutorial.gear_equipped(kind):
        ctx.world.spawn_tutorial_enemy("home_grove")
        # After the fight opens, so the hint lands in the combat log instead of
        # being replaced by it.
        ctx.check_for_enemies()
        ctx.tutorial.show_hint("step4")


class TakeCommand(Command):
    name = "take"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        item_id = _name(args)
        if not item_id:
            debug_log("take command called with no item specified")
            ctx.output.error("[bold red]No item specified. Use 'take <item>'[/bold red]")
            return

        current_room = ctx.player.current_room

        has_enemies, enemy_output = ctx.check_enemies_blocking_exploration(current_room)
        if has_enemies:
            ctx.output.write(enemy_output)
            return

        actual_item_id = ctx.resolver.resolve_shortcut(item_id, "room")
        if not actual_item_id:
            debug_log(f"Item {item_id} not found in room after shortcut resolution")
            show_not_found(
                ctx,
                f"[bold red]Cannot find {item_id} in this directory.[/bold red]",
                item_id,
                visible_room_items(ctx, current_room),
                label="Items here",
            )
            return

        debug_log(
            f"Player attempting to take item: {actual_item_id} (from input: {item_id})"
        )
        items_in_room = ctx.world.get_items_in_room(current_room)

        if actual_item_id not in items_in_room:
            debug_log(f"Item {actual_item_id} not found in room {current_room}")
            show_not_found(
                ctx,
                f"[bold red]Cannot find {item_id} in this directory.[/bold red]",
                item_id,
                visible_room_items(ctx, current_room),
                label="Items here",
            )
            return

        item = ctx.world.get_item(actual_item_id)
        if not item:
            debug_log(f"Error: Item data not found for {actual_item_id}")
            ctx.output.error(
                f"[bold red]Error: Item data not found for {item_id}[/bold red]"
            )
            return

        if not item.takeable:
            debug_log(f"Item {actual_item_id} is not takeable")
            ctx.output.error(f"[bold red]You cannot take {item_id}.[/bold red]")
            return

        if not ctx.player.can_use_item(item):
            class_restriction = class_restriction_text(item)
            debug_log(
                f"Item {actual_item_id} is class-restricted, player class "
                f"{ctx.player.player_class} not allowed"
            )
            ctx.output.error(
                f"[bold red]Only {class_restriction} spirits can wield {item_id}. "
                "Your essence is incompatible.[/bold red]"
            )
            return

        success = ctx.player.add_to_inventory(actual_item_id, item)
        if success:
            debug_log(f"Player took item {actual_item_id} from room {current_room}")
            ctx.world.remove_item_from_room(actual_item_id)
            ctx.player.run_stats["items_found"] = ctx.player.run_stats.get("items_found", 0) + 1
            take_flag = item.story_flag
            if take_flag:
                ctx.player.set_story_flag(take_flag)

            from src.rarity import RaritySystem

            item_name = item.name
            rarity = item.rarity
            formatted_name = RaritySystem.format_item_name_with_rarity(
                item_name, rarity, show_emoji=False
            )
            ctx.output.write(f"Added {item_icon(item.type)} {formatted_name} to your inventory.")

            if item.on_take is not None:
                debug_log(f"Executing on_take effect for {item_id}")
                ctx.effects.execute_effect(item.on_take)

            # Reprint room contents so the player sees the item is gone without
            # having to retype `ls`.
            ctx.relist_room()

            if (
                not ctx.player.tutorial_state.get("took_weapon", False)
                and item.type == "weapon"
            ):
                ctx.player.tutorial_state["took_weapon"] = True
                ctx.tutorial.show_hint("step3", actual_item_id)
        else:
            debug_log(f"Failed to add {actual_item_id} to inventory")
            ctx.output.error(
                f"[bold red]Could not add {item_id} to inventory.[/bold red]"
            )


class CatCommand(Command):
    name = "cat"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        filename = _name(args)
        if not filename:
            ctx.output.error("[bold red]No file specified. Use 'cat <filename>'[/bold red]")
            return

        current_room = ctx.player.current_room
        items_in_room = ctx.world.get_items_in_room(current_room)

        item_id = ctx.resolver.find_in_list(filename, items_in_room)

        if item_id:
            item = ctx.world.get_item(item_id)
            if item:
                self._render(ctx, item, item_id)
                # No room re-list after cat: the scene view already shows who is
                # here and the exits, and appending the full listing under the
                # file text read as a glitchy wall. `ls` re-lists on demand.
            else:
                ctx.output.error(f"[bold red]Error: Could not read {filename}[/bold red]")
        elif ctx.player.has_item(filename) or ctx.resolver.find_in_inventory(filename):
            item_id_inv = ctx.resolver.find_in_inventory(filename) or filename
            item = ctx.player.get_item_from_inventory(item_id_inv)
            if item:
                self._render(ctx, item, item_id_inv)
            else:
                ctx.output.error(f"[bold red]Error: Could not read {filename}[/bold red]")
        else:
            show_not_found(
                ctx,
                f"[bold red]Cannot find {filename} in this directory or your "
                "inventory.[/bold red]",
                filename,
                [*visible_room_items(ctx, ctx.player.current_room),
                 *inventory_names(ctx.player)],
                label="Files here",
            )

    @staticmethod
    def _render(ctx: "CommandHandler", item: "Item", item_id: str) -> bool:
        """Print the file; run on_read + story flag. Returns True if a story beat fired."""
        item_name = item.name
        content = (
            item.content
            or item.description
            or "This file appears to be empty or corrupted."
        )
        ctx.output.write(f"[bold]{item_name}[/bold]\n\n{content}")
        if item.on_read is not None:
            ctx.effects.execute_effect(item.on_read)
        # Capture before the story beat: its autosave must include the flag.
        captured = ctx.flags.on_file_read(item_id, save=False)
        story_beat = ctx.effects.trigger_story_flag(item)
        if captured and not story_beat:
            ctx.flags.checkpoint()
        ctx.tutorial.after_lore_read(story_beat)
        return story_beat


class DropCommand(Command):
    name = "drop"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        item_id = _name(args)
        if not item_id:
            ctx.output.error("[bold red]No item specified. Use 'drop <item>'[/bold red]")
            return

        item_id = ctx.player.resolve_inventory_item(item_id) or item_id
        if not ctx.player.has_item(item_id):
            show_not_found(
                ctx,
                f"[bold red]You don't have {item_id} in your inventory.[/bold red]",
                item_id,
                inventory_names(ctx.player),
                label="Inventory",
            )
            return

        item = ctx.player.get_item_from_inventory(item_id)

        if not item.droppable:
            ctx.output.error(
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
            if item.on_drop is not None:
                ctx.effects.execute_effect(item.on_drop)
            # Reprint room contents so the dropped item shows up without `ls`.
            ctx.relist_room()
        else:
            ctx.output.error(f"[bold red]Could not drop {item_id}.[/bold red]")


class ExamineCommand(Command):
    name = "examine"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        item_id = _name(args)
        if not item_id:
            ctx.output.error("[bold red]No item specified. Use 'examine <item>'[/bold red]")
            return

        in_inventory = ctx.player.resolve_inventory_item(item_id)
        if in_inventory:
            item = ctx.player.get_item_from_inventory(in_inventory)
        else:
            current_room = ctx.player.current_room
            in_room = ctx.resolver.resolve_shortcut(item_id, "room")
            if in_room:
                item = ctx.world.get_item(in_room)
            else:
                show_not_found(
                    ctx,
                    f"[bold red]Cannot find {item_id} in this directory or your "
                    "inventory.[/bold red]",
                    item_id,
                    [*visible_room_items(ctx, current_room), *inventory_names(ctx.player)],
                    label="Here",
                )
                return

        from src.rarity import RaritySystem

        item_name = item.name
        rarity = item.rarity
        formatted_name = RaritySystem.format_item_name_with_rarity(
            item_name, rarity, show_emoji=False
        )

        title = f"Examining: {item_icon(item.type)} {formatted_name}"
        description = item.description or "No detailed description available."

        details = []
        color = RaritySystem.get_rarity_color(rarity)
        details.append(f"[bold]Rarity:[/bold] [{color}]{rarity.title()}[/{color}]")

        item_type = item.type
        details.append(f"[bold]Type:[/bold] {item_icon(item_type)} {item_type.title()}")

        if item_type == "weapon":
            damage = item.damage
            if damage > 0:
                details.append(f"[bold]Damage:[/bold] {damage}")
        elif item_type == "armor":
            from src.player import armor_mitigation_pct
            details.append(
                f"[bold]Defense:[/bold] {item.defense} "
                f"(damage taken -{armor_mitigation_pct(item.defense):g}%)"
            )
        elif item_type == "consumable":
            healing = item.healing or 0
            if healing > 0:
                details.append(f"[bold]Healing:[/bold] {healing} HP")

        if item.usable:
            details.append("[green]This item can be used.[/green]")
        if item.consumed_on_use or item.consumable:
            details.append("[yellow]This item will be consumed when used.[/yellow]")
        if not item.takeable:
            details.append("[red]This item cannot be taken.[/red]")
        if not item.droppable:
            details.append("[red]This item cannot be dropped once taken.[/red]")

        if item.class_restriction:
            details.append(
                f"[bold]Class Restriction:[/bold] {item.class_restriction.title()}"
            )
        elif item.allowed_classes:
            allowed_classes = item.allowed_classes
            details.append(
                f"[bold]Allowed Classes:[/bold] {', '.join(allowed_classes).title()}"
            )

        content = f"{description}\n"
        if details:
            content += "\n" + "\n".join(details)

        ctx.output.write(f"[bold cyan]── {title} ──[/bold cyan]\n{content}")

        if item.on_examine is not None:
            ctx.effects.execute_effect(item.on_examine)


class TalkCommand(Command):
    name = "talk"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        npc_id = _first(args)
        if not npc_id:
            ctx.output.error("[bold red]No NPC specified. Use 'talk <npc>'[/bold red]")
            return

        current_room = ctx.player.current_room
        npcs_in_room = ctx.world.get_npcs_in_room(current_room)

        if npc_id not in npcs_in_room:
            show_not_found(
                ctx,
                f"[bold red]Cannot find {npc_id} in this directory.[/bold red]",
                npc_id,
                npcs_in_room,
                label="Here",
            )
            return

        npc = ctx.world.get_npc(npc_id)
        if not npc:
            ctx.output.error(
                f"[bold red]Error: NPC data not found for {npc_id}[/bold red]"
            )
            return

        npc_name = npc.name

        # Story-aware dialogue: ordered rules pick the right bank for the current
        # game state; NPCs without rules keep the legacy flat list.
        from src.npc_dialogue import resolve_dialogue_bank

        rules = npc.dialogue_rules
        banks = npc.dialogue
        state = {
            "flags": getattr(ctx.player, "story_flags", {}) or {},
            "items": set(getattr(ctx.player, "inventory", {}) or {}),
            "met": getattr(ctx.player, "met_npcs", set()),
            "npc_id": npc_id,
            "game_won": bool((getattr(ctx.player, "story_flags", {}) or {}).get("ending_chosen")),
        }
        dialogues = resolve_dialogue_bank(rules, banks, state) or npc.dialogues
        if not dialogues:
            ctx.output.write(
                f"[bold cyan]🗨  {npc_name}[/bold cyan]\n"
                f'[italic dim]"..."[/italic dim]\n'
                f"[dim]({npc_name} has nothing to say right now.)[/dim]"
            )
            return

        ctx.player.met_npcs.add(npc_id)
        dialogue = rng.choice(dialogues)
        # Render in ONE write. A char-by-char typewriter can't animate a string
        # that contains Rich markup — a mid-word frame like "[bold cyan]…[/b"
        # is unbalanced markup and raises MarkupError.
        ctx.output.write(
            f"[bold cyan]🗨  {npc_name}[/bold cyan]\n"
            f'[italic yellow]"{dialogue}"[/italic yellow]'
        )

        if npc.on_talk is not None:
            ctx.effects.execute_effect(npc.on_talk)


class EquipCommand(Command):
    name = "equip"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        weapon_id = _name(args)
        if not weapon_id:
            debug_log("equip command called with no weapon specified")
            ctx.output.write(
                "[bold red]No weapon specified. Use 'equip <weapon>'[/bold red]"
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
            show_not_found(
                ctx,
                f"[bold red]You don't have {original_input} in your inventory.[/bold red]",
                original_input,
                inventory_names(ctx.player),
                label="Inventory",
            )
            return

        weapon = ctx.player.get_item_from_inventory(weapon_id)
        weapon_type = weapon.type

        is_armor = (
            weapon_type == "armor" or "armor" in str(weapon_type)
            if weapon_type
            else False
        )
        if is_armor:
            if not ctx.player.can_use_item(weapon):
                class_restriction = class_restriction_text(weapon)
                ctx.output.write(
                    f"[bold red]This armor can only be used by {class_restriction} "
                    "class.[/bold red]"
                )
                return
            if ctx.player.equip_armor(weapon_id):
                armor_name = weapon.name
                pct = round(getattr(ctx.player, "armor_mitigation", 0.0) * 100)
                ctx.output.write(
                    f"You have equipped [green]{armor_name}[/green]. "
                    f"[cyan]🛡 Damage taken reduced by {pct}%.[/cyan]"
                )
                _tutorial_gear_equipped(ctx, "armor")
            return

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
            class_restriction = class_restriction_text(weapon)
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
            weapon_name = weapon.name
            ctx.output.write(f"You have equipped [green]{weapon_name}[/green].")
            ctx.effects.show_damage_change(old_damage, ctx.player.calculate_damage())

            _tutorial_gear_equipped(ctx, "weapon")
        else:
            debug_log(f"Failed to equip weapon {weapon_id}")
            ctx.output.write(f"[bold red]Failed to equip {weapon_id}.[/bold red]")
