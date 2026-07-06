#!/usr/bin/env python3
"""Read-only display commands: journal, inventory, map, keys.

Bodies moved verbatim from CommandHandler (self -> ctx); they reuse handler
helpers (get_formatted_item_description, _get_room_status_indicator,
_get_player_keys, STORY_FLAG_* tables) during the strangler migration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from src.commands.base import Command

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
            title = ctx.STORY_FLAG_TITLES.get(flag, flag.replace("_", " ").title())
            desc = ctx.STORY_FLAG_DESCRIPTIONS.get(flag, "")
            output.append(f"\n✦ {title}\n", style="bold magenta")
            if desc:
                output.append(f"  {desc}\n", style="dim")

        total = len(ctx.STORY_FLAG_TITLES)
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
                -RaritySystem.get_rarity_order(x[1].get("rarity", "common")) if x[1] else 0,
                x[1].get("name", x[0]) if x[1] else x[0],
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


class MapCommand(Command):
    name = "map"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        visited_rooms = [
            room_id
            for room_id, state in ctx.world.room_states.items()
            if state.get("visited", False)
        ]

        discovered_rooms = []
        for visited_room in visited_rooms:
            exits = ctx.world.get_exits(visited_room)
            for exit_room in exits:
                room_state = ctx.world.get_room_state(exit_room)
                if (
                    exit_room not in visited_rooms
                    and room_state
                    and not room_state.get("hidden", False)
                ):
                    discovered_rooms.append(exit_room)

        discovered_rooms = list(set(discovered_rooms))

        if not visited_rooms and not discovered_rooms:
            ctx.output.write(
                "[italic]Your map is empty. Explore to discover locations.[/italic]"
            )
            return

        output = Text()
        output.append("🗺  SYSTEM MAP\n", style="bold cyan")
        output.append("=" * 50 + "\n", style="dim")

        if visited_rooms:
            output.append("\n✅ EXPLORED AREAS:\n", style="bold green")
            for room_id in sorted(visited_rooms):
                status_indicator = ctx._get_room_status_indicator(room_id)
                if room_id == ctx.player.current_room:
                    output.append(
                        f"  ➤ {room_id} {status_indicator} "
                        "[bold cyan](YOU ARE HERE)[/bold cyan]\n"
                    )
                else:
                    output.append(f"  • {room_id} {status_indicator}\n", style="green")

        unvisited_discovered = [r for r in discovered_rooms if r not in visited_rooms]
        if unvisited_discovered:
            output.append("\n🔍 DISCOVERED AREAS:\n", style="bold yellow")
            for room_id in sorted(unvisited_discovered):
                status_indicator = ctx._get_room_status_indicator(room_id)
                output.append(f"  • {room_id} {status_indicator}\n", style="yellow")

        keys = ctx._get_player_keys()
        if keys:
            output.append("\n🔑 YOUR KEYS:\n", style="bold blue")
            for key_id in keys:
                output.append(f"  • {key_id}\n", style="blue")

        output.append(
            "\n[dim]💡 Use 'ls -a', 'find', and 'ps' to discover hidden areas![/dim]"
        )
        ctx.output.write(output)


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

        player_keys = ctx._get_player_keys()
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
