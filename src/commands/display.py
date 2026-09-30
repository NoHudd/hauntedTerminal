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

from src import room_paths
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
        output.append(f"⚑ {ctx.flags.summary()}\n", style="bold yellow")
        for room_id in sorted(ctx.world.rooms):
            flag = ctx.flags.flag_for(room_id)
            if flag is not None and ctx.world.flag_captured(room_id):
                output.append(
                    f"  {room_paths.room_path(room_id)}  {flag.text}\n", style="yellow"
                )

        if not discovered:
            output.append(
                "\nNo memories restored yet. Explore the filesystem and "
                "`cat` any lore files you find.",
                style="italic",
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
            f"\nProgress: {len(discovered)}/{total} memories restored.", style="dim"
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
        output.append("🔑 KEYS\n", style="bold cyan")
        output.append("=" * 50 + "\n", style="dim")

        keys = sorted(
            (iid, item) for iid, item in ctx.world.items.items()
            if str(item.type).lower() == "key"
        )
        flag_keys = {
            str(room.flag.grants) for room in ctx.world.rooms.values()
            if getattr(room, "flag", None) is not None and room.flag.grants
        }
        for key_id, item in keys:
            if not ctx.player.has_item(key_id):
                # Unearned: its doors are still invisible, so don't name them.
                source = "earned by a flag" if key_id in flag_keys else "dropped by a boss"
                output.append(f"\n❌ ??? — {source}\n", style="dim")
                continue
            # An undiscovered secret room stays secret, here as in ls.
            doors = ", ".join(
                room_paths.room_path(r)
                if not getattr(ctx.world.get_room(r), "hidden", False)
                or ctx.world.is_discovered(r)
                else "???"
                for r in item.unlocks
            ) or "—"
            output.append(f"\n✅ {item.name} ({key_id})\n", style="bold")
            output.append(f"   🚪 Opens: {doors}\n", style="blue")

        output.append("\n💡 HOW DOORS OPEN:\n", style="bold magenta")
        output.append(
            "Some flags hand you a key; bosses drop the rest. A locked directory "
            "only shows up once you hold its key.\n",
            style="dim",
        )
        for room_id, room in ctx.world.rooms.items():
            if getattr(room, "flags_required", 0):
                have = ctx.world.flag_counts(exclude=room_id)[0]
                output.append(
                    f"{room_paths.room_path(room_id)} takes no key: it opens once you "
                    f"hold {room.flags_required} flags (you have {have}). "
                    "tree shows the flags you hold.\n",
                    style="dim",
                )
        output.append("Stuck in a room? Type hint.\n", style="dim")
        ctx.output.write(output)
