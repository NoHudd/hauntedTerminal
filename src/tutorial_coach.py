"""The guided tutorial: which step the player is on and the hint for it."""
from src import room_paths
from src.events import EventType
from utils.debug_tools import debug_log

# Hint id -> the numbered step it belongs to, for the "step N of TOTAL" label.
STEP_NUMBERS = {
    "step1": 1, "step2": 2, "step3": 3,
    "step4": 4, "step4_fled": 4, "step5": 4,
    "step5_postcombat": 5, "step_hidden": 6, "step_cat": 7,
    "step_ps": 8, "step_up": 9, "step6": 10, "step6b": 11,
}
TOTAL_STEPS = 11
# Hints that point at a section of the output the frontend should draw the eye to.
HIGHLIGHTS = {"step6b": "Directories"}
# Hints that close the tutorial; the frontend drops its pinned guidance.
FINAL_HINTS = ("completed", "skip_summary")


class TutorialCoach:
    """Shows gated tutorial hints and advances the tutorial from combat events."""

    # Fallback if a class ever lacks a starter_weapon in classes.yaml.
    _FALLBACK_WEAPON = "segfault_shield"

    def __init__(self, player, world, bus):
        self.player = player
        self.world = world
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
        directories = self._visible_directories()
        example_dir = room_paths.basename(room_paths.room_path(directories[0])) if directories else "var"

        try:
            text = template.format(
                player_name=player_name,
                weapon_name=weapon_name,
                location=room_paths.room_path(self.player.current_room),
                example_dir=example_dir,
            )
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
                "highlight": HIGHLIGHTS.get(hint_type),
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
        if not ts.get("ls_a_used", False):
            return "step5_postcombat"
        if not ts.get("lore_read", False):
            return "step_hidden"
        if not ts.get("ps_used", False):
            return "step_cat"
        if not ts.get("pwd_used", False):
            return "step_ps"
        if not ts.get("went_up", False):
            return "step6" if self._visible_directories() else "step_up"
        if not ts.get("navigation_ls", False):
            return "step6"
        if not ts.get("navigation_moved", False):
            return "step6b"
        return None

    def _visible_directories(self):
        """Discovered rooms directly below the player's current directory."""
        here = room_paths.room_path(self.player.current_room)
        return [c for c in room_paths.children_of(here) if self.world.is_discovered(c)]

    def _active(self):
        return not self.player.tutorial_state.get("completed", False)

    # --- progression: commands report what happened, the coach decides ------

    def after_ls(self, weapon_found, weapon_id, has_directories, show_all=False):
        """ls: the first one points at the weapon; the first -a after combat
        reveals the hidden lore file; after pwd, it finds the way on."""
        ts = self.player.tutorial_state
        if not self._active():
            return
        if not ts.get("first_ls", False):
            ts["first_ls"] = True
            if weapon_found:
                ts["found_weapon"] = True
                self.show_hint("step2", weapon_id)
            return
        if show_all and ts.get("combat_action_taken", False) and not ts.get("ls_a_used", False):
            ts["ls_a_used"] = True
            if not ts.get("lore_read", False):
                self.show_hint("step_hidden")
            return
        if ts.get("pwd_used", False) and not ts.get("navigation_ls", False):
            if has_directories:
                ts["went_up"] = True
                ts["navigation_ls"] = True
                self.show_hint("step6b")
            else:
                self.show_hint("step_up")

    def after_lore_read(self, story_beat):
        """A cat that fired a story flag: the memory-restore autosave IS the
        checkpoint the tutorial is teaching, so this is the step's gate."""
        ts = self.player.tutorial_state
        if not (self._active() and ts.get("combat_action_taken", False)):
            return
        if story_beat and not ts.get("lore_read", False):
            ts["lore_read"] = True
            self.show_hint("step_cat")

    def after_ps(self):
        ts = self.player.tutorial_state
        if self._active() and ts.get("lore_read", False) and not ts.get("ps_used", False):
            ts["ps_used"] = True
            self.show_hint("step_ps")

    def after_pwd(self):
        ts = self.player.tutorial_state
        if not (self._active() and ts.get("ps_used", False)) or ts.get("pwd_used", False):
            return
        ts["pwd_used"] = True
        if self._visible_directories():
            ts["went_up"] = True
            self.show_hint("step6")
        else:
            self.show_hint("step_up")

    def after_move(self):
        """A successful cd: the first after pwd lands somewhere new; the first
        after the highlighted listing finishes the tutorial."""
        ts = self.player.tutorial_state
        if not self._active():
            return
        if ts.get("navigation_ls", False) and not ts.get("navigation_moved", False):
            ts["navigation_moved"] = True
            self.show_hint("completed")
        elif ts.get("pwd_used", False) and not ts.get("went_up", False):
            ts["went_up"] = True
            self.show_hint("step6")

    def on_combat_ended(self, event):
        """Handle combat end for tutorial post-combat hints (Step 5 post-combat + Step 6)."""
        ts = self.player.tutorial_state
        if ts.get("completed", False):
            return
        if ts.get("combat_action_taken", False) and not ts.get("ps_used", False):
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
