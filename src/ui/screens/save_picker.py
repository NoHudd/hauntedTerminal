"""
SavePickerScreen — LOAD GAME's run picker, and NEW GAME's "slots full, pick a
run to replace". Runs listed on the left; the highlighted run's class art and
details on the right. ↑/↓ choose, Enter confirm, d delete (y/n), Esc back.

The screen decides nothing: it answers with the commands a typed player can
send ("pick <runId>", "delete <runId>", "back") and the engine re-sends the
picker (after a delete) or moves on. Card art comes from
assets/sprites/ui/class_<class>.png via SpriteStore, as on the class picker.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from rich.console import Group
from rich.markup import escape
from rich.padding import Padding
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Static

from src.scene.effects import bob_offset
from src.scene.sprite_store import SpriteStore, to_renderable

_ART_PX = 32
_BOB_TICK_SECONDS = 0.2

CLASS_ICONS = {"guardian": "🛡", "weaver": "✨", "shaman": "🌿"}


def saved_ago(saved_at: float, now: float | None = None) -> str:
    """'just now', '5m ago', '2h ago', '3d ago'."""
    seconds = max(0, int((time.time() if now is None else now) - saved_at))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


class SavePickerScreen(ModalScreen):
    """List + preview run picker."""

    BINDINGS = [
        Binding("up", "move(-1)", "Up", show=False),
        Binding("k", "move(-1)", "Up", show=False),
        Binding("down", "move(1)", "Down", show=False),
        Binding("j", "move(1)", "Down", show=False),
        Binding("enter", "confirm", "Choose", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("y", "answer_delete(True)", show=False),
        Binding("n", "answer_delete(False)", show=False),
        Binding("escape", "back", "Back", show=False),
    ]

    CSS = """
    SavePickerScreen {
        align: center middle;
        background: $background;  /* opaque: hide the typed list behind the modal */
    }
    #save-picker {
        width: auto;
        height: auto;
    }
    #save-heading {
        width: 100%;
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    #save-row {
        width: auto;
        height: auto;
    }
    #save-list {
        width: 58;
        height: auto;
        min-height: 11;
        border: round $panel;
        padding: 0 1;
    }
    #save-preview {
        width: 38;
        height: auto;
        border: round $accent;
        padding: 0 1;
        margin-left: 1;
    }
    #save-hint {
        width: 100%;
        text-align: center;
        color: $text-disabled;
        padding-top: 1;
    }
    """

    _CONFIRM_GRACE_SECONDS = 0.25  # swallow the Enter that opened this screen

    def __init__(self, mode: str, runs: list[dict[str, Any]], legacy_count: int,
                 on_command: Callable[[str], None], reduce_motion: bool = False):
        super().__init__()
        self._mode = mode
        self._runs = runs
        self._legacy = legacy_count
        self._on_command = on_command
        self._reduce_motion = reduce_motion
        self._index = 0
        self._confirming_delete = False
        self._answered = False
        self._store = SpriteStore()
        self._mounted_at = 0.0
        self._bob_timer = None
        self._bob_start = 0.0

    def compose(self) -> ComposeResult:
        heading = (
            "CONTINUE A RUN" if self._mode == "continue"
            else "SLOTS FULL — PICK A RUN TO REPLACE"
        )
        with Vertical(id="save-picker"):
            yield Static(heading, id="save-heading")
            with Horizontal(id="save-row"):
                yield Static(id="save-list")
                if self._runs:
                    yield Static(id="save-preview")
            yield Static(id="save-hint")

    def on_mount(self) -> None:
        self._mounted_at = time.monotonic()
        self._bob_start = self._mounted_at
        self._draw()
        if self._runs and not self._reduce_motion:
            self._bob_timer = self.set_interval(_BOB_TICK_SECONDS, self._bob_tick)

    def on_unmount(self) -> None:
        if self._bob_timer is not None:
            self._bob_timer.stop()
            self._bob_timer = None

    # -- rendering ------------------------------------------------------------

    def list_text(self) -> str:
        if not self._runs:
            lines = ["", "No saves available"]
            if self._legacy:
                noun = "save is" if self._legacy == 1 else "saves are"
                lines.append(
                    f"[dim]({self._legacy} old {noun} from an earlier version, "
                    "kept in saves/legacy/)[/dim]"
                )
            return "\n".join(lines)
        lines = []
        for i, run in enumerate(self._runs):
            icon = CLASS_ICONS.get(run["playerClass"], "•")
            name = escape(f"{run['playerName'][:10]:<10}")
            room = escape(f"{run['roomPath'][:12]:<12}")
            cls = escape(f"{run['playerClass'].title()[:8]:<8}")
            diff = escape(f"{run['difficulty'][:6]:<6}")
            mark = " ✓" if run["cleared"] else ""
            body = f"{icon} {name} {cls} · {diff} {room} L{run['level']}{mark}"
            lines.append(
                f"[reverse bold]▶ {body}[/reverse bold]" if i == self._index else f"  {body}"
            )
        return "\n".join(lines)

    def preview(self, bob: int = 0) -> Group:
        run = self._runs[self._index]
        art = to_renderable(
            self._store.get_sprite("ui", f"class_{run['playerClass']}", _ART_PX, _ART_PX)
        )
        # bob shifts the art 1 row up/down without changing the panel height.
        art = Padding(art, (bob, 0, 1 - bob, 0))
        details = Text.assemble(
            (f"{run['playerName'].upper()} · {run['playerClass'].upper()}\n", "bold"),
            f"{run['difficulty']} · Level {run['level']}\n",
            f"{run['roomPath']}\n",
            f"HP {run['health']}/{run['maxHealth']}\n",
            (f"saved {saved_ago(run['savedAt'])}", "dim"),
            ("\n✓ Cleared" if run["cleared"] else "", "bold green"),
            justify="center",
        )
        return Group(art, details)

    def hint_text(self) -> str:
        if self._confirming_delete:
            name = escape(self._runs[self._index]["playerName"])
            return f"[bold yellow]Delete {name}'s run?[/bold yellow]  y / n"
        if not self._runs:
            return "esc back"
        enter = "continue" if self._mode == "continue" else "replace"
        delete = " · d delete" if self._mode == "continue" else ""
        return f"↑/↓ choose · enter {enter}{delete} · esc back"

    def _draw(self, bob: int = 0) -> None:
        try:
            self.query_one("#save-list", Static).update(self.list_text())
            self.query_one("#save-hint", Static).update(self.hint_text())
            if self._runs:
                self.query_one("#save-preview", Static).update(self.preview(bob))
        except NoMatches:
            # Not mounted yet (or under unit test): on_mount draws again.
            pass

    def _bob_tick(self) -> None:
        if not self.is_mounted or self._answered:
            return
        self._draw(bob=bob_offset(time.monotonic() - self._bob_start))

    # -- actions --------------------------------------------------------------

    def action_move(self, delta: int) -> None:
        if not self._runs or self._confirming_delete:
            return
        self._index = (self._index + delta) % len(self._runs)
        self._draw()

    def action_confirm(self) -> None:
        if self._confirming_delete:
            return
        if self._mounted_at and time.monotonic() - self._mounted_at < self._CONFIRM_GRACE_SECONDS:
            return
        if not self._runs:
            self._send("back")
            return
        self._send(f"pick {self._runs[self._index]['runId']}")

    def action_delete(self) -> None:
        if self._mode != "continue" or not self._runs or self._confirming_delete:
            return
        self._confirming_delete = True
        self._draw()

    def action_answer_delete(self, yes: bool) -> None:
        if not self._confirming_delete:
            return
        self._confirming_delete = False
        if yes:
            self._send(f"delete {self._runs[self._index]['runId']}")
            return
        self._draw()

    def action_back(self) -> None:
        if self._confirming_delete:
            self._confirming_delete = False
            self._draw()
            return
        self._send("back")

    def _send(self, command: str) -> None:
        # One answer per screen: the engine replaces or closes this screen.
        if self._answered:
            return
        self._answered = True
        self._on_command(command)
