"""Room flags: capture, counts, and the guidance that leads players to them.

Each room may declare a flag (docs/ROOM_FLAGS_SPEC.md). Commands report what
the player did (read a file, entered a room, typed a command); this service
decides whether a flag was captured and what Echo should say.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src import room_paths
from src.logs import log_lines
from utils.debug_tools import debug_log

FLAG_XP = 15
STUCK_AFTER = 8
ECHO = "[bold green]ECHO>[/bold green]"
TRIAL_BONUS = 4
TRIAL_TURNS = 10


class FlagService:
    def __init__(self, player: Any, world: Any, output: Any, save: Callable[[], None]):
        self.player = player
        self.world = world
        self.output = output
        self._save = save
        self._hints_asked: dict[str, int] = {}
        self._idle = 0
        self._nudged_room: str | None = None

    def flag_for(self, room_id: str) -> Any:
        room = self.world.get_room(room_id)
        return getattr(room, "flag", None) if room else None

    def counts(self) -> tuple[int, int, int, int]:
        main_got = main_total = secret_got = secret_total = 0
        for rid, room in self.world.rooms.items():
            if getattr(room, "flag", None) is None:
                continue
            got = int(self.world.flag_captured(rid))
            if room.hidden:
                secret_total += 1
                secret_got += got
            else:
                main_total += 1
                main_got += got
        return main_got, main_total, secret_got, secret_total

    def summary(self) -> str:
        main_got, main_total, secret_got, secret_total = self.counts()
        return f"Flags {main_got}/{main_total} · Secrets {secret_got}/{secret_total}"

    def on_file_read(self, item_id: str, save: bool = True) -> bool:
        """A file was read in the current room. Capture its flag if it is the
        room's flag file and not yet captured. Returns True on capture.
        save=False leaves the checkpoint to the caller (see checkpoint())."""
        room_id = self.player.current_room
        flag = self.flag_for(room_id)
        if flag is None or flag.file != item_id or self.world.flag_captured(room_id):
            return False
        if flag.via == "grep":
            if self._guiding():
                item = self.world.get_item(item_id)
                count = len(log_lines(item)) if item is not None and item.log else 0
                advice = (
                    flag.nudge if self._technique_known("grep")
                    else f"Search it instead: type {flag.command}"
                )
                self.output.write(f"{ECHO} {count} lines — nobody reads all that. {advice}")
            return False
        self._capture(room_id, flag, save)
        return True

    def _capture(self, room_id: str, flag: Any, save: bool) -> None:
        self.world.mark_flag_captured(room_id)
        self.player.harvest_cycles(FLAG_XP)
        self._idle = 0
        self.output.write(
            f"\n[bold yellow]⚑ Flag captured: {room_paths.room_path(room_id)} — "
            f"{flag.text}[/bold yellow]\n"
            f"[dim]{self.summary()} · +{FLAG_XP} cycles[/dim]"
        )
        if save:
            self.checkpoint()

    def on_grep(self, item_id: str, matched: list[str]) -> bool:
        """grep printed `matched` from item_id. Captures a grep flag when the
        flag line was among them."""
        room_id = self.player.current_room
        flag = self.flag_for(room_id)
        if (
            flag is not None and flag.via == "cat" and flag.file == item_id
            and not self.world.flag_captured(room_id)
            and any(flag.text in line for line in matched)
        ):
            self.output.write(
                f"{ECHO} That's this room's flag — but it only counts when you "
                f"read the file. Type {flag.command}"
            )
            return False
        if (
            flag is None or flag.via != "grep" or flag.file != item_id
            or self.world.flag_captured(room_id)
            or not any(flag.text in line for line in matched)
        ):
            return False
        self._capture(room_id, flag, save=True)
        return True

    def on_npc_talk(self) -> None:
        room_id = self.player.current_room
        flag = self.flag_for(room_id)
        if flag is not None and flag.clue and not self.world.flag_captured(room_id):
            self.output.write(f"[italic cyan]{flag.clue}[/italic cyan]")

    def checkpoint(self) -> None:
        try:
            self._save()
            self.output.write("[dim green]✓ Checkpoint saved.[/dim green]")
        except Exception as e:
            debug_log(f"Checkpoint save after a flag capture failed: {e}")
            self.output.write(f"[dim yellow]⚠ Checkpoint save failed: {e}[/dim yellow]")

    def _guiding(self) -> bool:
        return bool(self.player.tutorial_state.get("completed", False))

    def on_room_entered(self, room_id: str) -> None:
        """First visit to a room that teaches a technique: Echo gives the
        lesson. Also resets the stuck counter."""
        self._idle = 0
        self._nudged_room = None
        room = self.world.get_room(room_id)
        trial = getattr(room, "trial_class", "") if room else ""
        if trial and trial == self.player.player_class:
            self.player.add_status_effect(
                "trial_resonance",
                {"name": "Resonance", "damage_bonus": TRIAL_BONUS,
                 "description": f"+{TRIAL_BONUS} damage in your class's trial"},
                TRIAL_TURNS,
            )
            self.output.write(
                f"[bold magenta]This place resonates with you, "
                f"{self.player.player_class}. +{TRIAL_BONUS} damage for "
                f"{TRIAL_TURNS} turns.[/bold magenta]"
            )
        self._teach_if_ready(room_id)

    def _technique_known(self, via: str) -> bool:
        """Has the player captured any flag that needed this technique?"""
        return any(
            getattr(room, "flag", None) is not None and room.flag.via == via
            and self.world.flag_captured(rid)
            for rid, room in self.world.rooms.items()
        )

    def _lesson(self, flag: Any) -> str:
        if flag.teach:
            return str(flag.teach)
        if flag.via == "grep" and not self._technique_known("grep"):
            # Whichever grep room comes first teaches grep, not only /mnt.
            return (
                "This file is hundreds of lines long — too long to read. "
                "[bold]grep[/bold] searches a file for a word and prints only the "
                f"lines that contain it. Type {flag.command}."
            )
        return ""

    def _teach_if_ready(self, room_id: str) -> None:
        """Give the room's lesson once — but only when nothing is fighting
        here, or the arrival fight would bury it."""
        if not self._guiding():
            return
        flag = self.flag_for(room_id)
        if (
            flag is None or self.world.flag_captured(room_id)
            or self.world.flag_taught(room_id)
            or self.world.get_enemies_in_room(room_id)
        ):
            return
        lesson = self._lesson(flag)
        if not lesson:
            return
        self.world.mark_flag_taught(room_id)
        self.output.write(f"{ECHO} {lesson}")

    def hint(self) -> None:
        """`hint`: a nudge first, then the exact command."""
        room_id = self.player.current_room
        flag = self.flag_for(room_id)
        if flag is None:
            self.output.write(
                f"{ECHO} No flag hides in this directory. "
                "[bold]tree[/bold] shows where you've found them."
            )
            return
        if self.world.flag_captured(room_id):
            self.output.write(
                f"{ECHO} You already captured this room's flag. {self.summary()}"
            )
            return
        asked = self._hints_asked.get(room_id, 0) + 1
        self._hints_asked[room_id] = asked
        if asked == 1:
            self.output.write(f"{ECHO} {flag.nudge}")
        else:
            self.output.write(f"{ECHO} Type {flag.command}")

    def after_command(self, in_combat: bool) -> None:
        """Count commands spent in a room whose flag is still out there; nudge
        once after STUCK_AFTER of them."""
        if in_combat or not self._guiding():
            return
        room_id = self.player.current_room
        self._teach_if_ready(room_id)
        flag = self.flag_for(room_id)
        if flag is None or self.world.flag_captured(room_id) or self._nudged_room == room_id:
            return
        self._idle += 1
        if self._idle >= STUCK_AFTER:
            self._nudged_room = room_id
            self.output.write(
                f"{ECHO} {flag.nudge} [dim](Type [bold]hint[/bold] if you're stuck.)[/dim]"
            )
