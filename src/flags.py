"""Room flags: capture, counts, and the guidance that leads players to them.

Each room may declare a flag (docs/ROOM_FLAGS_SPEC.md). Commands report what
the player did (read a file, entered a room, typed a command); this service
decides whether a flag was captured and what Echo should say.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src import room_paths
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
        return True

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
        if not self._guiding():
            return
        flag = self.flag_for(room_id)
        if (
            flag is None or not flag.teach
            or self.world.flag_captured(room_id) or self.world.flag_taught(room_id)
        ):
            return
        self.world.mark_flag_taught(room_id)
        self.output.write(f"{ECHO} {flag.teach}")

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
        flag = self.flag_for(room_id)
        if flag is None or self.world.flag_captured(room_id) or self._nudged_room == room_id:
            return
        self._idle += 1
        if self._idle >= STUCK_AFTER:
            self._nudged_room = room_id
            self.output.write(
                f"{ECHO} {flag.nudge} [dim](Type [bold]hint[/bold] if you're stuck.)[/dim]"
            )
