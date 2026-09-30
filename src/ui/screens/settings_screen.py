"""
SettingsScreen — one row per setting: ↑/↓ choose a row, ←/→ change its value.

Changes apply live (the palette recolors as you cycle); Esc writes
config/user_settings.json and closes. Opened from the title menu's SETTINGS
entry and from Ctrl+P in-game.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Static

from config.settings_manager import PALETTE_DISPLAY_NAMES, SettingsManager

logger = logging.getLogger(__name__)

# Ordered list of palette keys (must match PALETTE_DISPLAY_NAMES order)
PALETTE_KEYS = ["default", "neon", "amber", "vscode-dark", "pastel", "yonce"]
SPEED_KEYS = ["normal", "fast", "off"]


@dataclass(frozen=True)
class SettingRow:
    """One setting: where it lives, what it offers, and how to apply a value."""
    key: str                  # key in SettingsManager.settings
    label: str
    description: str
    values: tuple[Any, ...]
    names: tuple[str, ...]    # display name for each value
    apply: Callable[[SettingsManager, Any], None]


ROWS: tuple[SettingRow, ...] = (
    SettingRow(
        "theme", "Color palette", "Recolor the whole interface.",
        tuple(PALETTE_KEYS), tuple(PALETTE_DISPLAY_NAMES[k] for k in PALETTE_KEYS),
        SettingsManager.apply_theme,
    ),
    SettingRow(
        "text_speed", "Text speed", "How fast story text types out.",
        tuple(SPEED_KEYS), ("Normal", "Fast", "Off"),
        SettingsManager.set_text_speed,
    ),
    SettingRow(
        "reduce_motion", "Reduce motion", "Skip the intro and all animations.",
        (False, True), ("Off", "On"),
        SettingsManager.set_reduce_motion,
    ),
    SettingRow(
        "hints", "In-game hints",
        "Show take/cat/cd hints while exploring and a heal reminder when HP is low.",
        (True, False), ("On", "Off"),
        SettingsManager.set_hints,
    ),
)


class SettingsScreen(ModalScreen):
    """Arrow-row settings modal."""

    BINDINGS = [
        Binding("up", "move(-1)", "Up", show=False),
        Binding("k", "move(-1)", "Up", show=False),
        Binding("down", "move(1)", "Down", show=False),
        Binding("j", "move(1)", "Down", show=False),
        Binding("left", "change(-1)", "Previous value", show=False),
        Binding("h", "change(-1)", "Previous value", show=False),
        Binding("right", "change(1)", "Next value", show=False),
        Binding("l", "change(1)", "Next value", show=False),
        Binding("escape", "close", "Back", show=False),
    ]

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-content {
        width: 60;
        height: auto;
        border: round $warning;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, manager: SettingsManager,
                 on_close: Callable[[], None] | None = None):
        super().__init__()
        self._manager = manager
        self._on_close = on_close
        self._index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-content"):
            yield Static(id="settings-body")

    def on_mount(self) -> None:
        self._draw()

    # -- rendering ------------------------------------------------------------

    def _value_index(self, row: SettingRow) -> int:
        current = self._manager.settings.get(row.key, row.values[0])
        try:
            return row.values.index(current)
        except ValueError:
            return 0

    def value_name(self, row: SettingRow) -> str:
        return row.names[self._value_index(row)]

    def _draw(self) -> None:
        lines = ["[bold]⚙  Settings[/bold]", ""]
        for i, row in enumerate(ROWS):
            name = self.value_name(row)
            if i == self._index:
                lines.append(f"[reverse bold] ▶ {row.label:<16} ◀ {name} ▶ [/reverse bold]")
            else:
                lines.append(f"[dim]   {row.label:<16}   {name}[/dim]")
        lines += [
            "",
            f"[dim italic]{ROWS[self._index].description}[/dim italic]",
            "",
            "[dim]↑/↓ choose · ←/→ change · esc back[/dim]",
        ]
        try:
            self.query_one("#settings-body", Static).update("\n".join(lines))
        except NoMatches:
            # Not mounted yet (or under unit test): on_mount draws again.
            pass

    # -- actions --------------------------------------------------------------

    def action_move(self, delta: int) -> None:
        self._index = (self._index + delta) % len(ROWS)
        self._draw()

    def action_change(self, delta: int) -> None:
        row = ROWS[self._index]
        value = row.values[(self._value_index(row) + delta) % len(row.values)]
        row.apply(self._manager, value)
        self._draw()

    def action_close(self) -> None:
        """Esc writes the settings file and goes back."""
        self._manager.save()
        self.dismiss()
        if self._on_close is not None:
            self._on_close()
