#!/usr/bin/env python3
"""Shell commands that exist to teach the real thing: man, tree, whoami, echo, clear.

Everything here mirrors a command the player will meet in an actual terminal.
``man`` is the important one — it is where the game stops being an analogy and
tells you what these commands genuinely do outside the fiction.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from src import room_paths
from src.commands.base import Command

if TYPE_CHECKING:  # pragma: no cover
    from src.command_handler import CommandHandler


# --- man ---------------------------------------------------------------------

# name -> (section, one-line purpose, synopsis, description, in-game note)
MANPAGES: dict[str, tuple[str, str, str, str, str]] = {
    "ls": (
        "1", "list directory contents", "ls [-a] [-l]",
        "Lists the entries of the current directory: its subdirectories and the\n"
        "files inside it.\n\n"
        "  -a   Also show entries whose names begin with a dot. Unix hides those\n"
        "       by convention, not by permission — -a is how you see them.\n"
        "  -l   Long format. Each entry gains a permission column: the leading\n"
        "       'd' means directory, then read/write/execute for owner, group\n"
        "       and others.",
        "Files here are items you can take or cat. Processes are the spirits you\n"
        "can talk to. -a is how hidden directories are found.",
    ),
    "cd": (
        "1", "change the working directory", "cd [directory]",
        "Moves you to another directory. Paths beginning with / are absolute and\n"
        "resolve from the root; anything else is relative to where you stand.\n\n"
        "  ..   the parent directory\n"
        "  .    the current directory\n\n"
        "With no argument, cd returns to your home directory.\n\n"
        "Entering a directory requires execute permission on it AND on every\n"
        "directory above it, which is why a sealed parent seals everything beneath.",
        "Permission here is carried by keys. A key you hold is spent automatically\n"
        "when you walk into the door it opens.",
    ),
    "pwd": (
        "1", "print the working directory", "pwd",
        "Prints the absolute path of the directory you are currently in.\n"
        "Short for 'print working directory'.",
        "Your location is always a real path — /home, /var/backups, /usr/games.",
    ),
    "cat": (
        "1", "concatenate and print files", "cat [file]",
        "Prints the contents of a file. Named for concatenate: given several\n"
        "files it prints them one after another, joined end to end.",
        "Reading lore files with cat is how the story is recovered.",
    ),
    "find": (
        "1", "search for files in a directory tree", "find [path] -name [pattern]",
        "Walks a directory tree and prints the paths that match. -name matches\n"
        "against the filename.",
        "Only a few searches are meaningful here; most of the filesystem is found\n"
        "by walking it with ls and cd.",
    ),
    "ps": (
        "1", "report running processes", "ps",
        "Reports a snapshot of the current processes: their PID (process id),\n"
        "PPID (parent process id) and command. PID 1 is init, the first process\n"
        "the kernel starts, and every other process descends from it.",
        "The daemons haunting this system are processes that outlived their parents.",
    ),
    "tree": (
        "1", "list directories as a tree", "tree",
        "Prints the directory hierarchy as an indented tree rather than one level\n"
        "at a time. Not part of POSIX, but present nearly everywhere.",
        "Only directories you have discovered appear.",
    ),
    "whoami": (
        "1", "print the effective user name", "whoami",
        "Prints the username you are currently acting as. Useful after su or\n"
        "sudo, when you may not be who you think you are.",
        "Prints your name, class and level.",
    ),
    "echo": (
        "1", "display a line of text", "echo [text ...]",
        "Writes its arguments back out, separated by spaces. The building block\n"
        "of shell scripts and the usual way to inspect a variable.",
        "The haunted filesystem sometimes echoes back something other than what\n"
        "you said.",
    ),
    "clear": (
        "1", "clear the terminal screen", "clear",
        "Clears the visible scrollback of the terminal. Nothing is deleted; only\n"
        "the display is reset.",
        "Clears the output panel.",
    ),
    "man": (
        "1", "display the manual for a command", "man [command]",
        "Displays the manual page for a command: what it does, how it is invoked,\n"
        "and what its options mean. The first place to look when a command is\n"
        "unfamiliar.\n\n"
        "Manual pages are grouped in sections; section 1 is user commands.",
        "Run 'man' with no argument to list every page available here.",
    ),
}

# Verbs that belong to the game rather than to Unix. Naming them explicitly keeps
# `man take` from pretending there is a real take(1).
GAME_VERBS = {
    "take", "drop", "use", "equip", "examine", "talk", "attack", "flee",
    "inventory", "inv", "journal", "keys", "shortcuts", "save", "quit", "exit",
    "help", "map",
}


class ManCommand(Command):
    name = "man"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        if not args:
            self._index(ctx)
            return

        topic = args[0].lower()
        page = MANPAGES.get(topic)
        if page is None:
            if topic in GAME_VERBS:
                ctx.output.write(
                    f"[yellow]No manual entry for {topic}[/yellow]\n\n"
                    f"[dim]{topic} is a command of this world, not of Unix. "
                    "Type [bold]help[/bold] for those.[/dim]"
                )
            else:
                ctx.output.write(f"[red]No manual entry for {topic}[/red]")
            return

        section, purpose, synopsis, description, in_game = page
        out = Text()
        out.append(f"{topic.upper()}({section})", style="bold")
        out.append(f"{' ' * 24}Sysadmin Spirit Manual\n\n")
        out.append("NAME\n", style="bold")
        out.append(f"     {topic} - {purpose}\n\n")
        out.append("SYNOPSIS\n", style="bold")
        out.append(f"     {synopsis}\n\n", style="cyan")
        out.append("DESCRIPTION\n", style="bold")
        for line in description.split("\n"):
            out.append(f"     {line}\n")
        out.append("\nIN THIS FILESYSTEM\n", style="bold")
        for line in in_game.split("\n"):
            out.append(f"     {line}\n", style="italic")
        ctx.output.write(out)

    @staticmethod
    def _index(ctx: "CommandHandler") -> None:
        out = Text()
        out.append("What manual page do you want?\n\n", style="bold")
        out.append("Real commands, documented here:\n", style="bold cyan")
        for name in sorted(MANPAGES):
            purpose = MANPAGES[name][1]
            out.append(f"  {name:<8}", style="cyan")
            out.append(f"{purpose}\n")
        out.append("\nTry: man ls\n", style="dim")
        ctx.output.write(out)


# --- tree --------------------------------------------------------------------


class TreeCommand(Command):
    name = "tree"
    aliases = ("map",)

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        out = Text()
        out.append("Discovered filesystem\n\n", style="bold cyan")
        root_id = room_paths.room_at("/")
        if root_id is None:
            ctx.output.write("[red]tree: no root directory[/red]")
            return
        self._branch(ctx, out, root_id, prefix="", is_last=True, is_root=True)

        keys = ctx.resolver.player_keys()
        if keys:
            out.append("\nKeys you carry: ", style="bold blue")
            out.append(", ".join(keys) + "\n", style="blue")
        out.append(
            "\n[dim]🔒 sealed · ⚔ another class · ✓ cleared · ← you are here[/dim]"
        )
        ctx.output.write(out)

    def _branch(
        self, ctx: "CommandHandler", out: Text, room_id: str,
        prefix: str, is_last: bool, is_root: bool = False,
    ) -> None:
        path = room_paths.room_path(room_id)
        label = room_paths.basename(path) if not is_root else "/"
        room = ctx.world.get_room(room_id)
        name = room.name if room else room_id

        allowed, denial = ctx.world.check_access(room_id, ctx.player)
        marks = []
        if not allowed and denial:
            if denial["reason"] == "class":
                marks.append("⚔")
            elif denial["room_id"] == room_id:
                key = ctx.world.get_room_state(room_id).get("key_required")
                marks.append(f"🔒 {key}" if key else "🔒")
        if ctx.world.is_room_cleared(room_id):
            marks.append("✓")
        here = room_id == ctx.player.current_room

        if is_root:
            connector = ""
        else:
            connector = "└── " if is_last else "├── "

        style = "bold cyan" if here else ("blue" if allowed else "dim")
        out.append(f"{prefix}{connector}")
        out.append(f"{label}{'' if is_root else '/'}", style=style)
        out.append(f"  {name}", style="dim")
        if marks:
            out.append("  " + " ".join(marks), style="yellow")
        if here:
            out.append("  ← you are here", style="bold cyan")
        out.append("\n")

        children = [
            child for child in room_paths.children_of(path)
            if ctx.world.is_discovered(child)
        ]
        if is_root:
            child_prefix = prefix
        else:
            child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(children):
            self._branch(
                ctx, out, child, child_prefix, is_last=(i == len(children) - 1)
            )


# --- small authentic extras --------------------------------------------------


class WhoamiCommand(Command):
    name = "whoami"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        player = ctx.player
        name = getattr(player, "name", "") or "unknown"
        out = Text()
        out.append(f"{name}\n", style="bold green")
        out.append(
            f"{str(getattr(player, 'player_class', '')).title()} · "
            f"level {getattr(player, 'level', 1)} · "
            f"{getattr(player, 'health', 0)}/{getattr(player, 'max_health', 0)} HP\n",
            style="dim",
        )
        if player.get_story_flag("sudo_trial_complete"):
            out.append("Superuser privileges: granted\n", style="yellow")
        ctx.output.write(out)


class EchoCommand(Command):
    name = "echo"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        said = " ".join(args)
        if not said:
            ctx.output.write("")
            return
        ctx.output.write(said)


class ClearCommand(Command):
    name = "clear"

    def execute(self, ctx: "CommandHandler", args: list[str]) -> None:
        # A write replaces the output panel, so writing nothing clears it.
        ctx.output.write("")
