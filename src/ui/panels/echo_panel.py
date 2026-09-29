"""EchoPanel — the tutorial guide's current instruction, pinned above the input.

Hints used to scroll through the output with everything else, where the next
room listing or the battle panel could push them out of sight. The panel keeps
the one thing the player should do next on screen until the next step replaces
it, and disappears when the tutorial ends.
"""
from __future__ import annotations

import re

from textual.widgets import Static

_ECHO_PREFIX = re.compile(r"^\[bold green\]ECHO>\[/bold green\]\s*")


class EchoPanel(Static):
    """Shows the latest tutorial hint; hidden when there is none."""

    def on_mount(self) -> None:
        self.clear()

    def show_hint(self, text: str, step: int | None, total: int) -> None:
        self.border_title = f"🗨 ECHO · step {step} of {total}" if step else "🗨 ECHO"
        self.update(_ECHO_PREFIX.sub("", text))
        self.display = True

    def clear(self) -> None:
        self.update("")
        self.display = False
