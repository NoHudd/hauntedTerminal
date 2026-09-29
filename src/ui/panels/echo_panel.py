"""EchoPanel — the tutorial guide's current instruction, pinned above the input.

Hints used to scroll through the output with everything else, where the next
room listing or the battle panel could push them out of sight. The panel keeps
the one thing the player should do next on screen until the next step replaces
it, and disappears when the tutorial ends.
"""
from __future__ import annotations

import re

from textual.timer import Timer
from textual.widgets import Static

_ECHO_PREFIX = re.compile(r"^\[bold green\]ECHO>\[/bold green\]\s*")


class EchoPanel(Static):
    """Shows the latest tutorial hint; hidden when there is none."""

    FLASH_PULSES = 3
    FLASH_SECONDS = 0.35

    _flash_timer: Timer | None = None

    def on_mount(self) -> None:
        self.clear()

    def show_hint(
        self, text: str, step: int | None, total: int, reduce_motion: bool = False,
    ) -> None:
        appearing = not self.display
        self.border_title = f"🗨 ECHO · step {step} of {total}" if step else "🗨 ECHO"
        self.update(_ECHO_PREFIX.sub("", text))
        self.display = True
        if appearing:
            self._flash(reduce_motion)

    def clear(self) -> None:
        self._stop_flash()
        self.update("")
        self.display = False

    def _flash(self, reduce_motion: bool) -> None:
        """Draw the eye to the panel when the tutorial starts: pulse its
        highlight a few times, then settle. With reduce motion, hold it once."""
        self._stop_flash()
        # One entry per tick: is the highlight on? Same total length either way.
        if reduce_motion:
            frames = [True] * (2 * self.FLASH_PULSES - 1) + [False]
        else:
            frames = [False, True] * (self.FLASH_PULSES - 1) + [False]
        self.set_class(True, "echo-flash")

        def next_frame() -> None:
            if not frames:
                self._stop_flash()
                return
            on = frames.pop(0)
            if on != self.has_class("echo-flash"):
                self.set_class(on, "echo-flash")

        self._flash_timer = self.set_interval(self.FLASH_SECONDS, next_frame)

    def _stop_flash(self) -> None:
        if self._flash_timer is not None:
            self._flash_timer.stop()
            self._flash_timer = None
        if self.has_class("echo-flash"):
            self.set_class(False, "echo-flash")
