#!/usr/bin/env python3
"""
Clean Textual UI Implementation for HFSE

This is a refactored version of the UI that provides:
- Enhanced combat system with visual feedback
- Dynamic hotkey system
- Clean panel organization
- Event-driven architecture

Author: Duhon Young
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, Input, RichLog
from textual.containers import Container, VerticalScroll, Horizontal, Vertical
from textual.reactive import var
from textual.screen import ModalScreen
from rich.text import Text

from src.ui.ui_interface import UIProtocol, UIError, UIInitializationError, UIStateError
from src.events import event_bus, EventType
from src.game_states import GameState, UIState
from src.state_manager import state_manager
from utils.typewriter import TypewriterPresets, create_typewriter_output_func, request_skip as request_typewriter_skip
from config.dev_config import SKIP_INTRO

from src.ui.panels.inventory_panel import InventoryPanel
from src.ui.panels.stats_panel import StatsPanel
from src.ui.panels.combat_panel import CombatPanel
from src.ui.panels.room_strip import RoomStrip
from src.ui.panels.entity_strip import EntityStrip
from src.ui.screens.combat_hint import CombatModeHintScreen
from src.ui.screens.log_viewer import LogViewerScreen
from src.ui.screens.settings_screen import SettingsScreen
from src.ui.command_suggester import CommandSuggester
from config.settings_manager import SettingsManager

import logging
import os
import threading
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TextualGameUI(App):
    """Enhanced Textual-based game UI with improved combat system."""

    CSS_PATH = os.path.join(os.path.dirname(__file__), "ui.css")
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+p", "open_settings", "Settings", key_display="ctrl + p"),
        Binding("l", "toggle_log_viewer", "Show/Hide Logs", key_display="L"),
        Binding("f5", "restart_game", "Restart Game", key_display="F5"),
    ]

    # =====================================
    # INITIALIZATION & SETUP
    # =====================================

    def __init__(self, *args, **kwargs):
        # Initialize state BEFORE calling super().__init__()
        # Note: Game state is now managed by StateManager singleton
        # Store view data (dicts) instead of backend objects
        self._settings_manager = SettingsManager()
        self._settings_manager.load()
        self._player_view = {}  # StatsView dict
        self._inventory_view = {}  # InventoryView dict
        self._room_view = {}  # RoomView dict
        self._combat_view = {}  # CombatView dict
        self._combat_log = []  # Store recent combat actions
        self._bound_combat_keys = []  # Track bound combat keys
        self._available_attacks = []  # Attack list from combat view data
        self._combat_hint_shown = False  # Track if selection mode hint was shown
        self._player_ref = None  # Set by game engine after player creation; used for tutorial checks
        self._world_ref = None   # Set by game engine; used by autocomplete suggester
        self._room_aliases_ref: dict = {}  # Populated from CommandHandler for cd autocomplete

        # Intro / main-menu state (arrow-key navigation)
        self._menu_index = 0
        self._menu_state = "idle"  # "typing" | "menu_ready" | "idle"
        self._intro_title: Optional[Text] = None
        self._intro_skip_hint: Optional[Text] = None
        self._intro_story_text = ""
        self._intro_full_story = ""

        super().__init__(*args, **kwargs)
        self.ui_state = UIState.INITIALIZING
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
    ]

    def _setup_event_subscriptions(self):
        """Subscribe to relevant game events."""
        for event_type, handler_name in self._EVENT_HANDLERS:
            event_bus.subscribe(event_type, getattr(self, handler_name))

    def compose(self) -> ComposeResult:
        """Create the main UI layout."""
        yield Static(id="header")
        with Horizontal():
            with Vertical(id="main-area"):
                yield RoomStrip(id="room-strip")
                yield EntityStrip(id="entity-strip")
                with VerticalScroll(id="output-panel"):
                    yield Static(self.output_content, id="output-display")
            with Container(id="sidebar"):
                yield InventoryPanel(id="inventory-panel")
                yield StatsPanel(id="stats-panel")
                yield CombatPanel(id="combat-panel")
        yield Footer()
        yield Input(placeholder="Enter command...", id="input-field")

    def on_mount(self) -> None:
        """Initialize the UI when mounted."""
        try:
            # Store panel references
            self._inv_panel = self.query_one("#inventory-panel", InventoryPanel)
            self._stats_panel = self.query_one("#stats-panel", StatsPanel)
            self._combat_panel = self.query_one("#combat-panel", CombatPanel)
            self._room_strip = self.query_one("#room-strip", RoomStrip)
            self._entity_strip = self.query_one("#entity-strip", EntityStrip)

            # Set panel titles
            self._inv_panel.border_title = "📦 Inventory"
            self._stats_panel.border_title = "📊 Stats"
            self._combat_panel.border_title = "⚔ Combat"

            self.ui_state = UIState.READY
            self._settings_manager.register_themes(self)
            self._settings_manager.apply_theme(self._settings_manager.settings["theme"])
            self._settings_manager.set_text_speed(self._settings_manager.settings["text_speed"])
            self._settings_manager.set_reduce_motion(self._settings_manager.settings["reduce_motion"])
            self._settings_manager.set_hints(self._settings_manager.settings["hints"])
            self._settings_manager.set_difficulty(self._settings_manager.settings["difficulty"])
            self._update_all_panels_to_defaults()

            # Attach context-aware autocomplete to the input field (always)
            input_widget = self.query_one("#input-field", Input)
            input_widget.suggester = CommandSuggester(
                get_player=lambda: self._player_ref,
                get_world=lambda: self._world_ref,
                get_aliases=lambda: self._room_aliases_ref,
            )

            # Display title screen with arrow-key main menu.
            # SKIP_INTRO bypasses the typewriter but keeps the navigable menu.
            self._display_title_screen(skip_typewriter=SKIP_INTRO)

            event_bus.emit_event(EventType.UI_READY, {}, "TextualGameUI")
            logger.info("TextualGameUI mounted successfully")
        except Exception as e:
            self.ui_state = UIState.ERROR
            logger.error(f"Error mounting TextualGameUI: {e}")
            raise UIInitializationError(f"Failed to initialize UI: {e}")

    def shutdown(self) -> None:
        """Clean shutdown of UI resources."""
        try:
            self.ui_state = UIState.SHUTTING_DOWN
            for event_type, handler_name in self._EVENT_HANDLERS:
                event_bus.unsubscribe(event_type, getattr(self, handler_name))
            logger.info("TextualGameUI shutdown complete")
        except Exception as e:
            logger.error(f"Error during UI shutdown: {e}")

    # =====================================
    # REACTIVE VARIABLES & WATCHERS
    # =====================================

    header_content = var("The Haunted Filesystem")
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
            self._player_view = event.data['stats']
        if 'inventory' in event.data:
            self._inventory_view = event.data['inventory']
        self._stats_panel.update_stats(self._player_view)

    def _reset_ui_state(self):
        """Reset all UI state - called when game starts or restarts."""
        logger.debug("Resetting UI state")

        # Clear all view data
        self._player_view = {}
        self._inventory_view = {}
        self._room_view = {}
        self._combat_view = {}

        # Clear combat data
        self._combat_log.clear()
        self._available_attacks = []

        # Remove combat UI styling
        self.remove_class("combat-active")

        # Unbind any combat hotkeys
        self._unbind_combat_hotkeys()

        # Set to exploring game state styling
        self._apply_game_state_styling("exploring")

        logger.debug("UI state reset complete")

    def _on_game_over(self, event):
        """Handle game over event."""
        # Reset UI state on game over/restart
        self._reset_ui_state()

        # CommandHandler triggers the particle animation (2.5s).
        # Defer the static game-over screen so it doesn't get overwritten by animation frames.
        # Dynamic read — settings_manager mutates dev_cfg.DISABLE_ANIMATIONS at runtime.
        import config.dev_config as _dev_cfg
        delay = 0.0 if _dev_cfg.DISABLE_ANIMATIONS else 2.6
        if delay > 0:
            self.set_timer(delay, self.display_game_over)
        else:
            self.display_game_over()

    def _on_player_created(self, event):
        """Handle player created event."""
        # Event data is now StatsView dict
        self._player_view = event.data
        self._stats_panel.update_stats(self._player_view)

    def _on_player_stats_changed(self, event):
        """Handle player stats changed event."""
        # Event data is now StatsView dict
        self._player_view = event.data
        self._stats_panel.update_stats(self._player_view)
        if state_manager.is_in_combat():
            self._update_combat_panels()

    def _on_player_inventory_changed(self, event):
        """Handle player inventory changed event."""
        # Event data is now InventoryView dict
        self._inventory_view = event.data
        self._inv_panel.update_inventory(self._inventory_view)

    def _on_room_entered(self, event):
        """Handle room entered event with enhanced theming."""
        if 'room' in event.data:
            self._room_view = event.data['room']
            exits = self._room_view.get('exits', [])
            enemies = self._room_view.get('enemies', [])
            npcs = self._room_view.get('npcs', [])

            room_name = self._room_view.get('name', '')
            self._room_strip.refresh_room(room_name, exits)
            self._entity_strip.refresh_entities(enemies, npcs)

            # Apply dynamic room theming using room view data
            self._apply_room_theme(room_name, self._room_view)

            # Apply exploring game state
            self._apply_game_state_styling("exploring")

    def _on_ui_state_changed(self, event):
        """Handle UI state changed event - trigger UI styling changes only."""
        new_state = event.data.get('new_state')
        # State is managed by StateManager, UI just reacts to changes
        # Trigger any UI-specific styling updates here if needed

    def _on_combat_started(self, event):
        """Handle combat started — one-shot initialization of combat UI."""
        self._combat_view = event.data
        self._available_attacks = event.data.get('available_attacks', [])
        self._bind_combat_hotkeys()
        self._apply_game_state_styling("in_combat")
        self._show_combat_ui()

    def _on_combat_frame_updated(self, event):
        """Handle per-turn combat frame update — refresh health and cooldowns."""
        self._combat_view = event.data
        self._available_attacks = event.data.get('available_attacks', [])
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
            if state_manager.is_in_combat():
                self._update_combat_panels()

    def _on_combat_ended(self, event):
        """Handle combat ended event with styling reset."""
        logger.debug("Combat ended event received")

        # Reset to exploring game state styling and hide combat UI
        self._apply_game_state_styling("exploring")
        self._hide_combat_ui()

        # Clear combat data immediately (state is managed by StateManager)
        logger.debug("Clearing combat data")
        self._combat_view = {}
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
        event_bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": command, "game_state": state_manager.current_state},
            "TextualGameUI"
        )

    def on_key(self, event):
        """Handle key press events."""
        if event.key == "escape":
            # Defer to active modal screen (e.g., Settings) — its own ESC binding handles dismiss.
            if len(self.screen_stack) > 1:
                return
            # Emit quit command to use existing confirmation flow
            event_bus.emit_event(
                EventType.COMMAND_ENTERED,
                {"command": "quit", "game_state": state_manager.current_state},
                "TextualGameUI"
            )
            return

        # Main menu: arrow-key navigation; any other key fast-forwards typewriter
        if state_manager.current_state == GameState.MENU:
            if self._menu_state == "typing":
                request_typewriter_skip()
                event.stop()
                return
            if self._menu_state == "menu_ready":
                if event.key == "up":
                    self._menu_index = (self._menu_index - 1) % 3
                    self._render_intro()
                    event.stop()
                elif event.key == "down":
                    self._menu_index = (self._menu_index + 1) % 3
                    self._render_intro()
                    event.stop()
                elif event.key in ("enter", "return"):
                    self._select_menu_option()
                    event.stop()

    def on_input_blurred(self, event: Input.Blurred) -> None:
        """Handle when the input field loses focus (TAB pressed)."""
        # Show the selection-mode hint modal once ever (persisted), not every
        # session — after the first combat it never interrupts again.
        if (
            state_manager.is_in_combat()
            and not self._combat_hint_shown
            and not self._settings_manager.settings.get("seen_selection_mode", False)
        ):
            self._combat_hint_shown = True
            self._settings_manager.settings["seen_selection_mode"] = True
            self._settings_manager.save()
            self.push_screen(CombatModeHintScreen())

        # Tutorial: detect Selection Mode usage during tutorial combat
        if state_manager.is_in_combat() and self._player_ref is not None:
            ts = getattr(self._player_ref, 'tutorial_state', {})
            if ts.get('combat_typed', False) and not ts.get('combat_selection', False):
                event_bus.emit_event(
                    EventType.TUTORIAL_SELECTION_MODE_USED,
                    {},
                    "TextualGameUI"
                )

    # =====================================
    # DEV TOOLS ACTIONS
    # =====================================

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
        event_bus.emit_event(EventType.GAME_RESTART_REQUESTED, {}, "TextualGameUI")

    def _bind_combat_hotkeys(self):
        """Dynamically bind combat hotkeys with actual attack names."""
        # Unbind any existing combat keys first
        self._unbind_combat_hotkeys()

        if not self._available_attacks:
            return

        try:
            # Use available attacks from combat view data (list of AttackView dicts)
            # Filter out attacks on cooldown
            available_list = [
                attack
                for attack in self._available_attacks
                if not attack.get('on_cooldown', False)
            ]

            # Bind keys dynamically
            for i, attack_data in enumerate(available_list, 1):
                if i > 9:
                    break

                key = str(i)
                action = f"combat_hotkey_{i}"
                attack_name = attack_data.get('name', attack_data.get('id', 'Unknown'))

                # Bind the key
                self.bind(key, action, description=attack_name, show=True)
                self._bound_combat_keys.append(key)

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

    def _execute_combat_hotkey(self, hotkey_number: int):
        """Execute combat action based on hotkey number - only available attacks."""
        # Use StateManager to check combat state
        if not state_manager.is_in_combat():
            return

        try:
            # Log all available attacks with cooldown status
            logger.debug(f"Hotkey {hotkey_number} pressed. Available attacks: {len(self._available_attacks)}")
            for i, attack in enumerate(self._available_attacks, 1):
                on_cd = attack.get('on_cooldown', False)
                cd_remaining = attack.get('cooldown_remaining', 0)
                attack_name = attack.get('name', 'Unknown')
                logger.debug(f"  [{i}] {attack_name}: on_cooldown={on_cd}, remaining={cd_remaining}")

            # Use available attacks from combat view data (list of AttackView dicts)
            # Only include attacks that are NOT on cooldown
            available_list = [
                attack
                for attack in self._available_attacks
                if not attack.get('on_cooldown', False)
            ]

            logger.debug(f"After cooldown filter: {len(available_list)} attacks available")

            if 1 <= hotkey_number <= len(available_list):
                attack_data = available_list[hotkey_number - 1]
                attack_id = attack_data.get('id')
                attack_name = attack_data.get('name')

                logger.debug(f"Executing attack: {attack_name} (id={attack_id})")

                event_bus.emit_event(
                    EventType.COMBAT_ACTION_SELECTED,
                    {"choice": attack_id},
                    "TextualGameUI"
                )

                # Don't show immediate feedback during combat - the combat log will show the results
                # The combat system handles all output during combat mode
            else:
                # Check if hotkey corresponds to an attack on cooldown
                if 1 <= hotkey_number <= len(self._available_attacks):
                    attack_data = self._available_attacks[hotkey_number - 1]
                    if attack_data.get('on_cooldown', False):
                        attack_name = attack_data.get('name', 'Attack')
                        cd_remaining = attack_data.get('cooldown_remaining', 0)

                        # Push cooldown notice to combat log so panel stays intact.
                        self._combat_log.append({
                            "actor": "system",
                            "message": f"⏱ {attack_name} on cooldown ({cd_remaining}t)"
                        })
                        if len(self._combat_log) > 10:
                            self._combat_log.pop(0)
                        self._update_combat_main_output()

                        logger.debug(f"Hotkey [{hotkey_number}] - {attack_name} on cooldown for {cd_remaining} turns")
                    else:
                        logger.debug(f"Hotkey [{hotkey_number}] not available (only {len(available_list)} attacks ready)")
                else:
                    logger.debug(f"Hotkey [{hotkey_number}] out of range (only {len(self._available_attacks)} attacks)")

        except Exception as e:
            logger.error(f"Error executing combat hotkey {hotkey_number}: {e}")
            # Don't overwrite combat display with error messages

    # =====================================
    # UI PROTOCOL IMPLEMENTATION
    # =====================================

    def _check_ready(self) -> None:
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")

    def _add_to_history(self, content: str) -> None:
        self.message_history.append(content)
        if len(self.message_history) > self.max_messages:
            self.message_history.pop(0)

    def update_output(self, content: str) -> None:
        """Update the main output display."""
        self._check_ready()
        self._add_to_history(content)

        # During combat, preserve combat panel: append to log instead of replacing.
        if state_manager.is_in_combat() and self._combat_view:
            self._combat_log.append({"actor": "system", "message": content})
            if len(self._combat_log) > 10:
                self._combat_log.pop(0)
            self._update_combat_main_output()
            return

        self.output_content = content

    def update_output_renderable(self, renderable) -> None:
        """Push a Rich Renderable (Panel, Group, Table) directly to the output
        widget. Used for content that benefits from auto-width box drawing."""
        self._check_ready()
        try:
            self.query_one("#output-display").update(renderable)
        except Exception as e:
            logger.debug(f"update_output_renderable failed: {e}")

    def append_output(self, content: str) -> None:
        """Append content to the current output display."""
        self._check_ready()
        self._add_to_history(content)
        self.output_content = (self.output_content + "\n" + content) if self.output_content else content

    def update_inventory(self, content: str) -> None:
        """Update the inventory panel."""
        self._check_ready()
        self._inv_panel.update(content)

    def update_stats(self, content: str) -> None:
        """Update the stats panel."""
        self._check_ready()
        self._stats_panel.update(content)

    def update_exits(self, exits: list) -> None:
        """Update the room strip exits display."""
        self._check_ready()
        room_name = self._room_view.get('name', '') if self._room_view else ''
        self._room_strip.refresh_room(room_name, exits)

    def update_player_name(self, name: str) -> None:
        """Update the player name display."""
        self._check_ready()
        self.header_content = f"The Haunted Filesystem - {name}"

    def clear_console(self) -> None:
        """Clear the output display."""
        self._check_ready()
        self.output_content = ""
        self.message_history.clear()

    def display_game_over(self) -> None:
        """Show the game over screen."""
        if self.ui_state != UIState.READY:
            return

        self.clear_console()

        player_name = self._player_view.get('player_name', 'Unknown Sysadmin')

        game_over_content = f"""[bold red]GAME OVER[/bold red]

[bold]System Critical Failure[/bold]

Brave sysadmin {player_name}, your session has been terminated.

[yellow]Press any key to return to the main menu...[/yellow]"""

        self.update_output(game_over_content)
        self.query_one("#input-field").focus()

    def save_current_game(self) -> None:
        """Handle game saving UI feedback."""
        event_bus.emit_event(EventType.GAME_SAVED, {"trigger": "ui_request"}, "TextualGameUI")
        save_text = Text("Game saved successfully!", style="green")
        self.update_output(save_text)

    # =====================================
    # COMBAT UI SYSTEM
    # =====================================

    def _show_combat_ui(self):
        """Activate combat UI mode."""
        self.add_class("combat-active")
        self._update_combat_panels()

        input_field = self.query_one("#input-field")
        input_field.placeholder = "combat@system:~$ Enter command..."

    def _hide_combat_ui(self):
        """Deactivate combat UI mode."""
        self.remove_class("combat-active")
        self._combat_panel.show_idle()

        # Delayed refresh ensures panels update after combat cleanup completes
        def delayed_panel_refresh():
            self._inv_panel.update_inventory(self._inventory_view)
            self._stats_panel.update_stats(self._player_view)
            if self._room_view:
                room_name = self._room_view.get('name', '')
                exits = self._room_view.get('exits', [])
                enemies = self._room_view.get('enemies', [])
                npcs = self._room_view.get('npcs', [])
                self._room_strip.refresh_room(room_name, exits)
                self._entity_strip.refresh_entities(enemies, npcs)

        self.set_timer(0.1, delayed_panel_refresh)
        self.query_one("#input-field").placeholder = "Enter command..."

    def _update_combat_panels(self):
        """Update all combat-related panels."""
        if not self._combat_view:
            return

        self._combat_panel.refresh_combat(self._combat_view, self._player_view)
        self._update_combat_main_output()
        self._stats_panel.refresh_combat(self._player_view, self._combat_view)
        self._inv_panel.update_inventory(self._inventory_view)

    def _update_combat_main_output(self):
        """Update main output panel with combat log and actions."""
        if not self._combat_view:
            return

        output_lines = []

        if self._combat_log:
            # Mid-combat: show only outcomes. Controls live in the footer; the
            # attack list was shown at combat start. Keeps the log readable
            # instead of re-dumping the full controls block every turn.
            output_lines.append("[bold yellow]⚔ COMBAT LOG ⚔[/bold yellow]")
            output_lines.append("=" * 40)

            _ACTOR_FORMAT = {
                "player": ("green",  "👤"),
                "enemy":  ("red",    "👹"),
                "system": ("yellow", "⚡"),
            }
            for action in self._combat_log[-10:]:
                actor = action.get('actor', 'system')
                message = action.get('message', 'Action performed')
                color, icon = _ACTOR_FORMAT.get(actor, ("white", "📋"))
                output_lines.append(f"[{color}]{icon} {message}[/{color}]")

            output_lines.append("=" * 40)
            output_lines.append(
                "[dim]Attacks: number keys in the footer · "
                "type 'use <item>' or 'flee'[/dim]"
            )
        else:
            # Combat start: introduce the fight and show attack options once.
            output_lines.extend([
                "[bold yellow]⚔ BATTLE STARTED ⚔[/bold yellow]",
                "=" * 40,
                "[dim]Press [bold]TAB[/bold] for selection mode, or type an attack. "
                "'flee' to escape.[/dim]",
                "",
                self._get_dynamic_hotkey_display(),
            ])

        content_text = "\n".join(output_lines)
        # Bypass update_output's combat-routing to avoid recursion.
        self._add_to_history(content_text)
        self.output_content = content_text

    def _get_dynamic_hotkey_display(self):
        """Generate dynamic hotkey display based on available attacks."""
        if not self._player_view:
            return "[dim]Attack options loading...[/dim]"

        try:
            # Use available attacks from combat view data (list of AttackView dicts)
            hotkey_lines = ["[bold green]QUICK ATTACKS:[/bold green]"]

            # Get base damage from player view
            base_damage = self._player_view.get('damage', 0)

            hotkey_num = 1
            for attack_data in self._available_attacks:
                if hotkey_num > 9:
                    break

                attack_name = attack_data.get('name', attack_data.get('id', 'Unknown'))
                on_cooldown = attack_data.get('on_cooldown', False)

                # Calculate total damage and gather metadata
                bonus_damage = attack_data.get('bonus_damage', 0)
                total_damage = base_damage + bonus_damage
                accuracy = attack_data.get('accuracy', 100)
                cooldown = attack_data.get('cooldown', 0)
                atk_type = attack_data.get('type', '')
                type_icon = {"physical": "⚔", "magical": "✨", "nature": "🌿"}.get(atk_type, "•")
                cd_label = f"CD {cooldown}t" if cooldown > 0 else "no CD"

                if not on_cooldown:
                    hotkey_lines.append(
                        f"[cyan][{hotkey_num}][/cyan] {type_icon} {attack_name} — "
                        f"[yellow]{total_damage} dmg[/yellow] "
                        f"([dim]{accuracy}% hit · {cd_label}[/dim])"
                    )
                    hotkey_num += 1
                else:
                    cooldown_remaining = attack_data.get('cooldown_remaining', 0)
                    hotkey_lines.append(
                        f"[dim][{hotkey_num}] {type_icon} {attack_name} — "
                        f"on cooldown ({cooldown_remaining}t left)[/dim]"
                    )
                    hotkey_num += 1

            if hotkey_num == 1:
                hotkey_lines.append("[dim]No attacks available[/dim]")

            return "\n".join(hotkey_lines)

        except Exception as e:
            logger.error(f"Error generating hotkey display: {e}")
            return "[dim]Attack options loading...[/dim]"

    # =====================================
    # ENHANCED STYLING METHODS
    # =====================================

    _ROOM_CLASSES = ["room-home", "room-dangerous", "room-safe"]
    _STATE_CLASSES = {
        "exploring": "game-state-exploring",
        "in_combat": "game-state-in-combat",
        "menu": "game-state-menu",
    }

    def _apply_room_theme(self, room_id: str, room_data: dict):
        """Apply visual theme based on room characteristics."""
        for cls in self._ROOM_CLASSES:
            self.remove_class(cls)

        desc = room_data.get("description", "").lower()
        if "home" in room_id.lower():
            self.add_class("room-home")
        elif room_data.get("enemies") or "danger" in desc:
            self.add_class("room-dangerous")
        elif room_data.get("safe", False) or "safe" in desc:
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
        # Floating number pop in combat panel for both directions.
        try:
            self._combat_panel.show_damage_pop(amount, actor, effect_type)
            self.set_timer(0.7, self._combat_panel.clear_damage_pop)
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
        self._combat_panel.show_idle()
        self._room_strip.refresh_room("Loading...", [])
        self._entity_strip.refresh_entities([], [])

    # =====================================
    # TITLE SCREEN & UI UTILITIES
    # =====================================

    def _display_title_screen(self, skip_typewriter: bool = False):
        """Display the title screen, full-panel, with arrow-key main menu."""
        title_ascii = '''
██╗  ██╗ █████╗ ██╗   ██╗███╗   ██╗████████╗███████╗██████╗
██║  ██║██╔══██╗██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
███████║███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██║  ██║
██╔══██║██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██║  ██║
██║  ██║██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██████╔╝
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═════╝

███████╗██╗██╗     ███████╗███████╗██╗   ██╗███████╗████████╗███████╗███╗   ███╗
██╔════╝██║██║     ██╔════╝██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝██╔════╝████╗ ████║
█████╗  ██║██║     █████╗  ███████╗ ╚████╔╝ ███████╗   ██║   █████╗  ██╔████╔██║
██╔══╝  ██║██║     ██╔══╝  ╚════██║  ╚██╔╝  ╚════██║   ██║   ██╔══╝  ██║╚██╔╝██║
██║     ██║███████╗███████╗███████║   ██║   ███████║   ██║   ███████╗██║ ╚═╝ ██║
╚═╝     ╚═╝╚══════╝╚══════╝╚══════╝   ╚═╝   ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝

A Terminal Adventure by Duhon Young'''

        opening_story = '''

[bold cyan]>>> INITIALIZING SYSTEM MEMORY... <<<[/bold cyan]
Fragments of directories flicker. File clusters scream in silence.
The great corruption has spread through the machine, leaving broken symlinks and
phantom processes where life once pulsed.

Once, sysadmins kept balance between order and entropy.
But now… your body is gone. Your essence remains—
a [green]Sysadmin Spirit[/green], bound to the filesystem.

At the system's heart lurks the [red]Daemon Overlord[/red],
a malignant process feeding on entropy,
rewriting directories into its dominion of chaos.

Your mission: traverse the haunted filesystem,
purge corrupted sectors, reclaim lost commands,
and [bold]restore the root.[/bold]

Fail, and the machine is consumed.
Succeed, and the filesystem breathes again.

'''

        # Switch to full-panel intro mode
        self.add_class("intro-mode")
        self._menu_index = 0
        self._intro_title = Text(title_ascii, style="bold green", justify="center")
        self._intro_skip_hint = Text(
            "\n[press any key to skip intro]\n",
            style="dim italic", justify="center",
        )
        self._intro_full_story = opening_story

        if skip_typewriter:
            self._intro_story_text = opening_story
            self._menu_state = "menu_ready"
            self._render_intro()
            return

        self._intro_story_text = ""
        self._menu_state = "typing"
        self._render_intro()

        def run_typewriter():
            try:
                def cb(text: str):
                    self._intro_story_text = text
                    self.call_from_thread(self._render_intro)
                TypewriterPresets.INTRO.type_text_sync(opening_story, cb)
            except Exception as e:
                logger.error(f"Typewriter effect failed for title screen: {e}")
            finally:
                self._intro_story_text = opening_story
                self._menu_state = "menu_ready"
                self.call_from_thread(self._render_intro)

        threading.Thread(target=run_typewriter, daemon=True).start()

    def _render_intro(self):
        """Compose and display the intro screen for the current menu state."""
        out = Text()
        if self._intro_title is not None:
            out.append_text(self._intro_title)
        if self._intro_skip_hint is not None:
            out.append_text(self._intro_skip_hint)

        if self._intro_story_text:
            story = Text.from_markup(self._intro_story_text)
            story.justify = "center"
            out.append_text(story)

        if self._menu_state == "menu_ready":
            out.append("\n")
            labels = ["NEW GAME", "LOAD GAME", "EXIT"]
            for i, label in enumerate(labels):
                if i == self._menu_index:
                    line = Text(f"  ▶  {label}  ◀  \n", style="reverse bold green", justify="center")
                else:
                    line = Text(f"     {label}     \n", style="dim cyan", justify="center")
                out.append_text(line)
            out.append_text(Text(
                "\n↑/↓ to select   ↵ to confirm   esc to quit\n",
                style="dim italic", justify="center",
            ))

        self.update_output(out)

    def _select_menu_option(self):
        """Confirm the highlighted main-menu option."""
        if self._menu_state != "menu_ready":
            return
        choice = ["1", "2", "3"][self._menu_index]
        self.remove_class("intro-mode")
        self._menu_state = "idle"
        try:
            input_widget = self.query_one("#input-field", Input)
            input_widget.focus()
        except Exception:
            pass
        event_bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": choice, "game_state": state_manager.current_state},
            "TextualGameUI"
        )
