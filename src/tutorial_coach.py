"""The guided tutorial: which step the player is on and the hint for it."""
from src.events import EventType
from utils.debug_tools import debug_log

# Hint id -> the numbered step it belongs to, for the "step N of TOTAL" label.
STEP_NUMBERS = {
    "step1": 1, "step2": 2, "step3": 3, "step4": 4, "step4_fled": 4,
    "step5": 5, "step5_postcombat": 5, "step6": 6, "step6b": 6,
}
TOTAL_STEPS = 6
# Hints that close the tutorial; the frontend drops its pinned guidance.
FINAL_HINTS = ("completed", "skip_summary")


class TutorialCoach:
    """Shows gated tutorial hints and advances the tutorial from combat events."""

    # Fallback if a class ever lacks a starter_weapon in classes.yaml.
    _FALLBACK_WEAPON = "segfault_shield"

    def __init__(self, player, bus):
        self.player = player
        self.bus = bus

    def show_hint(self, hint_type, item_name=None):
        """Show a gated tutorial hint. Text lives in data/tutorial_hints.yaml.

        The weapon name is whatever the player is actually looking at when a
        hint names one: the item the caller passed, else the class's authored
        starter weapon. It used to be a hardcoded class->id map here, which
        silently drifted from classes.yaml.
        """
        if self.player.tutorial_state.get("completed", False):
            return

        from src.data_loader import load_class_data, load_tutorial_hints

        template = load_tutorial_hints().get(hint_type)
        if template is None:
            debug_log(f"No tutorial hint text for '{hint_type}'")
            return

        weapon_name = item_name
        if not weapon_name:
            klass = load_class_data().get(self.player.player_class)
            weapon_name = getattr(klass, "starter_weapon", None) or self._FALLBACK_WEAPON

        player_name = getattr(self.player, "name", "") or "spirit"

        try:
            text = template.format(player_name=player_name, weapon_name=weapon_name)
        except (KeyError, IndexError) as e:
            # An unknown placeholder is a content bug; show the raw line rather
            # than dropping the tutorial step entirely.
            debug_log(f"Tutorial hint '{hint_type}' has a bad placeholder: {e}")
            text = template

        self.bus.emit_event(
            EventType.TUTORIAL_HINT,
            {
                "hint_id": hint_type,
                "text": text,
                "step": STEP_NUMBERS.get(hint_type),
                "total": TOTAL_STEPS,
                "final": hint_type in FINAL_HINTS,
            },
            "TutorialCoach",
        )

        if hint_type == "completed":
            self.player.tutorial_state["completed"] = True

    def current_step(self):
        """Return the hint key for the step the player is currently expected to perform."""
        ts = self.player.tutorial_state or {}
        if not ts.get("first_ls", False):
            return "step1"
        if not ts.get("took_weapon", False):
            return "step2"
        if not ts.get("equipped_weapon", False):
            return "step3"
        if not ts.get("combat_action_taken", False):
            return "step4"
        if not ts.get("navigation_ls", False):
            return "step6"
        if not ts.get("navigation_moved", False):
            return "step6b"
        return None

    def on_combat_ended(self, event):
        """Handle combat end for tutorial post-combat hints (Step 5 post-combat + Step 6)."""
        ts = self.player.tutorial_state
        if ts.get("completed", False):
            return
        if ts.get("combat_action_taken", False) and not ts.get("navigation_ls", False):
            if event.data.get("victory", False):
                self.show_hint("step5_postcombat")

    def on_combat_action_result(self, event):
        """Step 4 gate: first landed attack (typed OR hotkey — both emit this
        event identically) shows the Step 5 hint."""
        ts = self.player.tutorial_state
        if ts.get("completed", False):
            return
        data = event.data or {}
        if data.get("actor") == "player" and data.get("action") == "attack":
            if not ts.get("combat_action_taken", False):
                ts["combat_action_taken"] = True
                self.show_hint("step5")
