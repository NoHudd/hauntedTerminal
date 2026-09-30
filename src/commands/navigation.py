#!/usr/bin/env python3
"""Navigation commands: ls, cd.

The rooms form a real directory tree (see src/room_paths.py), so both verbs
behave like their shell counterparts:

- ``cd`` takes any absolute or relative path and understands ``.`` and ``..``.
  It is not restricted to the room's exit list; what restricts you is
  permission, on every ancestor directory as well as the destination.
- ``ls`` lists the current directory's child directories alongside its files,
  processes and hostiles. ``-a`` also shows ``.``, ``..`` and hidden children
  (revealing them), and ``-l`` renders permissions in long format.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

import config.dev_config as dev_cfg
from src import room_paths
from src.item_icons import item_icon
from src.commands.base import Command
from src.commands.hints import show_not_found
from utils.debug_tools import debug_log

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler

HOME_PATH = "/home"


# --- shared helpers ----------------------------------------------------------


def _unlock_with_held_key(ctx: "CommandHandler", room_id: str) -> bool:
    """If the player carries the key for room_id, spend it: unlock and reveal.

    Returns True if the room became accessible. Mirrors the long-standing
    behaviour where walking into a door you have the key for just opens it.
    """
    state = ctx.world.get_room_state(room_id)
    key_required = state.get("key_required")
    if not key_required or not ctx.player.has_item(key_required):
        return False

    key_item = ctx.player.get_item_from_inventory(key_required)
    unlocks = [
        ctx.room_aliases.get(str(r).lower(), r) for r in key_item.unlocks
    ]
    if room_id not in unlocks and not key_item.usable:
        return False

    ctx.world.discover_room(room_id)
    ctx.world.unlock_room(room_id)
    path = room_paths.room_path(room_id)
    key_name = key_item.name
    ctx.output.write(
        f"[yellow]The {key_name} fits. {path} unlocks.[/yellow]"
    )
    debug_log(f"{key_required} auto-unlocked {room_id}")
    return True


def _permission_bits(ctx: "CommandHandler", room_id: str) -> str:
    """Long-format permission column for a child directory."""
    allowed, denial = ctx.world.check_access(room_id, ctx.player)
    if allowed:
        return "drwxr-xr-x"
    if denial and denial["reason"] == "class":
        return "dr-x------"
    return "dr--------"


def _exit_names(ctx: "CommandHandler", room_id: str) -> list[str]:
    """Names a player could type to leave this room: path basenames and room ids."""
    names: list[str] = []
    for exit_id in ctx.world.get_exits(room_id):
        # Hidden rooms stay hidden: a typo must not reveal what `ls -a` guards.
        if not ctx.world.is_discovered(exit_id):
            continue
        names.append(room_paths.basename(room_paths.room_path(exit_id)))
        names.append(exit_id)
    return names


class CdCommand(Command):
    name = "cd"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        current_room = ctx.player.current_room
        current_path = room_paths.room_path(current_room)

        # Bare `cd` goes home, exactly like a shell with $HOME set.
        typed = args[0] if args else HOME_PATH

        target = room_paths.resolve(typed, current_path, ctx.room_aliases)
        if target is None:
            show_not_found(
                ctx,
                f"[bold red]cd: {typed}: No such file or directory[/bold red]",
                typed,
                _exit_names(ctx, current_room),
                label="Exits",
            )
            return

        if target == current_room:
            ctx.output.write(f"You are already in [bold]{current_path}[/bold].")
            return

        # Try the key in every sealed door along the way before reporting failure.
        # A key both reveals and unlocks: a player holding the opt_key should not
        # be told the mage tower does not exist.
        allowed, denial = ctx.world.check_access(target, ctx.player)
        while not allowed and denial and denial["reason"] in ("locked", "missing"):
            if not _unlock_with_held_key(ctx, denial["room_id"]):
                break
            allowed, denial = ctx.world.check_access(target, ctx.player)

        if not allowed:
            self._deny(ctx, typed, denial)
            return

        destination_path = room_paths.room_path(target)
        debug_log(f"Moving player from {current_path} to {destination_path}")
        ctx.player.move_to(target)

        room = ctx.world.get_room(target)
        room_name = room.name if room else target
        ctx.output.write(
            f"[bold cyan]{destination_path}[/bold cyan] — entering {room_name}..."
        )

        ctx.display_location()
        ctx.arrive()
        ctx.tutorial.after_move()

    @staticmethod
    def _deny(ctx: "CommandHandler", typed: str, denial: dict | None) -> None:
        """Report a refused cd the way a shell would, then say what would help."""
        if not denial:
            ctx.output.error(f"[bold red]cd: {typed}: Permission denied[/bold red]")
            return

        path = denial["path"]

        if denial["reason"] == "missing":
            # An undiscovered directory is indistinguishable from one that isn't
            # there — which is exactly what makes `ls -a` worth learning.
            ctx.output.error(
                f"[bold red]cd: {typed}: No such file or directory[/bold red]"
            )
            return

        if denial["reason"] == "class":
            ctx.output.error(f"[bold red]cd: {path}: Permission denied[/bold red]")
            ctx.output.write(
                f"[cyan]⚔ Only {denial['class_restriction']} spirits may enter "
                f"{path}.[/cyan]"
            )
            return

        if denial["reason"] == "flags":
            ctx.output.error(f"[bold red]cd: {path}: Permission denied[/bold red]")
            ctx.output.write(
                f"[yellow]💡 {path} opens once you hold {denial['flags_required']} "
                f"flags. You have {denial['flags_have']} — [bold]tree[/bold] shows "
                "which directories still hide one.[/yellow]"
            )
            return

        ctx.output.error(f"[bold red]cd: {path}: Permission denied[/bold red]")
        key_required = denial["key_required"]
        blocked_ancestor = room_paths.normalize(typed) != path and not typed.startswith("-")
        if key_required:
            ctx.output.write(
                f"[yellow]💡 You need '{key_required}' to traverse {path}."
                "[/yellow]"
            )
        else:
            ctx.output.write(f"[yellow]💡 {path} is sealed.[/yellow]")
        if blocked_ancestor:
            ctx.output.write(
                f"[dim]{path} is on the way to {typed} — a directory can only be "
                "entered through its parents.[/dim]"
            )


class LsCommand(Command):
    name = "ls"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        room_id = ctx.player.current_room
        flags = "".join(a[1:] for a in args if a.startswith("-") and len(a) > 1)
        show_all = "a" in flags
        long_format = "l" in flags

        output = Text()
        has_content = False
        hints = getattr(dev_cfg, "SHOW_HINTS", True)

        has_enemies, enemy_output = ctx.check_enemies_blocking_exploration(room_id)
        if has_enemies:
            ctx.output.write(enemy_output)
            return

        revealed, directories = self._render_directories(
            ctx, output, room_id, show_all, long_format
        )
        has_content = has_content or bool(output)

        items = ctx.world.get_items_in_room(room_id) or []
        if show_all:
            ctx.world.mark_hidden_files_listed(room_id)
        else:
            # Hidden files only list under -a, like real dotfiles. They stay
            # addressable by name (cat/take) either way.
            items = [
                item_id for item_id in items
                if not getattr(ctx.world.get_item(item_id), "hidden", False)
            ]
        weapon_found, weapon_id = self._render_items(
            ctx, output, items, hints, long_format, has_content
        )
        has_content = has_content or bool(items)

        npcs = ctx.world.get_npcs_in_room(room_id) or []
        self._render_npcs(ctx, output, npcs, hints, has_content)
        has_content = has_content or bool(npcs)

        enemies = ctx.world.get_enemies_in_room(room_id) or []
        self._render_enemies(ctx, output, enemies, has_content)
        has_content = has_content or bool(enemies)

        if not has_content:
            output.append("No files, processes, or entities found.")

        ctx.output.write(output)

        if revealed:
            # The sidebar and scene only rebuild on ROOM_ENTERED. Without this a
            # newly revealed directory stays invisible in the persistent UI until
            # the player leaves and comes back.
            ctx.announce_room()

        ctx.tutorial.after_ls(
            weapon_found, weapon_id,
            has_directories=bool(directories), show_all=show_all,
        )

    # -- sections -------------------------------------------------------------

    @staticmethod
    def _may_discover(ctx: "CommandHandler", room_id: str) -> bool:
        """Whether `ls -a` is allowed to reveal this hidden room yet.

        A room may declare a `discovery_requirement`: a story flag the player
        must hold before the directory shows up at all. It exists so a room the
        player is not ready for cannot be stumbled into — /proc/self is the Sudo
        Trial, an unfleeable boss, and it stays invisible until something in the
        world has actually told you the trial is there.
        """
        room = ctx.world.get_room(room_id)
        requirement = getattr(room, "discovery_requirement", None) if room else None
        if not requirement:
            return True
        return bool(ctx.player.get_story_flag(requirement))

    def _render_directories(
        self, ctx: "CommandHandler", output: Text, room_id: str,
        show_all: bool, long_format: bool,
    ) -> tuple[list[str], list[str]]:
        """List child directories. With -a, also reveal and show hidden ones.
        Returns (newly revealed, all listed)."""
        here = room_paths.room_path(room_id)
        children = room_paths.children_of(here)

        revealed: list[str] = []
        visible: list[str] = []
        for child in children:
            if ctx.world.is_discovered(child):
                visible.append(child)
            elif show_all and self._may_discover(ctx, child):
                if ctx.world.discover_room(child):
                    revealed.append(child)
                visible.append(child)

        if not visible and not show_all:
            return revealed, visible

        output.append("Directories:\n", style="bold blue")

        if show_all:
            for dot in (".", ".."):
                if long_format:
                    output.append(f"  drwxr-xr-x  {dot}\n", style="dim")
                else:
                    output.append(f"  {dot}/\n", style="dim")

        for child in visible:
            path = room_paths.room_path(child)
            name = room_paths.basename(path)
            room = ctx.world.get_room(child)
            label = room.name if room else child
            style = "blue" if ctx.world.check_access(child, ctx.player)[0] else "dim"
            cleared = " ✓" if ctx.world.is_room_cleared(child) else ""
            if long_format:
                output.append(f"  {_permission_bits(ctx, child)}  ", style="dim")
                output.append(f"{name}/", style=f"bold {style}")
                output.append(f"  {label}{cleared}\n")
            else:
                output.append(f"  {name}/", style=f"bold {style}")
                output.append(f" - {label}{cleared}\n")

        for child in revealed:
            path = room_paths.room_path(child)
            output.append(
                f"\n✨ Revealed hidden directory: {path}\n", style="bold green"
            )
        return revealed, visible

    def _render_items(
        self, ctx: "CommandHandler", output: Text, items: list[str],
        hints: bool, long_format: bool, has_content: bool,
    ) -> tuple[bool, str | None]:
        if not items:
            return False, None
        from src.rarity import RaritySystem

        if has_content:
            output.append("\n")
        output.append("Files:\n", style="bold green")

        weapon_found = False
        weapon_id = None
        for item_id in items:
            item = ctx.world.get_item(item_id)
            # A hidden file is a dotfile: listed, hinted and completed with its
            # leading dot, so what the player sees is what they type.
            shown = f".{item_id}" if item and item.hidden else item_id
            description = ctx.get_formatted_item_description(item)
            # Colour the file by rarity so value reads at a glance. Common maps to
            # white, invisible against the description, so commons get green.
            rarity = item.rarity if item else "common"
            item_color = RaritySystem.get_rarity_color(rarity)
            if item_color in ("white", "bright_white", "default"):
                item_color = "green"
            if item and item.story_flag:
                item_color = "red"  # story files all read like .bash_profile
            if long_format:
                output.append("  -rw-r--r--  ", style="dim")
            else:
                output.append("  ")
            output.append(f"{item_icon(item.type if item else None)} ")
            output.append(shown, style=f"bold {item_color}")
            output.append(f" - {description}\n")
            if hints:
                readable = (
                    item and item.type == "lore"
                    and not item.takeable
                )
                verb = "cat" if readable else "take"
                output.append(f"     → {verb} {shown}\n", style="dim cyan")

            if item and item.type == "weapon" and not weapon_found:
                weapon_found = True
                weapon_id = item_id
        return weapon_found, weapon_id

    @staticmethod
    def _render_npcs(
        ctx: "CommandHandler", output: Text, npcs: list[str],
        hints: bool, has_content: bool,
    ) -> None:
        if not npcs:
            return
        if has_content:
            output.append("\n")
        output.append("Processes:\n", style="bold yellow")
        for npc_id in npcs:
            npc = ctx.world.get_npc(npc_id)
            if not npc:
                continue
            description = (
                npc.short_description
                or npc.description
                or npc.name
                or "No description available"
            )
            output.append(f"  {npc_id}", style="yellow")
            output.append(f" - {description}\n")
            if hints:
                output.append(f"     → talk {npc_id}\n", style="dim cyan")

    @staticmethod
    def _render_enemies(
        ctx: "CommandHandler", output: Text, enemies: list[str], has_content: bool,
    ) -> None:
        if not enemies:
            return
        if has_content:
            output.append("\n")
        output.append("Corrupted Entities:\n", style="bold red")
        for enemy_id in enemies:
            enemy = ctx.world.get_enemy(enemy_id, ctx.player.player_class)
            if enemy:
                name = enemy.name
                health = enemy.health
                damage = enemy.damage
                output.append(f"  {enemy_id}", style="red")
                output.append(f" - {name} (HP: {health}, DMG: {damage})\n")
            else:
                output.append(f"  {enemy_id} - Unknown Enemy\n", style="red")
