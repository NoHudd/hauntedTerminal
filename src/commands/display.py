#!/usr/bin/env python3
"""Read-only display commands: journal, inventory, keys.

The old `map` verb now lives in shell.py as `tree`, which renders the same
information as a real directory hierarchy (and still answers to "map").

Keys come from ctx.resolver; item blurbs from the handler's
get_formatted_item_description.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from src.commands.base import Command
from src.item_effects import STORY_FLAG_DESCRIPTIONS, STORY_FLAG_TITLES

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


class JournalCommand(Command):
    name = "journal"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        flags = ctx.player.story_flags or {}
        discovered = [k for k, v in flags.items() if v]

        output = Text()
        output.append("📖 JOURNAL\n", style="bold cyan")
        output.append("=" * 50 + "\n", style="dim")

        if not discovered:
            output.append(
                "\n[italic]No memories restored yet. Explore the filesystem and "
                "`cat` any lore files you find.[/italic]"
            )
            ctx.output.write(output)
            return

        for flag in discovered:
            title = STORY_FLAG_TITLES.get(flag, flag.replace("_", " ").title())
            desc = STORY_FLAG_DESCRIPTIONS.get(flag, "")
            output.append(f"\n✦ {title}\n", style="bold magenta")
            if desc:
                output.append(f"  {desc}\n", style="dim")

        total = len(STORY_FLAG_TITLES)
        output.append(
            f"\n[dim]Progress: {len(discovered)}/{total} memories restored.[/dim]"
        )
        ctx.output.write(output)


class InventoryCommand(Command):
    name = "inventory"
    aliases = ("inv",)

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        items = ctx.player.get_inventory_items()

        if not items:
            ctx.output.write(
                "[bold cyan]── Inventory ──[/bold cyan]\n"
                "[italic]Your inventory is empty.[/italic]"
            )
            return

        from src.rarity import RaritySystem

        inventory_content = "[bold]Inventory:[/bold]\n"

        sorted_items = sorted(
            [(item_id, ctx.player.get_item_from_inventory(item_id)) for item_id in items],
            key=lambda x: (
                -RaritySystem.get_rarity_order(x[1].rarity) if x[1] else 0,
                x[1].name if x[1] else x[0],
            ),
        )

        for item_id, item in sorted_items:
            if item is None:
                inventory_content += f"  [green]{item_id}[/green]\n"
                continue

            is_equipped = item_id == ctx.player.equipped_weapon
            formatted_item = RaritySystem.format_inventory_item(item_id, item, is_equipped)
            description = ctx.get_formatted_item_description(item)
            inventory_content += f"  {formatted_item}\n    [dim]{description}[/dim]\n"

        ctx.output.write(
            f"[bold cyan]── Inventory ──[/bold cyan]\n{inventory_content.rstrip()}"
        )


class KeysCommand(Command):
    name = "keys"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        output = Text()
        output.append("🔑 KEY PROGRESSION SYSTEM\n", style="bold cyan")
        output.append("=" * 50 + "\n", style="dim")

        key_info = {
            "lib_key": {
                "name": "Library Key",
                "found_in": "usr_lib_arcane",
                "unlocks": ["var_dungeon"],
                "description": "Unlocks the Variable Dungeon",
            },
            "opt_key": {
                "name": "Optional Key",
                "found_in": "var_dungeon",
                "unlocks": ["opt_mage_tower", "srv_warrior_tomb"],
                "description": "Unlocks class-restricted areas",
            },
        }

        output.append("📋 PROGRESSION STATUS:\n", style="bold yellow")

        for key_id, info in key_info.items():
            has_key = ctx.player.has_item(key_id)
            key_symbol = "✅" if has_key else "❌"
            output.append(
                f"\n{key_symbol} {info['name']} ({key_id})\n",
                style="bold" if has_key else "dim",
            )
            output.append(
                f"   📍 Found in: {info['found_in']}\n",
                style="green" if has_key else "dim",
            )
            output.append(
                f"   🚪 Unlocks: {', '.join(info['unlocks'])}\n",
                style="blue" if has_key else "dim",
            )
            output.append(f"   💡 {info['description']}\n", style="italic")

        player_keys = ctx.resolver.player_keys()
        if player_keys:
            output.append("\n🎒 KEYS IN INVENTORY:\n", style="bold green")
            for key in player_keys:
                output.append(f"  • {key}\n", style="green")
        else:
            output.append("\nNo keys currently in inventory.\n", style="dim")

        output.append("\n💡 PROGRESSION HINTS:\n", style="bold magenta")
        output.append(
            "1. Start by exploring usr_lib_arcane to find the lib_key\n", style="dim"
        )
        output.append(
            "2. Use lib_key to unlock var_dungeon and explore deeper\n", style="dim"
        )
        output.append(
            "3. Find opt_key while exploring to access class-restricted areas\n",
            style="dim",
        )
        ctx.output.write(output)
