"""
SettingsScreen — modal for palette, text speed, and reduce motion settings.
Opens via Ctrl+P, closes with ESC.
"""
import logging
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container
from textual.widgets import Static, RadioSet, RadioButton, Switch, Label

from config.settings_manager import SettingsManager, PALETTE_DISPLAY_NAMES

logger = logging.getLogger(__name__)

# Ordered list of palette keys (must match PALETTE_DISPLAY_NAMES order)
PALETTE_KEYS = ["default", "neon", "amber", "vscode-dark", "pastel", "yonce"]
SPEED_KEYS = ["normal", "fast", "off"]
DIFFICULTY_KEYS = ["easy", "medium", "hard"]


class SettingsScreen(ModalScreen):
    """Full-screen modal for user settings."""

    BINDINGS = [("escape", "dismiss", "Close")]

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-content {
        width: 52;
        height: auto;
        border: round $warning;
        background: $surface;
        padding: 1 2;
    }
    #settings-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $panel;
    }
    .settings-label {
        color: $text-muted;
        text-style: bold;
        padding-top: 1;
        padding-bottom: 0;
    }
    #settings-hint {
        text-align: center;
        color: $text-disabled;
        padding-top: 1;
        border-top: solid $panel;
    }
    .settings-disabled {
        color: $text-disabled;
        opacity: 0.4;
    }
    """

    def __init__(self, manager: SettingsManager):
        super().__init__()
        self._manager = manager

    def compose(self) -> ComposeResult:
        s = self._manager.settings
        current_theme = s.get("theme", "default")
        current_speed = s.get("text_speed", "normal")
        current_motion = s.get("reduce_motion", False)
        current_hints = s.get("hints", True)
        current_difficulty = s.get("difficulty", "medium")

        with Container(id="settings-content"):
            yield Static("⚙️  Settings", id="settings-title")

            yield Label("🎨 Color Palette", classes="settings-label")
            yield RadioSet(
                *[
                    RadioButton(PALETTE_DISPLAY_NAMES[key], value=(key == current_theme))
                    for key in PALETTE_KEYS
                ],
                id="palette-radio",
            )

            yield Label("⌨️  Text Animation Speed", classes="settings-label")
            yield RadioSet(
                RadioButton("Normal", value=(current_speed == "normal")),
                RadioButton("Fast",   value=(current_speed == "fast")),
                RadioButton("Off",    value=(current_speed == "off")),
                id="speed-radio",
            )

            yield Label("🎯 Difficulty", classes="settings-label")
            yield Static("[dim]Scales enemy strength & leveling[/dim]")
            yield RadioSet(
                RadioButton("Easy",   value=(current_difficulty == "easy")),
                RadioButton("Medium", value=(current_difficulty == "medium")),
                RadioButton("Hard",   value=(current_difficulty == "hard")),
                id="difficulty-radio",
            )

            yield Label("Reduce Motion", classes="settings-label")
            yield Static("[dim]Skip intro & all animations[/dim]")
            yield Switch(value=current_motion, id="reduce-motion-switch")

            yield Label("In-game hints", classes="settings-label")
            yield Static("[dim]Show → take/cat/cd command hints while exploring[/dim]")
            yield Switch(value=current_hints, id="hints-switch")

            yield Static(
                "[dim]🔊 Sound Volume — coming soon[/dim]",
                classes="settings-disabled",
            )
            yield Static(
                "Space/Enter select  ·  Tab navigate  ·  ESC close",
                id="settings-hint",
            )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle palette or speed selection."""
        if event.radio_set.id == "palette-radio":
            key = PALETTE_KEYS[event.index]
            self._manager.apply_theme(key)
        elif event.radio_set.id == "speed-radio":
            key = SPEED_KEYS[event.index]
            self._manager.set_text_speed(key)
        elif event.radio_set.id == "difficulty-radio":
            self._manager.set_difficulty(DIFFICULTY_KEYS[event.index])

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle toggles."""
        if event.switch.id == "reduce-motion-switch":
            self._manager.set_reduce_motion(event.value)
        elif event.switch.id == "hints-switch":
            self._manager.set_hints(event.value)

    def action_dismiss(self) -> None:
        """ESC closes and saves."""
        self._manager.save()
        self.dismiss()
