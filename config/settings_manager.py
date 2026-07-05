"""
SettingsManager — owns user settings state, theme registration, and persistence.
"""
import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULTS = {
    "theme": "default",
    "text_speed": "normal",
    "reduce_motion": False,
    "hints": True,  # in-game inline affordances (→ take/cat/cd)
    "seen_selection_mode": False,  # combat selection-mode modal: show once ever
    "difficulty": "medium",  # easy | medium | hard — scales enemy stats + XP
}

# Palette definitions: name → (primary, success, error, warning, accent)
PALETTES = {
    "default":    None,  # uses Textual's built-in "textual-dark"
    "neon":       ("#0044ff", "#00ffcc", "#ff3355", "#ffcc00", "#aa00ff"),
    "amber":      ("#508040", "#c8a84b", "#883020", "#f0d060", "#886633"),
    "vscode-dark":("#569cd6", "#4ec9b0", "#f44747", "#dcdcaa", "#c586c0"),
    "pastel":     ("#91caff", "#b3e5b3", "#ffb3b3", "#ffe58f", "#d3adf7"),
    "yonce":      ("#00A7AA", "#98E342", "#FB4384", "#E6DB73", "#FFB1F2"),
}

PALETTE_DISPLAY_NAMES = {
    "default":     "Default",
    "neon":        "Neon",
    "amber":       "Amber",
    "vscode-dark": "VS Code Dark",
    "pastel":      "Pastel",
    "yonce":       "Yoncé",
}


class SettingsManager:
    """Singleton-style manager for user settings."""

    def __init__(self, settings_path: str = "config/user_settings.json"):
        self._path = settings_path
        self.settings: dict = dict(DEFAULTS)
        self._app = None  # set by register_themes()

    def load(self) -> None:
        """Read settings from JSON file, filling missing keys with defaults."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    saved = json.load(f)
                # Merge: saved values override defaults, missing keys get defaults
                for key, default in DEFAULTS.items():
                    self.settings[key] = saved.get(key, default)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not read settings file: {e}. Using defaults.")
                self.settings = dict(DEFAULTS)
        else:
            self.settings = dict(DEFAULTS)

    def register_themes(self, app) -> None:
        """Register custom Theme objects with the Textual app. Call once at startup."""
        from textual.theme import Theme
        self._app = app
        for key, colors in PALETTES.items():
            if colors is None:
                continue  # "default" uses textual-dark, no registration needed
            primary, success, error, warning, accent = colors
            app.register_theme(Theme(
                name=key,
                primary=primary,
                secondary=primary,
                accent=accent,
                success=success,
                warning=warning,
                error=error,
            ))

    def apply_theme(self, name: str) -> None:
        """Switch the active palette. Applies live if app is available."""
        self.settings["theme"] = name
        if self._app is not None:
            textual_name = "textual-dark" if name == "default" else name
            self._app.theme = textual_name

    def set_text_speed(self, speed: str) -> None:
        """Set text animation speed: 'normal', 'fast', or 'off'."""
        self.settings["text_speed"] = speed
        import config.dev_config as dev_cfg
        from utils.typewriter import TypewriterPresets
        # If reduce_motion is on, keep animations disabled regardless of speed
        if self.settings.get("reduce_motion", False):
            dev_cfg.DISABLE_ANIMATIONS = True
            return
        if speed == "off":
            dev_cfg.DISABLE_ANIMATIONS = True
        elif speed == "fast":
            dev_cfg.DISABLE_ANIMATIONS = False
            TypewriterPresets.NARRATIVE.chars_per_second = 120.0
            TypewriterPresets.DIALOGUE.chars_per_second = 200.0
            TypewriterPresets.DRAMATIC.chars_per_second = 80.0
        else:  # normal
            dev_cfg.DISABLE_ANIMATIONS = False
            TypewriterPresets.NARRATIVE.chars_per_second = 35.0
            TypewriterPresets.DIALOGUE.chars_per_second = 60.0
            TypewriterPresets.DRAMATIC.chars_per_second = 20.0

    def set_reduce_motion(self, enabled: bool) -> None:
        """Toggle reduce motion (disables all animations and intro)."""
        self.settings["reduce_motion"] = enabled
        import config.dev_config as dev_cfg
        dev_cfg.DISABLE_ANIMATIONS = enabled
        dev_cfg.SKIP_INTRO = enabled

    def set_hints(self, enabled: bool) -> None:
        """Toggle in-game inline affordance hints (→ take/cat/cd in listings)."""
        self.settings["hints"] = enabled
        import config.dev_config as dev_cfg
        dev_cfg.SHOW_HINTS = enabled

    def set_difficulty(self, mode: str) -> None:
        """Set the difficulty mode (easy/medium/hard) and apply it live."""
        from src import difficulty
        self.settings["difficulty"] = mode if mode in difficulty.MODES else "medium"
        difficulty.set_mode(self.settings["difficulty"])

    def apply_all(self) -> None:
        """Push loaded settings into runtime config. Call once after load()."""
        self.set_hints(self.settings.get("hints", True))
        self.set_difficulty(self.settings.get("difficulty", "medium"))

    def save(self) -> None:
        """Write current settings to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self.settings, f, indent=2)
        except OSError as e:
            logger.error(f"Could not save settings: {e}")
