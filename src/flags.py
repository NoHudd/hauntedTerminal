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

    def on_file_read(self, item_id: str, already_saved: bool = False) -> bool:
        """A file was read in the current room. Capture its flag if it is the
        room's flag file and not yet captured. Returns True on capture."""
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
        if not already_saved:
            try:
                self._save()
                self.output.write("[dim green]✓ Checkpoint saved.[/dim green]")
            except Exception as e:
                debug_log(f"Checkpoint save after flag in {room_id} failed: {e}")
                self.output.write(f"[dim yellow]⚠ Checkpoint save failed: {e}[/dim yellow]")
        return True
