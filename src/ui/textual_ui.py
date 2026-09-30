#!/usr/bin/env python3
"""
Clean Textual UI Implementation for HFSE

This is a refactored version of the UI that provides:
- Enhanced combat system with visual feedback
- Dynamic hotkey system
- Clean panel organization
- Event-driven architecture

Author: NoHudd
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static, Input
from textual.containers import Container, VerticalScroll, Horizontal, Vertical
from textual.reactive import var
from rich.text import Text

from src.ui.ui_interface import UIInitializationError, UIStateError
from engine.events import EventBus, EventType
from src.game_states import GameState, UIState
from src.state_manager import StateManager
from engine.view_models import AttackView, CombatView, InventoryView, RoomView, StatsView
from config.dev_config import SKIP_INTRO

from src.ui.panels.echo_panel import EchoPanel
from src.ui.panels.inventory_panel import InventoryPanel
from src.ui.panels.stats_panel import StatsPanel
from src.ui.panels.scene_view import SceneView
from src.ui.screens.combat_hint import CombatModeHintScreen
from src.ui.screens.log_viewer import LogViewerScreen
from src.ui.screens.quit_confirm import QuitConfirmScreen
from src.ui.screens.selection_screen import SelectionCard, SelectionScreen
from src.ui.screens.settings_screen import SettingsScreen
from src.ui.combat_log import render_combat_output
from src.ui.command_input import CommandInput
from src.ui.command_suggester import CommandSuggester
from src.ui.endings import FinaleReveal
from src.ui.title_menu import TitleMenu
from config.settings_manager import SettingsManager

import logging
import os
import threading
from dataclasses import replace
from typing import Optional

logger = logging.getLogger(__name__)


class TextualGameUI(App):
    """Enhanced Textual-based game UI with improved combat system."""

    CSS_PATH = os.path.join(os.path.dirname(__file__), "ui.css")
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        # Ctrl+Q and Ctrl+C both route through the same confirmation the `quit`
        # command uses. Textual binds ctrl+q to an immediate exit by default,
        # which silently discarded unsaved progress.
        Binding("ctrl+q", "request_quit", "Quit", key_display="ctrl + q", priority=True),
        Binding("ctrl+c", "request_quit", "Quit", show=False, priority=True),
        Binding("ctrl+p", "open_settings", "Settings", key_display="ctrl + p"),
        Binding("l", "toggle_log_viewer", "Show/Hide Logs", key_display="L"),
        # Priority, so it reaches the app even while the command box has focus.
        Binding("f12", "toggle_log_viewer", "Logs", show=False, priority=True),
        Binding("f5", "restart_game", "Restart Game", key_display="F5"),
    ]

    # =====================================
    # INITIALIZATION & SETUP
    # =====================================

    def __init__(self, *args, **kwargs):
        # Initialize state BEFORE calling super().__init__()
        # Store view data (dicts) instead of backend objects
        self._settings_manager = SettingsManager()
        self._settings_manager.load()
        self._player_view: Optional[StatsView] = None
        self._inventory_view: Optional[InventoryView] = None
        self._room_view: Optional[RoomView] = None
        self._combat_view: Optional[CombatView] = None
        self._combat_log = []  # Store recent combat actions
        self._bound_combat_keys = []  # Track bound combat keys
        self._available_attacks: list[AttackView] = []
        self._combat_hint_shown = False  # Track if selection mode hint was shown
        self._player_ref = None  # Set by game engine after player creation; used for tutorial checks
        self._world_ref = None   # Set by game engine; used by autocomplete suggester
        self._room_aliases_ref: dict = {}  # Populated from CommandHandler for cd autocomplete

        self._title_menu = TitleMenu(self)
        self._finale = FinaleReveal(self)

        super().__init__(*args, **kwargs)
        self.ui_state = UIState.INITIALIZING
        # A private bus until the engine hands over its own via attach_bus;
        # lets the app run standalone (e.g. under Pilot) with nothing listening.
        bus = EventBus()
        self.bus = bus
        self.state_manager = StateManager(bus)
        self._setup_event_subscriptions()

    def attach_bus(self, bus: EventBus, state_manager: StateManager) -> None:
        """Move this UI's subscriptions onto the owning engine's bus."""
        self._teardown_event_subscriptions()
        self.bus = bus
        self.state_manager = state_manager
        self._setup_event_subscriptions()

    _EVENT_HANDLERS = [
        (EventType.GAME_STARTED, "_on_game_started"),
        (EventType.GAME_OVER, "_on_game_over"),
        (EventType.PLAYER_CREATED, "_on_player_created"),
        (EventType.PLAYER_STATS_CHANGED, "_on_player_stats_changed"),
        (EventType.PLAYER_INVENTORY_CHANGED, "_on_player_inventory_changed"),
        (EventType.ROOM_ENTERED, "_on_room_entered"),
        (EventType.UI_STATE_CHANGED, "_on_ui_state_changed"),
        (EventType.COMBAT_STARTED, "_on_combat_started"),
        (EventType.COMBAT_FRAME_UPDATED, "_on_combat_frame_updated"),
        (EventType.COMBAT_ACTION_RESULT, "_on_combat_action_result"),
        (EventType.COMBAT_ENDED, "_on_combat_ended"),
        (EventType.ENEMY_DEFEATED, "_on_enemy_defeated"),
        (EventType.GAME_WON, "_on_game_won"),
        (EventType.GAME_QUIT, "_on_game_quit"),
        (EventType.QUIT_CONFIRM_REQUESTED, "_on_quit_confirm_requested"),
        (EventType.TUTORIAL_HINT, "_on_tutorial_hint"),
    ]

    def _setup_event_subscriptions(self):
        """Subscribe to relevant game events."""
        for event_type, handler_name in self._EVENT_HANDLERS:
            self.bus.subscribe(event_type, getattr(self, handler_name))

    def _teardown_event_subscriptions(self):
        for event_type, handler_name in self._EVENT_HANDLERS:
            self.bus.unsubscribe(event_type, getattr(self, handler_name))

    def compose(self) -> ComposeResult:
        """Create the main UI layout."""
        yield Static(id="header")
        with Horizontal():
            with Vertical(id="main-area"):
                yield SceneView(id="scene-view")
                with VerticalScroll(id="output-panel"):
                    yield Static(self.output_content, id="output-display")
            with Container(id="sidebar"):
                yield InventoryPanel(id="inventory-panel")
                yield StatsPanel(id="stats-panel")
        yield EchoPanel(id="echo-panel")
        yield Footer()
        yield CommandInput(placeholder="Enter command...", id="input-field")

    def on_mount(self) -> None:
        """Initialize the UI when mounted."""
        try:
            # Store panel references
            self._inv_panel = self.query_one("#inventory-panel", InventoryPanel)
            self._stats_panel = self.query_one("#stats-panel", StatsPanel)
            self._scene_view = self.query_one("#scene-view", SceneView)
            self._echo_panel = self.query_one("#echo-panel", EchoPanel)

            # Set panel titles
            self._inv_panel.border_title = "📦 Inventory"
            self._stats_panel.border_title = "📊 Stats"

            self.ui_state = UIState.READY
            # Widget mutation is only safe from the thread Textual runs on.
            # Game logic runs off it (the game-over animation, the intro
            # typewriter), so the UIProtocol methods below marshal back here.
            self._ui_thread_id = threading.get_ident()
            self._settings_manager.register_themes(self)
            self._settings_manager.apply_theme(self._settings_manager.settings["theme"])
            self._settings_manager.set_text_speed(self._settings_manager.settings["text_speed"])
            self._settings_manager.set_reduce_motion(self._settings_manager.settings["reduce_motion"])
            self._settings_manager.set_hints(self._settings_manager.settings["hints"])
            self._update_all_panels_to_defaults()

            # Attach context-aware autocomplete to the input field (always)
            input_widget = self.query_one("#input-field", CommandInput)
            input_widget.suggester = CommandSuggester(
                get_player=lambda: self._player_ref,
                get_world=lambda: self._world_ref,
                get_aliases=lambda: self._room_aliases_ref,
            )
            input_widget.can_complete = lambda: not self.state_manager.is_in_combat()

            # Display title screen with arrow-key main menu.
            # SKIP_INTRO bypasses the typewriter but keeps the navigable menu.
            self._display_title_screen(skip_typewriter=SKIP_INTRO)

            self.bus.emit_event(EventType.UI_READY, {}, "TextualGameUI")
            logger.info("TextualGameUI mounted successfully")
        except Exception as e:
            self.ui_state = UIState.ERROR
            logger.error(f"Error mounting TextualGameUI: {e}")
            raise UIInitializationError(f"Failed to initialize UI: {e}")

    def shutdown(self) -> None:
        """Clean shutdown of UI resources."""
        try:
            self.ui_state = UIState.SHUTTING_DOWN
            self._teardown_event_subscriptions()
            logger.info("TextualGameUI shutdown complete")
        except Exception as e:
            logger.error(f"Error during UI shutdown: {e}")

    # =====================================
    # REACTIVE VARIABLES & WATCHERS
    # =====================================

    header_content = var("Haunted Terminal")
    output_content = var("")
    message_history = []
    max_messages = 100

    def watch_header_content(self, content: str) -> None:
        """Update header when content changes."""
        if self.query("#header"):
            self.query_one("#header").update(Text(content, justify="center", style="bold cyan"))

    def watch_output_content(self, content: str) -> None:
        """Update main output when content changes."""
        if self.query("#output-display"):
            self.query_one("#output-display").update(content)

    # =====================================
    # EVENT HANDLERS
    # =====================================

    def _on_game_started(self, event):
        """Handle game started event."""
        # Reset all UI state when game starts/restarts
        self._reset_ui_state()

        # State is managed by StateManager, not UI
        # Extract view data from event
        if 'stats' in event.data:
            self._player_view = StatsView.from_dict(event.data['stats'])
        if 'inventory' in event.data:
            self._inventory_view = InventoryView.from_dict(event.data['inventory'])
        self._stats_panel.update_stats(self._player_view)

    def _reset_ui_state(self, leave_battle: bool = True):
        """Reset all UI state - called when game starts or restarts.

        leave_battle=False keeps the fight on the scene: after a death the
        scene drains from the battle straight to black, never via the room.
        """
        logger.debug("Resetting UI state")

        # Clear all view data
        self._player_view = None
        self._inventory_view = None
        self._room_view = None
        self._combat_view = None

        # Clear combat data
        self._combat_log.clear()
        self._available_attacks = []

        self._echo_panel.clear()

        self.remove_class("combat-active")
        if leave_battle:
            self._scene_view.end_battle()

        # Unbind any combat hotkeys
        self._unbind_combat_hotkeys()

        # Set to exploring game state styling
        self._apply_game_state_styling("exploring")

        logger.debug("UI state reset complete")

    def _on_game_over(self, event):
        """A death drains the scene and shows the GAME OVER card; a restart
        goes back to the title."""
        reason = event.data.get("reason")
        player_view = self._player_view
        self._reset_ui_state(leave_battle=reason != "defeat")

        if reason == "restart":
            self._display_title_screen()
            return
        if reason != "defeat":
            return

        # The card names the player; the reset above cleared the view it reads.
        self._player_view = player_view
        self._scene_view.play_death(
            reduce_motion=bool(self._settings_manager.settings.get("reduce_motion", False))
        )

        # CommandHandler triggers the particle animation (2.5s).
        # Focus the input once the animation's final frame (the choices) is up.
        # Dynamic read — settings_manager mutates dev_cfg.DISABLE_ANIMATIONS at runtime.
        import config.dev_config as _dev_cfg
        delay = 0.0 if _dev_cfg.DISABLE_ANIMATIONS else 2.6
        if delay > 0:
            self.set_timer(delay, self.display_game_over)
        else:
            self.display_game_over()

    def _on_player_created(self, event):
        """Handle player created event."""
        self._player_view = StatsView.from_dict(event.data)
        self._stats_panel.update_stats(self._player_view)

    def _on_player_stats_changed(self, event):
        """Handle player stats changed event."""
        self._player_view = StatsView.from_dict(event.data)
        self._stats_panel.update_stats(self._player_view)
        if self.state_manager.is_in_combat():
            self._update_combat_panels()

    def _on_player_inventory_changed(self, event):
        """Handle player inventory changed event."""
        self._inventory_view = InventoryView.from_dict(event.data)
        self._inv_panel.update_inventory(self._inventory_view)

    def _on_room_entered(self, event):
        """Handle room entered event with enhanced theming."""
        if 'room' in event.data:
            self._room_view = RoomView.from_dict(event.data['room'])
            room_name = self._room_view.name
            self._scene_view.show_explore(self._room_view)

            # Apply dynamic room theming using room view data
            self._apply_room_theme(room_name, self._room_view)

            # Apply exploring game state
            self._apply_game_state_styling("exploring")

    # States where the player is picking difficulty/class/name — the game panels
    # (scene, inventory, stats, combat) carry no information yet, so the output
    # panel takes the whole screen (input stays for typing the choice).
    _SELECTION_STATES = {
        "waiting_for_difficulty",
        "waiting_for_class",
        "tutorial_name_input",
    }

    def _on_ui_state_changed(self, event):
        """Handle UI state changed event - trigger UI styling changes only."""
        new_state = str(event.data.get('new_state'))
        if new_state in self._SELECTION_STATES:
            self.add_class("selection-mode")
        else:
            self.remove_class("selection-mode")

        # Art-card pickers for difficulty/class; name entry stays typed.
        self._close_picker()
        if new_state == "waiting_for_difficulty":
            self._open_picker("Choose your difficulty", self._difficulty_cards())
        elif new_state == "waiting_for_class":
            self._open_picker("Choose your class", self._class_cards())

    # -- art-card pickers -------------------------------------------------------

    _picker: SelectionScreen | None = None

    def _open_picker(self, heading: str, cards: list) -> None:
        def on_pick(card: SelectionCard) -> None:
            self.bus.emit_event(
                EventType.COMMAND_ENTERED,
                {"command": card.command},
                "SelectionScreen",
            )

        reduce_motion = bool(self._settings_manager.settings.get("reduce_motion", False))
        self._picker = SelectionScreen(heading, cards, on_pick, reduce_motion=reduce_motion)
        # Defer the push past the in-flight key event: pushing synchronously lets
        # the SAME Enter that triggered this state change hit the new screen's
        # "enter" binding and auto-confirm card 1 (observed: menu→easy in 1 ms).
        self.call_after_refresh(self.push_screen, self._picker)

    def _close_picker(self) -> None:
        if self._picker is not None:
            try:
                if self._picker.is_current or self._picker in self.screen_stack:
                    self._picker.dismiss()
            except Exception as e:
                logger.debug(f"Picker dismiss failed: {e}")
            self._picker = None

    @staticmethod
    def _difficulty_cards() -> list:
        from src.difficulty import MODES
        info = {
            "easy":   ("🌱\nGentler enemies, faster leveling.\nFor learning the ropes.", "green"),
            "medium": ("⚖\nThe intended, balanced challenge.", "yellow"),
            "hard":   ("🔥\nTougher enemies, longer fights;\nyou level slower.", "red"),
        }
        return [
            SelectionCard(
                command=str(i),
                title=mode,
                subtitle=info.get(mode, ("", "white"))[0],
                art_key=f"difficulty_{mode}",
                accent=info.get(mode, ("", "white"))[1],
            )
            for i, mode in enumerate(MODES, 1)
        ]

    @staticmethod
    def _class_cards() -> list:
        from src.data_loader import load_class_data
        from src.move_info import class_move_lines, stat_lines
        accents = {"guardian": "cyan", "weaver": "magenta", "shaman": "green"}
        cards = []
        for i, (class_id, data) in enumerate(load_class_data().items(), 1):
            # data is a typed CharacterClass model; display carries the labels
            tagline = (data.description or "").split(" - ")[0]
            hp, dmg = stat_lines(data)
            moves = "\n".join(class_move_lines(data))
            stats = f"{hp}\n{dmg}\n⚔ {data.display.weapon_name}\n\nMoves:\n{moves}"
            cards.append(SelectionCard(
                command=str(i),
                title=data.name,
                subtitle=f"{tagline}\n\n{stats}",
                art_key=f"class_{class_id}",
                accent=accents.get(class_id, "white"),
            ))
        return cards

    def _on_combat_started(self, event):
        """Handle combat started — one-shot initialization of combat UI."""
        self._combat_view = CombatView.from_dict(event.data)
        self._available_attacks = self._combat_view.available_attacks
        self._bind_combat_hotkeys()
        self.query_one("#input-field", Input).blur()
        self._apply_game_state_styling("in_combat")
        self._show_combat_ui()

    def _on_combat_frame_updated(self, event):
        """Handle per-turn combat frame update — refresh health and cooldowns."""
        self._combat_view = CombatView.from_dict(event.data)
        self._available_attacks = self._combat_view.available_attacks
        self._update_combat_panels()

    def _on_combat_action_result(self, event):
        """Handle combat action result with enhanced feedback and visual effects."""
        action_data = event.data
        if action_data:
            self._combat_log.append(action_data)
            # Keep only last 10 combat actions
            if len(self._combat_log) > 10:
                self._combat_log.pop(0)

            # Create visual feedback for damage/healing
            damage = action_data.get("damage", 0)
            healing = action_data.get("healing", 0)
            actor = action_data.get("actor", "")

            if damage > 0:
                self._show_floating_number(damage, "damage", actor)
            if healing > 0:
                self._show_floating_number(healing, "heal", actor)

            # Use StateManager to check combat state
            if self.state_manager.is_in_combat():
                self._update_combat_panels()

    def _on_tutorial_hint(self, event):
        """Pin the current tutorial step; the closing summary goes to the output."""
        data = event.data or {}
        if data.get("final"):
            self._ui_call(self._echo_panel.clear)
            self._ui_call(self.append_output, "\n" + data.get("text", ""))
            return
        self._ui_call(
            self._echo_panel.show_hint,
            data.get("text", ""), data.get("step"), data.get("total", 0),
            bool(self._settings_manager.settings.get("reduce_motion", False)),
        )
        if data.get("highlight"):
            self._ui_call(self._flash_section, data["highlight"])

    _FLASH_PULSES = 3
    _FLASH_SECONDS = 0.35

    def _flash_section(self, label: str) -> None:
        """Pulse the "<label>:" section of the current output so the player can
        find what Echo is pointing at, then leave it lit."""
        base = self.output_content
        if not isinstance(base, Text):
            return
        start = base.plain.find(f"{label}:")
        if start < 0:
            return
        end = base.plain.find("\n\n", start)
        lit = base.copy()
        lit.stylize("bold black on yellow", start, len(base.plain) if end < 0 else end)

        if self._settings_manager.settings.get("reduce_motion", False):
            self.output_content = lit
            return

        frames = [lit, base] * self._FLASH_PULSES + [lit]

        def next_frame() -> None:
            # The player typed something else: the section is gone, stop.
            if not frames or (self.output_content is not base and self.output_content is not lit):
                timer.stop()
                return
            self.output_content = frames.pop(0)

        timer = self.set_interval(self._FLASH_SECONDS, next_frame)
        next_frame()

    def _on_enemy_defeated(self, event):
        """Enemy died: scene drains its HP bar to zero and removes the sprite.
        Needed for one-tap kills — no combat frame update follows the killing blow."""
        if self._combat_view is not None:
            self._combat_view = replace(self._combat_view, enemy_health=0)
        self._scene_view.defeat_enemy()

    # -- victory finale ---------------------------------------------------------

    def _on_game_won(self, event):
        """Victory: scene brightens; epilogue arrives in beats; recap card last."""
        reduce_motion = bool(self._settings_manager.settings.get("reduce_motion", False))
        self._scene_view.play_finale(reduce_motion=reduce_motion)
        self._finale.start(event.data or {}, reduce_motion)

    def _on_combat_ended(self, event):
        """Handle combat ended event with styling reset."""
        logger.debug("Combat ended event received")

        # Reset to exploring game state styling and hide combat UI
        self._apply_game_state_styling("exploring")
        self._hide_combat_ui(leave_battle=not event.data.get("defeat", False))

        # Clear combat data immediately (state is managed by StateManager)
        logger.debug("Clearing combat data")
        self._combat_view = None
        self._combat_log.clear()
        self._available_attacks = []

        # Unbind combat hotkeys
        self._unbind_combat_hotkeys()

        # Force-focus input so user isn't stranded in Selection Mode after combat.
        try:
            self.query_one("#input-field", Input).focus()
        except Exception as e:
            logger.debug(f"Could not refocus input post-combat: {e}")

        # Reset combat hint flag so it can show again next combat session.
        self._combat_hint_shown = False

        logger.debug("Combat ended handling complete")

    # =====================================
    # INPUT HANDLING
    # =====================================

    def on_input_submitted(self, event: Input.Submitted):
        """Handle command input."""
        command = event.value.strip()
        event.input.value = ""

        if not command:
            return

        # Emit command event with current state from StateManager
        self.bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": command},
            "TextualGameUI"
        )

    def on_key(self, event):
        """Handle key press events."""
        # Victory finale in progress: any key fast-forwards the reveal.
        if self._finale.revealing:
            self._finale.skip()
            event.stop()
            return

        if event.key == "escape":
            # Defer to active modal screen (e.g., Settings) — its own ESC binding handles dismiss.
            if len(self.screen_stack) > 1:
                return
            # Esc mid-line cancels the line, like a shell. Only an Esc on an
            # empty prompt means "quit" — a typo must never close the game.
            if self._cancel_pending_input():
                event.stop()
                return
            # Emit quit command to use existing confirmation flow
            self.bus.emit_event(
                EventType.COMMAND_ENTERED,
                {"command": "quit"},
                "TextualGameUI"
            )
            return

        # Main menu: arrow-key navigation; any other key fast-forwards typewriter
        if self.state_manager.current_state == GameState.MENU:
            if self._title_menu.handle_key(event.key):
                event.stop()

    def _cancel_pending_input(self) -> bool:
        """Clear a half-typed command. True if there was one to clear."""
        field = self.query_one("#input-field", Input)
        if not field.value:
            return False
        field.value = ""
        return True

    def on_input_blurred(self, event: Input.Blurred) -> None:
        """Handle when the input field loses focus (TAB pressed)."""
        # Show the selection-mode hint modal once ever (persisted), not every
        # session — after the first combat it never interrupts again.
        if (
            self.state_manager.is_in_combat()
            and not self._combat_hint_shown
            and not self._settings_manager.settings.get("seen_selection_mode", False)
        ):
            self._combat_hint_shown = True
            self._settings_manager.settings["seen_selection_mode"] = True
            self._settings_manager.save()
            self.push_screen(CombatModeHintScreen())

    # =====================================
    # DEV TOOLS ACTIONS
    # =====================================

    def action_request_quit(self) -> None:
        """Ask the domain to quit, so the usual save prompt runs first."""
        self.bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": "quit"},
            "TextualGameUI",
        )

    def _on_quit_confirm_requested(self, event) -> None:
        """Show the quit chooser instead of making the player type a letter."""
        def answer(choice: str) -> None:
            self.bus.emit_event(
                EventType.COMMAND_ENTERED,
                {"command": choice},
                "QuitConfirmScreen",
            )

        # Deferred so the Enter/ESC that asked to quit cannot fall through onto
        # the new screen's own bindings and answer it instantly.
        self.call_after_refresh(self.push_screen, QuitConfirmScreen(answer))

    def _on_game_quit(self, event) -> None:
        """The domain confirmed the quit: stop the app so Textual restores the
        terminal on the way out."""
        self.exit()

    def action_open_settings(self) -> None:
        """Open the settings modal."""
        self.push_screen(SettingsScreen(self._settings_manager))

    def action_toggle_log_viewer(self) -> None:
        """Toggle the log viewer modal."""
        # Check if log viewer is already shown
        if any(isinstance(screen, LogViewerScreen) for screen in self.screen_stack):
            self.pop_screen()
        else:
            self.push_screen(LogViewerScreen())

    def action_restart_game(self) -> None:
        """Restart game state without closing UI."""
        # Show restart message
        self.output_content = "[yellow]Restarting game...[/yellow]"
        # Emit restart request event to game engine
        self.bus.emit_event(EventType.GAME_RESTART_REQUESTED, {}, "TextualGameUI")

    def _bind_combat_hotkeys(self):
        """Dynamically bind combat hotkeys with actual attack names, plus the
        always-available flee key."""
        # Unbind any existing combat keys first
        self._unbind_combat_hotkeys()

        if not self._available_attacks:
            return

        try:
            # One key per attack in the panel's order, cooldowns included, so
            # the number shown next to an attack is always the key that fires it.
            for i, attack_data in enumerate(self._available_attacks, 1):
                if i > 9:
                    break

                key = str(i)
                action = f"combat_hotkey_{i}"
                attack_name = attack_data.name

                # Bind the key
                self.bind(key, action, description=attack_name, show=True)
                self._bound_combat_keys.append(key)

            # Flee is always available (boss fights still block it — combat.py
            # shows the existing "cannot flee from a boss" message).
            self.bind("0", "combat_flee", description="Flee", show=True)
            self._bound_combat_keys.append("0")

        except Exception as e:
            logger.error(f"Error binding combat hotkeys: {e}")

    def _unbind_combat_hotkeys(self):
        """Remove all dynamically bound combat hotkeys."""
        for key in self._bound_combat_keys:
            try:
                self.unbind(key)
            except Exception as e:
                logger.debug(f"Error unbinding key {key}: {e}")

        self._bound_combat_keys.clear()

    # =====================================
    # HOTKEY ACTIONS
    # =====================================

    def action_combat_hotkey_1(self) -> None: self._execute_combat_hotkey(1)
    def action_combat_hotkey_2(self) -> None: self._execute_combat_hotkey(2)
    def action_combat_hotkey_3(self) -> None: self._execute_combat_hotkey(3)
    def action_combat_hotkey_4(self) -> None: self._execute_combat_hotkey(4)
    def action_combat_hotkey_5(self) -> None: self._execute_combat_hotkey(5)
    def action_combat_hotkey_6(self) -> None: self._execute_combat_hotkey(6)
    def action_combat_hotkey_7(self) -> None: self._execute_combat_hotkey(7)
    def action_combat_hotkey_8(self) -> None: self._execute_combat_hotkey(8)
    def action_combat_hotkey_9(self) -> None: self._execute_combat_hotkey(9)

    def action_combat_flee(self) -> None:
        """0 = flee. Emits the same event typed 'flee' produces, so
        combat.py's existing boss-block/success handling needs no changes."""
        if not self.state_manager.is_in_combat():
            return
        self.bus.emit_event(
            EventType.COMBAT_ACTION_SELECTED,
            {"choice": "flee"},
            "TextualGameUI",
        )

    def _execute_combat_hotkey(self, hotkey_number: int):
        """Fire the attack the combat panel shows at this number. One that is
        cooling down says so instead of firing anything."""
        if not self.state_manager.is_in_combat():
            return

        try:
            if not 1 <= hotkey_number <= len(self._available_attacks):
                logger.debug(
                    f"Hotkey [{hotkey_number}] out of range "
                    f"(only {len(self._available_attacks)} attacks)"
                )
                return

            attack_data = self._available_attacks[hotkey_number - 1]
            if attack_data.on_cooldown:
                # Push cooldown notice to combat log so panel stays intact.
                self._combat_log.append({
                    "actor": "system",
                    "message": (
                        f"⏱ {attack_data.name} on cooldown "
                        f"({attack_data.cooldown_remaining}t)"
                    ),
                })
                if len(self._combat_log) > 10:
                    self._combat_log.pop(0)
                self._update_combat_main_output()
                return

            logger.debug(f"Executing attack: {attack_data.name} (id={attack_data.id})")
            # The combat log shows the result; no immediate feedback here.
            self.bus.emit_event(
                EventType.COMBAT_ACTION_SELECTED,
                {"choice": attack_data.id},
                "TextualGameUI"
            )

        except Exception as e:
            logger.error(f"Error executing combat hotkey {hotkey_number}: {e}")
            # Don't overwrite combat display with error messages

    # =====================================
    # UI PROTOCOL IMPLEMENTATION
    # =====================================

    def _check_ready(self) -> None:
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")

    def _on_ui_thread(self) -> bool:
        return threading.get_ident() == getattr(self, "_ui_thread_id", None)

    def _ui_call(self, fn, *args) -> None:
        """Run a widget mutation on Textual's thread, wherever we are now.

        call_from_thread raises if you are already on the UI thread, so the
        check is not optional. The fallback covers the app not running yet
        (tests, teardown), where a direct call is correct.
        """
        if self._on_ui_thread():
            fn(*args)
            return
        try:
            self.call_from_thread(fn, *args)
        except Exception as e:
            logger.debug(f"call_from_thread failed, calling directly: {e}")
            fn(*args)

    def _add_to_history(self, content: str) -> None:
        self.message_history.append(content)
        if len(self.message_history) > self.max_messages:
            self.message_history.pop(0)

    def update_output(self, content: str) -> None:
        """Update the main output display (replaces the panel content)."""
        self._check_ready()
        self._add_to_history(content)

        # During combat, preserve combat panel: append to log instead of replacing.
        if self.state_manager.is_in_combat() and self._combat_view is not None:
            self._combat_log.append({"actor": "system", "message": content})
            if len(self._combat_log) > 10:
                self._combat_log.pop(0)
            self._update_combat_main_output()
            return

        self.output_content = content

    def display_message(self, message: str) -> None:
        """Show a one-off message (UIProtocol); same as replacing the output."""
        self.update_output(message)

    def update_output_renderable(self, renderable) -> None:
        """Push a Rich Renderable (Panel, Group, Table) directly to the output
        widget. Used for content that benefits from auto-width box drawing."""
        self._check_ready()
        try:
            self.query_one("#output-display").update(renderable)
        except Exception as e:
            logger.debug(f"update_output_renderable failed: {e}")

    def append_output(self, content) -> None:
        """Append content to the current output display.

        Style-safe: content may be a plain/markup string OR a Rich Text object.
        Joining with an f-string would stringify Text and flatten its colors,
        so mixed content is joined as Text."""
        self._check_ready()
        self._add_to_history(content)

        # During combat the output panel is the combat log — same path as update_output.
        if self.state_manager.is_in_combat() and self._combat_view is not None:
            self._combat_log.append({"actor": "system", "message": content})
            if len(self._combat_log) > 10:
                self._combat_log.pop(0)
            self._update_combat_main_output()
            return

        old = self.output_content
        if not old:
            self.output_content = content
        elif isinstance(old, Text) or isinstance(content, Text):
            joined = Text()
            joined.append(old if isinstance(old, Text) else Text.from_markup(str(old)))
            joined.append("\n")
            joined.append(content if isinstance(content, Text) else Text.from_markup(str(content)))
            self.output_content = joined
        else:
            self.output_content = f"{old}\n{content}"

    def clear_console(self) -> None:
        """Clear the output display."""
        self._check_ready()
        self.output_content = ""
        self.message_history.clear()

    def display_game_over(self) -> None:
        """Hand the keyboard back for the game-over choices. The screen itself
        is the animation's final frame (GameFlow); writing a second card here
        raced it and contradicted its r / n / q."""
        if self.ui_state != UIState.READY:
            return
        self.query_one("#input-field").focus()

    def _show_combat_ui(self):
        """Activate combat UI mode: battle scene + combat styling."""
        self.add_class("combat-active")
        self._scene_view.show_battle(
            self._combat_view,
            self._player_view,
            reduce_motion=bool(self._settings_manager.settings.get("reduce_motion", False)),
        )
        self._update_combat_panels()

        input_field = self.query_one("#input-field")
        input_field.placeholder = "combat@system:~$ Enter command..."

    def _hide_combat_ui(self, leave_battle: bool = True):
        """Deactivate combat UI mode.

        leave_battle=False on a death: the game-over flow owns the scene
        (play_death), and dropping out of battle mode would show the room
        behind it. This comes from the COMBAT_ENDED payload, not the game
        state: the UI hears COMBAT_ENDED before the engine sets GAME_OVER.

        Synchronous. This used to defer everything behind a 0.1s timer because
        the engine emitted ROOM_ENTERED *after* its panel refresh, so the fresh
        room view had not arrived by the time this ran and the scene restored
        stale. The engine now emits ROOM_ENTERED first, so there is nothing to
        wait for — and a timer is a race, not a fix.
        """
        self.remove_class("combat-active")
        self.query_one("#input-field").placeholder = "Enter command..."
        self._inv_panel.update_inventory(self._inventory_view)
        self._stats_panel.update_stats(self._player_view)

        if leave_battle:
            self._scene_view.end_battle()

    def _update_combat_panels(self):
        """Update all combat-related panels."""
        if self._combat_view is None:
            return

        self._scene_view.update_battle(self._combat_view)
        self._update_combat_main_output()
        self._stats_panel.refresh_combat(self._player_view, self._combat_view)
        self._inv_panel.update_inventory(self._inventory_view)

    def _update_combat_main_output(self):
        """Update main output panel with combat log and actions."""
        if self._combat_view is None:
            return
        content_text = render_combat_output(
            self._combat_log, self._player_view, self._available_attacks,
            player_hp=(
                self._combat_view.player_health, self._combat_view.player_max_health
            ),
        )
        # Bypass update_output's combat-routing to avoid recursion.
        self._add_to_history(content_text)
        self.output_content = content_text

    # =====================================
    # ENHANCED STYLING METHODS
    # =====================================

    _ROOM_CLASSES = ["room-home", "room-dangerous", "room-safe"]
    _STATE_CLASSES = {
        "exploring": "game-state-exploring",
        "in_combat": "game-state-in-combat",
        "menu": "game-state-menu",
    }

    def _apply_room_theme(self, room_id: str, room: RoomView):
        """Apply visual theme based on room characteristics."""
        for cls in self._ROOM_CLASSES:
            self.remove_class(cls)

        desc = room.description.lower()
        if "home" in room_id.lower():
            self.add_class("room-home")
        elif room.enemies or "danger" in desc:
            self.add_class("room-dangerous")
        elif "safe" in desc:
            self.add_class("room-safe")

    def _apply_game_state_styling(self, state: str):
        """Apply styling based on current game state."""
        for cls in self._STATE_CLASSES.values():
            self.remove_class(cls)
        if state in self._STATE_CLASSES:
            self.add_class(self._STATE_CLASSES[state])

    def _apply_status_effect_styling(self, effects: list):
        """Apply visual styling based on active status effects."""
        # Remove all existing status effect classes
        for class_name in ["status-poisoned", "status-blessed", "status-cursed"]:
            self.remove_class(class_name)

        # Apply styling based on most significant effect
        if not effects:
            return

        for effect in effects:
            effect_type = effect.get("type", "").lower()
            if "poison" in effect_type or "damage" in effect_type:
                self.add_class("status-poisoned")
                break
            elif "bless" in effect_type or "heal" in effect_type or "regen" in effect_type:
                self.add_class("status-blessed")
                break
            elif "curse" in effect_type or "debuff" in effect_type:
                self.add_class("status-cursed")
                break

    def _show_floating_number(self, amount: int, effect_type: str, actor: str):
        """Show floating damage/heal numbers with visual feedback."""
        # Floating number pop in the battle scene for both directions.
        try:
            self._scene_view.play_effect(effect_type, actor, amount)
        except Exception as e:
            logger.debug(f"Damage pop failed: {e}")

        if effect_type == "damage":
            # Border flash red when enemy hits player.
            if actor == "enemy":
                self.add_class("panel-update")
                self.set_timer(0.3, lambda: self.remove_class("panel-update"))
        elif effect_type == "heal":
            self.add_class("status-blessed")
            self.set_timer(0.5, lambda: self.remove_class("status-blessed"))

    # =====================================
    # PANEL UPDATE UTILITIES
    # =====================================

    def _update_all_panels_to_defaults(self):
        """Set all panels to default states."""
        self._inv_panel.update("Inventory will appear here")
        self._stats_panel.update("Stats will appear here")
        self._scene_view.show_loading()

    # =====================================
    # TITLE SCREEN & UI UTILITIES
    # =====================================

    def _display_title_screen(self, skip_typewriter: bool = False):
        """Display the title screen, full-panel, with arrow-key main menu."""
        self._title_menu.show(skip_typewriter)
