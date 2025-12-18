#!/usr/bin/env python3
"""
Clean Textual UI Implementation for HFSE

This is a refactored version of the UI that provides:
- Enhanced combat system with visual feedback
- Dynamic hotkey system
- Clean panel organization
- Event-driven architecture

Author: Claude Code Enhancement
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, RichLog
from textual.containers import Container, VerticalScroll, Horizontal
from textual.reactive import var
from textual.screen import ModalScreen
from rich.text import Text

from src.ui.ui_interface import UIProtocol, UIError, UIInitializationError, UIStateError
from src.events import event_bus, EventType
from src.game_states import GameState, UIState
from utils.typewriter import TypewriterPresets, create_typewriter_output_func
from config.dev_config import SKIP_INTRO

import logging
import os
import threading
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TextualGameUI(App):
    """Enhanced Textual-based game UI with improved combat system."""
    
    CSS_PATH = os.path.join(os.path.dirname(__file__), "ui.css")
    BINDINGS = [
        ("l", "toggle_log_viewer", "Show/Hide Logs"),
        ("f5", "restart_game", "Restart Game"),
    ]

    # =====================================
    # INITIALIZATION & SETUP
    # =====================================
    
    def __init__(self, *args, **kwargs):
        # Initialize state BEFORE calling super().__init__()
        self._current_game_state = GameState.MENU
        self._player_data = None
        self._world_data = None
        self._combat_session = None
        self._combat_log = []  # Store recent combat actions
        self._bound_combat_keys = []  # Track bound combat keys

        super().__init__(*args, **kwargs)
        self.ui_state = UIState.INITIALIZING
        self._setup_event_subscriptions()
        
    def _setup_event_subscriptions(self):
        """Subscribe to relevant game events."""
        event_bus.subscribe(EventType.GAME_STARTED, self._on_game_started)
        event_bus.subscribe(EventType.GAME_OVER, self._on_game_over)
        event_bus.subscribe(EventType.PLAYER_CREATED, self._on_player_created)
        event_bus.subscribe(EventType.PLAYER_STATS_CHANGED, self._on_player_stats_changed)
        event_bus.subscribe(EventType.PLAYER_INVENTORY_CHANGED, self._on_player_inventory_changed)
        event_bus.subscribe(EventType.ROOM_ENTERED, self._on_room_entered)
        event_bus.subscribe(EventType.UI_STATE_CHANGED, self._on_ui_state_changed)
        event_bus.subscribe(EventType.COMBAT_STARTED, self._on_combat_started)
        event_bus.subscribe(EventType.COMBAT_ACTION_RESULT, self._on_combat_action_result)
        event_bus.subscribe(EventType.COMBAT_ENDED, self._on_combat_ended)

    def compose(self) -> ComposeResult:
        """Create the main UI layout."""
        yield Static(id="header")
        with Horizontal():
            with VerticalScroll(id="output-panel"):
                yield Static(self.output_content, id="output-display")
            with Container(id="sidebar"):
                yield Static("", id="inventory-panel")
                yield Static("", id="stats-panel") 
                yield Static("", id="exits-panel")
        yield Footer()
        yield Input(placeholder="Enter command...", id="input-field")

    def on_mount(self) -> None:
        """Initialize the UI when mounted."""
        try:
            # Set panel titles
            self.query_one("#inventory-panel").border_title = "Inventory"
            self.query_one("#stats-panel").border_title = "Stats"
            self.query_one("#exits-panel").border_title = "Exits"
            
            self.ui_state = UIState.READY
            self._update_all_panels_to_defaults()

            # Display title screen unless SKIP_INTRO is enabled
            if not SKIP_INTRO:
                self._display_title_screen()

            # Focus input field
            self.query_one("#input-field").focus()
            
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
            # Unsubscribe from all events
            event_bus.unsubscribe(EventType.GAME_STARTED, self._on_game_started)
            event_bus.unsubscribe(EventType.GAME_OVER, self._on_game_over)
            event_bus.unsubscribe(EventType.PLAYER_CREATED, self._on_player_created)
            event_bus.unsubscribe(EventType.PLAYER_STATS_CHANGED, self._on_player_stats_changed)
            event_bus.unsubscribe(EventType.PLAYER_INVENTORY_CHANGED, self._on_player_inventory_changed)
            event_bus.unsubscribe(EventType.ROOM_ENTERED, self._on_room_entered)
            event_bus.unsubscribe(EventType.UI_STATE_CHANGED, self._on_ui_state_changed)
            event_bus.unsubscribe(EventType.COMBAT_STARTED, self._on_combat_started)
            event_bus.unsubscribe(EventType.COMBAT_ACTION_RESULT, self._on_combat_action_result)
            event_bus.unsubscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
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
        self._current_game_state = GameState.PLAYING
        if 'player' in event.data:
            self._player_data = event.data['player']
        if 'world' in event.data:
            self._world_data = event.data['world']
        self._update_stats_panel()

    def _on_game_over(self, event):
        """Handle game over event."""
        self._current_game_state = GameState.GAME_OVER
        self.display_game_over()

    def _on_player_created(self, event):
        """Handle player created event."""
        if 'player' in event.data:
            self._player_data = event.data['player']
            self._update_stats_panel()

    def _on_player_stats_changed(self, event):
        """Handle player stats changed event."""
        if 'player' in event.data:
            self._player_data = event.data['player']
            self._update_stats_panel()
            if self._current_game_state == GameState.IN_COMBAT:
                self._update_combat_panels()

    def _on_player_inventory_changed(self, event):
        """Handle player inventory changed event."""
        if 'player' in event.data:
            self._player_data = event.data['player']
            self._update_inventory_panel()

    def _on_room_entered(self, event):
        """Handle room entered event with enhanced theming."""
        if 'world' in event.data:
            self._world_data = event.data['world']
            self._update_exits_panel()
            
            # Apply dynamic room theming if player and room data available
            if self._player_data and hasattr(self._player_data, 'current_room'):
                room_id = self._player_data.current_room
                room_data = self._world_data.rooms.get(room_id, {}) if self._world_data else {}
                self._apply_room_theme(room_id, room_data)
                
            # Apply exploring game state
            self._apply_game_state_styling("exploring")

    def _on_ui_state_changed(self, event):
        """Handle UI state changed event."""
        new_state = event.data.get('new_state')
        if new_state:
            self._current_game_state = new_state

    def _on_combat_started(self, event):
        """Handle combat started event with enhanced styling."""
        self._current_game_state = GameState.IN_COMBAT
        self._combat_session = event.data.get('session')

        # Bind combat hotkeys dynamically
        self._bind_combat_hotkeys()

        # Apply combat game state styling
        self._apply_game_state_styling("in_combat")
        self._show_combat_ui()

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
            
            if self._current_game_state == GameState.IN_COMBAT:
                self._update_combat_panels()

    def _on_combat_ended(self, event):
        """Handle combat ended event with styling reset."""
        logger.debug("Combat ended event received")

        # Reset to exploring game state styling and hide combat UI first
        self._apply_game_state_styling("exploring")
        self._hide_combat_ui()

        # Delay clearing combat data to allow for UI refresh
        def clear_combat_data():
            logger.debug("Clearing combat data after UI refresh")
            self._current_game_state = GameState.PLAYING
            self._combat_session = None
            self._combat_log.clear()

            # Unbind combat hotkeys
            self._unbind_combat_hotkeys()

        self.call_later(0.2, clear_combat_data)

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
            
        # Emit command event
        event_bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": command, "game_state": self._current_game_state},
            "TextualGameUI"
        )

    def on_key(self, event):
        """Handle key press events."""
        if event.key == "escape":
            # Emit quit command to use existing confirmation flow
            event_bus.emit_event(
                EventType.COMMAND_ENTERED,
                {"command": "quit", "game_state": self._current_game_state},
                "TextualGameUI"
            )

    # =====================================
    # DEV TOOLS ACTIONS
    # =====================================

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

        if not self._player_data:
            return

        try:
            from src.combat import combat_system

            # Get available attacks
            available_attacks = combat_system.get_available_attacks(
                self._player_data,
                getattr(self._player_data, 'spells', [])
            )

            # Filter out attacks on cooldown
            available_list = [
                (attack_id, attack_data)
                for attack_id, attack_data in available_attacks.items()
                if not attack_data.get('on_cooldown', False)
            ]

            # Bind keys dynamically
            for i, (attack_id, attack_data) in enumerate(available_list, 1):
                if i > 9:
                    break

                key = str(i)
                action = f"combat_hotkey_{i}"
                attack_name = attack_data.get('name', attack_id)

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
        if self._current_game_state != GameState.IN_COMBAT:
            return
            
        try:
            from src.combat import combat_system
            available_attacks = combat_system.get_available_attacks(
                self._player_data, 
                getattr(self._player_data, 'spells', [])
            )
            
            # Only include attacks that are NOT on cooldown
            available_list = [(aid, adata) for aid, adata in available_attacks.items() 
                            if not adata.get('on_cooldown', False)]
            
            if 1 <= hotkey_number <= len(available_list):
                attack_id, attack_data = available_list[hotkey_number - 1]
                
                event_bus.emit_event(
                    EventType.COMBAT_ACTION_SELECTED,
                    {"choice": attack_id},
                    "TextualGameUI"
                )
                
                # Don't show immediate feedback during combat - the combat log will show the results
                # The combat system handles all output during combat mode
            else:
                # During combat, don't overwrite the combat display with error messages
                # The user can see available hotkeys in the combat display
                logger.debug(f"Hotkey [{hotkey_number}] not available")
            
        except Exception as e:
            logger.error(f"Error executing combat hotkey {hotkey_number}: {e}")
            # Don't overwrite combat display with error messages

    # =====================================
    # UI PROTOCOL IMPLEMENTATION
    # =====================================

    def update_output(self, content: str) -> None:
        """Update the main output display."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        
        self.message_history.append(content)
        if len(self.message_history) > self.max_messages:
            self.message_history.pop(0)
        
        self.output_content = content

    def append_output(self, content: str) -> None:
        """Append content to the current output display."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        
        self.message_history.append(content)
        if len(self.message_history) > self.max_messages:
            self.message_history.pop(0)
        
        # Append to existing content with a newline
        if self.output_content:
            self.output_content += "\n" + content
        else:
            self.output_content = content

    def update_inventory(self, content: str) -> None:
        """Update the inventory panel."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        if self.query("#inventory-panel"):
            self.query_one("#inventory-panel").update(content)

    def update_stats(self, content: str) -> None:
        """Update the stats panel."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        if self.query("#stats-panel"):
            self.query_one("#stats-panel").update(content)

    def update_exits(self, exits: list) -> None:
        """Update the exits panel."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        
        if not exits:
            content = "No exits available"
        else:
            exit_lines = [f"[cyan]• {exit_name}[/]" for exit_name in exits]
            content = "\n".join(exit_lines)
        
        if self.query("#exits-panel"):
            self.query_one("#exits-panel").update(content)

    def update_player_name(self, name: str) -> None:
        """Update the player name display."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        self.header_content = f"The Haunted Filesystem - {name}"

    def clear_console(self) -> None:
        """Clear the output display."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        self.output_content = ""
        self.message_history.clear()

    def display_game_over(self) -> None:
        """Show the game over screen."""
        if self.ui_state != UIState.READY:
            return
            
        self.clear_console()
        
        player_name = self._player_data.name if self._player_data and hasattr(self._player_data, 'name') else "Unknown Sysadmin"
            
        game_over_content = f"""[bold red]GAME OVER[/bold red]

[bold]System Critical Failure[/bold]

Brave sysadmin {player_name}, your session has been terminated.

[yellow]Press any key to return to the main menu...[/yellow]"""
        
        self.update_output(game_over_content)
        self.query_one("#input-field").focus()

    def update_game_state_panels(self, player: Any, world: Any) -> None:
        """Update all game state panels with current data."""
        logger.debug(f"update_game_state_panels called - player: {player is not None}, world: {world is not None}")
        if self.ui_state != UIState.READY:
            logger.debug(f"UI not ready - current state: {self.ui_state}")
            raise UIStateError("UI is not ready for updates")
            
        self._player_data = player
        self._world_data = world
        logger.debug(f"Updated data - player_data: {self._player_data is not None}, world_data: {self._world_data is not None}")
        
        self._update_inventory_panel()
        self._update_stats_panel()
        self._update_exits_panel()

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
        self.query_one("#exits-panel").border_title = "Battle Status"
        self._update_combat_panels()
        
        input_field = self.query_one("#input-field")
        input_field.placeholder = "combat@system:~$ Enter command..."

    def _hide_combat_ui(self):
        """Deactivate combat UI mode."""
        logger.debug("Hiding combat UI and restoring normal panels")
        self.remove_class("combat-active")
        
        # Explicitly reset exits panel and forcefully clear any combat content
        exits_panel = self.query_one("#exits-panel")
        exits_panel.border_title = "Exits"
        
        # FORCE clear the exits panel content immediately to remove enemy health display
        exits_panel.update("Loading exits...")
        
        # Force refresh the UI data by requesting an update from the game engine
        logger.debug(f"Before panel update - player_data exists: {self._player_data is not None}, world_data exists: {self._world_data is not None}")
        
        # Update all panels to their normal state
        self._update_inventory_panel()
        self._update_stats_panel()
        self._update_exits_panel()
        
        # If the exits panel still shows loading, set default message
        if "Loading exits..." in str(exits_panel.renderable) or not self._world_data or not self._player_data:
            logger.debug("Setting default messages for panels")
            exits_panel.update("Exits will appear here")
            if not self._player_data:
                self.query_one("#stats-panel").update("Stats will appear here")
        
        # Schedule a delayed refresh to ensure panels get updated once combat cleanup is complete
        def delayed_panel_refresh():
            logger.debug("Performing delayed panel refresh after combat")
            
            # Force clear exits panel again in case combat content is still showing
            exits_panel = self.query_one("#exits-panel")
            current_content = str(exits_panel.renderable)
            
            # If exits panel still contains combat-related content, force clear it
            if any(word in current_content.lower() for word in ["hp", "health", "battle", "⚔️", "🛡️"]):
                logger.debug("Combat content still detected in exits panel, force clearing")
                exits_panel.update("Exits will appear here")
            
            # Update all panels
            self._update_inventory_panel()
            self._update_stats_panel() 
            self._update_exits_panel()
            
            # Final check - if exits panel still has combat content, override it
            updated_content = str(exits_panel.renderable)
            if any(word in updated_content.lower() for word in ["hp", "health", "battle", "⚔️", "🛡️"]):
                logger.debug("Combat content STILL present after refresh, forcing clear")
                exits_panel.update("Exits will appear here")
        
        self.call_later(0.1, delayed_panel_refresh)
        
        logger.debug("Combat UI hidden, panels updated")
        
        input_field = self.query_one("#input-field")
        input_field.placeholder = "Enter command..."

    def _update_combat_panels(self):
        """Update all combat-related panels."""
        if not self._combat_session or not self._player_data:
            return
        
        self._update_combat_health_panel()
        self._update_combat_main_output()
        self._update_combat_stats_panel()
        self._update_inventory_panel()

    def _update_combat_health_panel(self):
        """Update exits panel with battle status during combat."""
        if not self._combat_session or not self._player_data:
            return
        
        # Get combat data
        enemy_name = self._combat_session.enemy_data.get("name", self._combat_session.enemy_id)
        enemy_health = self._combat_session.enemy_health
        enemy_max_health = self._combat_session.enemy_max_health
        
        player_health = self._player_data.health
        player_max_health = self._player_data.max_health
        
        # Create enhanced health bars with gradient styling
        player_bar = self._create_enhanced_health_bar(player_health, player_max_health, 12)
        enemy_bar = self._create_enhanced_health_bar(enemy_health, enemy_max_health, 12)
        
        # Simple battle status display
        battle_lines = [
            f"[bold red]⚔️ {enemy_name.upper()}[/bold red]",
            f"HP: {enemy_health}/{enemy_max_health}",
            enemy_bar,
            "",
            f"[bold green]🛡️ {self._player_data.name.upper()}[/bold green]",
            f"HP: {player_health}/{player_max_health}",
            player_bar
        ]
        
        content = "\n".join(battle_lines)
        self.query_one("#exits-panel").update(content)

    def _update_combat_main_output(self):
        """Update main output panel with combat log and actions."""
        if not self._combat_session or not self._player_data:
            return
        
        output_lines = []
        
        # Combat log section
        if self._combat_log:
            output_lines.append("[bold yellow]⚔️ COMBAT LOG ⚔️[/bold yellow]")
            output_lines.append("=" * 40)
            
            for action in self._combat_log[-10:]:
                actor = action.get('actor', 'system')
                message = action.get('message', 'Action performed')
                
                if actor == 'player':
                    output_lines.append(f"[green]👤 {message}[/green]")
                elif actor == 'enemy':
                    output_lines.append(f"[red]👹 {message}[/red]")
                else:
                    output_lines.append(f"[white]📋 {message}[/white]")
            
            output_lines.append("=" * 40)
        else:
            output_lines.extend([
                "[bold yellow]⚔️ BATTLE STARTED ⚔️[/bold yellow]",
                "=" * 40,
                "[white]Combat actions will appear here...[/white]",
                "=" * 40
            ])
        
        # Tutorial and hotkey display
        output_lines.extend([
            "",
            "[bold cyan]💡 COMBAT CONTROLS:[/bold cyan]",
            "[dim]• Press TAB to see detailed attack info[/dim]",
            "[dim]• Use number keys for quick attacks[/dim]",
            "[dim]• Type attack names or 'use item'[/dim]",
            "",
            self._get_dynamic_hotkey_display()
        ])
        
        content_text = "\n".join(output_lines)
        self.update_output(content_text)

    def _get_dynamic_hotkey_display(self):
        """Generate dynamic hotkey display based on available attacks."""
        if not self._player_data:
            return "[dim]Attack options loading...[/dim]"
        
        try:
            from src.combat import combat_system
            available_attacks = combat_system.get_available_attacks(
                self._player_data, 
                getattr(self._player_data, 'spells', [])
            )
            
            hotkey_lines = ["[bold green]QUICK ATTACKS:[/bold green]"]
            
            hotkey_num = 1
            for attack_id, attack_data in available_attacks.items():
                if hotkey_num > 9:
                    break
                
                attack_name = attack_data.get('name', attack_id)
                on_cooldown = attack_data.get('on_cooldown', False)
                
                if not on_cooldown:
                    # Calculate total damage
                    base_damage = self._player_data.calculate_damage() if hasattr(self._player_data, 'calculate_damage') else 0
                    bonus_damage = attack_data.get('bonus_damage', 0)
                    total_damage = base_damage + bonus_damage
                    accuracy = attack_data.get('accuracy', 100)
                    
                    hotkey_lines.append(f"[cyan][{hotkey_num}][/cyan] {attack_name} - [yellow]{total_damage} dmg[/yellow] ([dim]{accuracy}% hit[/dim])")
                    hotkey_num += 1
                else:
                    cooldown_remaining = attack_data.get('cooldown_remaining', 0)
                    hotkey_lines.append(f"[dim][{hotkey_num}] {attack_name} (cooldown: {cooldown_remaining}t)[/dim]")
                    hotkey_num += 1
            
            if hotkey_num == 1:
                hotkey_lines.append("[dim]No attacks available[/dim]")
            
            return "\n".join(hotkey_lines)
            
        except Exception as e:
            logger.error(f"Error generating hotkey display: {e}")
            return "[dim]Attack options loading...[/dim]"

    def _update_combat_stats_panel(self):
        """Update stats panel with combat-specific info and controls."""
        if not self._player_data:
            return
        
        stats_lines = []
        
        # Player info
        if hasattr(self._player_data, 'name'):
            stats_lines.append(f"[bold green]🛡️ {self._player_data.name.upper()}[/bold green]")
        if hasattr(self._player_data, 'player_class'):
            stats_lines.append(f"Class: {self._player_data.player_class.title()}")
        
        # Enhanced health display with gradient bar
        if hasattr(self._player_data, 'health') and hasattr(self._player_data, 'max_health'):
            health_percent = self._player_data.health / self._player_data.max_health
            health_color = "red" if health_percent < 0.3 else ("yellow" if health_percent < 0.7 else "green")
            enhanced_health_bar = self._create_enhanced_health_bar(self._player_data.health, self._player_data.max_health, 10)
            
            # Health status indicators
            health_status = ""
            if health_percent <= 0.15:
                health_status = " [red blink]💀 CRITICAL[/red blink]"
            elif health_percent <= 0.3:
                health_status = " [red]⚠️ LOW[/red]"
            elif health_percent >= 1.0:
                health_status = " [green]✨ FULL[/green]"
            
            stats_lines.extend([
                "",
                f"[{health_color}]❤️ HP: {self._player_data.health}/{self._player_data.max_health}[/]{health_status}",
                enhanced_health_bar
            ])
        
        # Attack power
        if hasattr(self._player_data, 'calculate_damage'):
            base_attack = self._player_data.calculate_damage()
            stats_lines.extend([
                "",
                f"[cyan]Base ATK: {base_attack}[/]"
            ])
        
        # Combat controls reminder
        stats_lines.extend([
            "",
            "[bold yellow]CONTROLS:[/bold yellow]",
            "[dim]TAB - Attack details[/dim]",
            "[dim]1-9 - Quick attacks[/dim]",
            "[dim]flee - Escape[/dim]"
        ])
        
        content = "\n".join(stats_lines)
        self.query_one("#stats-panel").update(content)

    # =====================================
    # ENHANCED STYLING METHODS
    # =====================================
    
    def _format_enhanced_inventory_item(self, item_id: str, item_data: dict, is_equipped: bool = False) -> str:
        """Format inventory item with enhanced visual styling."""
        from src.rarity import RaritySystem
        
        name = item_data.get("name", item_id)
        rarity = item_data.get("rarity", "common")
        rarity_color = RaritySystem.RARITY_COLORS[rarity]
        
        # Base item display with rarity styling
        item_text = f"[{rarity_color}]{name}[/{rarity_color}]"
        
        # Add rarity badge
        rarity_badge = f"[{rarity_color} dim]({rarity})[/]"
        
        # Add damage info for weapons
        damage_info = ""
        if item_data.get("type") == "weapon" and "damage" in item_data:
            damage = item_data["damage"]
            damage_info = f" [cyan]⚔ {damage}dmg[/cyan]"
        
        # Add equipped indicator with enhanced styling
        equipped_indicator = ""
        if is_equipped:
            equipped_indicator = " [green bold]⚡ EQUIPPED[/green bold]"
        
        # Add item type icons
        type_icon = self._get_item_type_icon(item_data.get("type", ""))
        
        return f"{type_icon} {item_text} {rarity_badge}{damage_info}{equipped_indicator}"
    
    def _get_item_type_icon(self, item_type: str) -> str:
        """Get appropriate icon for item type."""
        icons = {
            "weapon": "⚔️",
            "consumable": "🧪",
            "script": "📜",
            "key": "🗝️",
            "armor": "🛡️",
            "tool": "🔧",
            "misc": "📦"
        }
        return icons.get(item_type, "📄")
    
    def _apply_room_theme(self, room_id: str, room_data: dict):
        """Apply visual theme based on room characteristics."""
        # Remove all existing room classes
        for class_name in ["room-home", "room-dangerous", "room-safe"]:
            self.remove_class(class_name)
        
        # Determine room theme based on content and properties
        if room_id == "home" or "home" in room_id.lower():
            self.add_class("room-home")
        elif self._world_data and self._world_data.get_enemies_in_room(room_id):
            self.add_class("room-dangerous")
        elif room_data.get("safe", False) or "safe" in room_data.get("description", "").lower():
            self.add_class("room-safe")
    
    def _apply_game_state_styling(self, state: str):
        """Apply styling based on current game state."""
        # Remove all existing game state classes
        for class_name in ["game-state-exploring", "game-state-in-combat", "game-state-menu"]:
            self.remove_class(class_name)
        
        # Apply appropriate class based on state
        if state == "exploring":
            self.add_class("game-state-exploring")
        elif state == "in_combat":
            self.add_class("game-state-in-combat")
        elif state == "menu":
            self.add_class("game-state-menu")
    
    def _create_enhanced_health_bar(self, current: int, maximum: int, length: int = 12) -> str:
        """Create an enhanced health bar with gradient styling."""
        if maximum <= 0:
            return "[dim]▒▒▒▒▒▒▒▒▒▒▒▒[/dim]"
        
        health_percent = current / maximum
        filled_length = int(health_percent * length)
        empty_length = length - filled_length
        
        # Choose color and style based on health percentage
        if health_percent > 0.7:
            bar_color = "green"
            bar_char = "█"
        elif health_percent > 0.4:
            bar_color = "yellow"
            bar_char = "▓"
        elif health_percent > 0.15:
            bar_color = "red"
            bar_char = "▒"
        else:
            bar_color = "red blink"
            bar_char = "░"
        
        filled_bar = bar_char * filled_length
        empty_bar = "░" * empty_length
        
        return f"[{bar_color}]{filled_bar}[/{bar_color}][dim]{empty_bar}[/dim]"
    
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
        if effect_type == "damage":
            # Flash the border red briefly for damage
            if actor == "enemy":  # Enemy damaged player
                self.add_class("panel-update")
                self.call_later(0.3, lambda: self.remove_class("panel-update"))
            
            # Don't append to output during combat - the combat log handles this
            # Visual feedback is enough (border flash)
            
        elif effect_type == "heal":
            # Flash green for healing
            self.add_class("status-blessed")
            self.call_later(0.5, lambda: self.remove_class("status-blessed"))
            
            # Don't append to output during combat - the combat log handles this
            # Visual feedback is enough (border flash)

    # =====================================
    # PANEL UPDATE UTILITIES
    # =====================================

    def _update_all_panels_to_defaults(self):
        """Set all panels to default states."""
        if self.query("#inventory-panel"):
            self.query_one("#inventory-panel").update("Inventory will appear here")
        if self.query("#stats-panel"):
            self.query_one("#stats-panel").update("Stats will appear here")
        if self.query("#exits-panel"):
            self.query_one("#exits-panel").update("Exits will appear here")

    def _update_inventory_panel(self):
        """Update the inventory panel with current player data and enhanced styling."""
        if not self._player_data or not hasattr(self._player_data, 'inventory'):
            return
            
        if not self._player_data.inventory:
            content = "[dim italic]Empty inventory[/dim italic]"
        else:
            # Import rarity system
            from src.rarity import RaritySystem
            
            inventory_lines = []
            # Sort items by rarity (highest to lowest), then by name
            sorted_items = sorted(
                self._player_data.inventory.items(),
                key=lambda x: (-RaritySystem.get_rarity_order(x[1].get("rarity", "common")), x[1].get("name", x[0]))
            )
            
            # Enhanced inventory display with styling
            rarity_sections = {}
            for item_id, item_data in sorted_items:
                rarity = item_data.get("rarity", "common")
                if rarity not in rarity_sections:
                    rarity_sections[rarity] = []
                
                # Check if this item is equipped
                is_equipped = (hasattr(self._player_data, 'equipped_weapon') and 
                             item_id == self._player_data.equipped_weapon)
                
                # Use the rarity system to format the item with enhanced styling
                item_display = self._format_enhanced_inventory_item(item_id, item_data, is_equipped)
                rarity_sections[rarity].append(item_display)
            
            # Display items grouped by rarity
            rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]
            for rarity in rarity_order:
                if rarity in rarity_sections:
                    # Add rarity header with styling
                    rarity_header = f"[{RaritySystem.RARITY_COLORS[rarity]} bold]═══ {rarity.upper()} ═══[/]"
                    inventory_lines.append(rarity_header)
                    inventory_lines.extend(rarity_sections[rarity])
                    inventory_lines.append("")  # Empty line between sections
                
            content = "\n".join(inventory_lines).rstrip()
        
        if self.query("#inventory-panel"):
            # Add temporary visual feedback for inventory updates
            panel = self.query_one("#inventory-panel")
            panel.add_class("panel-update")
            panel.update(content)
            
            # Remove the update class after a brief moment
            def remove_update_class():
                try:
                    panel.remove_class("panel-update")
                except:
                    pass
            self.call_later(0.5, remove_update_class)

    def _update_stats_panel(self):
        """Update the stats panel with current player data."""
        logger.debug(f"_update_stats_panel called - player_data: {self._player_data is not None}")
        if not self._player_data:
            logger.debug("No player data available for stats panel")
            return
            
        stats_lines = []
        if hasattr(self._player_data, 'name'):
            stats_lines.append(f"[bold green]🛡️ {self._player_data.name.upper()}[/bold green]")
        if hasattr(self._player_data, 'player_class'):
            stats_lines.append(f"Class: {self._player_data.player_class.title()}")
            
        # Enhanced health display with bar
        if hasattr(self._player_data, 'health') and hasattr(self._player_data, 'max_health'):
            health_percent = self._player_data.health / self._player_data.max_health
            health_color = "red" if health_percent < 0.3 else ("yellow" if health_percent < 0.7 else "green")
            health_bar = self._create_health_bar(self._player_data.health, self._player_data.max_health, health_color, bar_length=12)
            stats_lines.extend([
                "",
                f"[{health_color}]HP: {self._player_data.health}/{self._player_data.max_health}[/]",
                health_bar
            ])
        
        # Add attack damage information
        if hasattr(self._player_data, 'calculate_damage'):
            total_attack_damage = self._player_data.calculate_damage()
            stats_lines.extend([
                "",
                f"[cyan]Attack: {total_attack_damage}[/]"
            ])
        
        content = "\n".join(stats_lines)
        if self.query("#stats-panel"):
            self.query_one("#stats-panel").update(content)

    def _update_exits_panel(self):
        """Update the exits panel with current world data."""
        logger.debug(f"_update_exits_panel called - world_data: {self._world_data is not None}, player_data: {self._player_data is not None}")
        
        if not self._world_data or not self._player_data:
            logger.debug(f"Missing data - world_data: {self._world_data}, player_data: {self._player_data}")
            return
            
        if hasattr(self._player_data, 'current_room') and hasattr(self._world_data, 'rooms'):
            current_room = getattr(self._player_data, 'current_room', None)
            logger.debug(f"Current room: {current_room}")
            if current_room and current_room in self._world_data.rooms:
                room_data = self._world_data.rooms[current_room]
                exits = room_data.get('exits', [])
                logger.debug(f"Found exits: {exits}")
                self.update_exits(exits)
            else:
                logger.debug(f"Room not found or invalid - current_room: {current_room}, available rooms: {list(self._world_data.rooms.keys()) if hasattr(self._world_data, 'rooms') else 'No rooms attr'}")
        else:
            logger.debug(f"Missing attributes - player has current_room: {hasattr(self._player_data, 'current_room')}, world has rooms: {hasattr(self._world_data, 'rooms')}")

    def _create_health_bar(self, current, maximum, color, bar_length=10):
        """Create ASCII health bar with customizable length."""
        if maximum <= 0:
            empty_bar = "▒" * bar_length
            return f"[gray]{empty_bar}[/gray]"
        
        filled = int((current / maximum) * bar_length)
        empty = bar_length - filled
        bar = "█" * filled + "▒" * empty
        return f"[{color}]{bar}[/{color}]"

    # =====================================
    # TITLE SCREEN & UI UTILITIES
    # =====================================

    def _display_title_screen(self):
        """Display the game title screen with typewriter effect."""
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
        
        title_text = Text(title_ascii, style="bold green", justify="center")
        menu_text = Text("\n1. New Game\n2. Load Game\n3. Exit\n\nEnter your choice: ", style="cyan")
        
        # Display title and story with typewriter effect
        initial_display = Text()
        initial_display.append_text(title_text)
        self.update_output(initial_display)
        
        def display_story_with_typewriter():
            """Display opening story with typewriter effect in background thread."""
            try:
                def story_callback(text: str):
                    combined_display = Text()
                    combined_display.append_text(title_text)
                    combined_display.append_text(Text.from_markup(text))
                    self.call_from_thread(self.update_output, combined_display)
                
                TypewriterPresets.NARRATIVE.type_text_sync(opening_story, story_callback)
                
                # Finally add menu options
                final_display = Text()
                final_display.append_text(title_text)
                final_display.append_text(Text.from_markup(opening_story))
                final_display.append_text(menu_text)
                self.call_from_thread(self.update_output, final_display)
                
            except Exception as e:
                logger.error(f"Typewriter effect failed for title screen: {e}")
                # Fallback to instant display
                combined_text = Text()
                combined_text.append_text(title_text)
                combined_text.append_text(Text.from_markup(opening_story))
                combined_text.append_text(menu_text)
                self.call_from_thread(self.update_output, combined_text)
        
        # Run typewriter effect in background thread
        story_thread = threading.Thread(target=display_story_with_typewriter, daemon=True)
        story_thread.start()

# =============================================================================
# DEV TOOLS: Log Viewer Modal
# =============================================================================

class LogViewerScreen(ModalScreen):
    """Modal overlay for viewing debug logs in real-time."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("l", "dismiss", "Close"),
    ]

    def __init__(self):
        super().__init__()
        self._log_position = 0
        self._refresh_timer = None

    def compose(self) -> ComposeResult:
        """Create log viewer UI."""
        yield RichLog(highlight=True, markup=False, id="log-display", max_lines=500)

    def on_mount(self) -> None:
        """Initialize log viewer when mounted."""
        from config.dev_config import DEBUG_LOG_FILE

        self.log_file = DEBUG_LOG_FILE
        log_widget = self.query_one("#log-display", RichLog)

        # Load last 100 lines from log file
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    # Get last 100 lines
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                    for line in recent_lines:
                        log_widget.write(line.rstrip())

                    # Track file position
                    f.seek(0, 2)  # Seek to end
                    self._log_position = f.tell()
            else:
                log_widget.write("[yellow]Debug log file not found. Logs will appear here when generated.[/yellow]")
        except Exception as e:
            log_widget.write(f"[red]Error loading log file: {e}[/red]")

        # Set up auto-refresh every 500ms
        self._refresh_timer = self.set_interval(0.5, self._refresh_log)

    def _refresh_log(self) -> None:
        """Refresh log content with new lines."""
        try:
            if not os.path.exists(self.log_file):
                return

            log_widget = self.query_one("#log-display", RichLog)

            with open(self.log_file, 'r') as f:
                # Seek to last read position
                f.seek(self._log_position)
                new_lines = f.readlines()

                # Append new lines
                for line in new_lines:
                    log_widget.write(line.rstrip())

                # Update position
                self._log_position = f.tell()

        except Exception as e:
            # Silently ignore errors during refresh
            pass

    def action_dismiss(self) -> None:
        """Close the log viewer."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        self.app.pop_screen()
