#!/usr/bin/env python3
"""
Improved Textual UI Implementation

This is a refactored version of the UI that removes circular dependencies
and uses events for communication with the game engine.
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Container, VerticalScroll, Horizontal
from textual.reactive import var
from rich.text import Text
from src.ui.ui_interface import UIProtocol, UIError, UIInitializationError, UIStateError
from src.events import event_bus, EventType
from src.game_states import GameState, UIState
import logging
import random
import os
from typing import Dict, Callable, Any, Optional

logger = logging.getLogger(__name__)

class TextualGameUI(App):
    """Improved Textual-based game UI with proper separation of concerns."""
    
    CSS_PATH = os.path.join(os.path.dirname(__file__), "ui.css")
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui_state = UIState.INITIALIZING
        self._setup_event_subscriptions()
        
        # UI state
        self._current_game_state = GameState.MENU
        self._player_data = None
        self._world_data = None
        self._combat_session = None
        
    def _setup_event_subscriptions(self):
        """Subscribe to relevant game events."""
        event_bus.subscribe(EventType.GAME_STARTED, self._on_game_started)
        event_bus.subscribe(EventType.GAME_OVER, self._on_game_over)
        event_bus.subscribe(EventType.PLAYER_STATS_CHANGED, self._on_player_stats_changed)
        event_bus.subscribe(EventType.PLAYER_INVENTORY_CHANGED, self._on_player_inventory_changed)
        event_bus.subscribe(EventType.ROOM_ENTERED, self._on_room_entered)
        event_bus.subscribe(EventType.UI_STATE_CHANGED, self._on_ui_state_changed)
        event_bus.subscribe(EventType.COMBAT_STARTED, self._on_combat_started)
        event_bus.subscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
    
    # Reactive variables for UI content
    header_content = var("The Haunted Filesystem")
    output_content = var("")
    
    message_history = []
    max_messages = 100
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Static(id="header")
        with Horizontal():
            with VerticalScroll(id="output-panel"):
                yield Static(self.output_content, id="output-display")
            with Container(id="sidebar"):
                yield Static("", id="inventory-panel")
                yield Static("", id="stats-panel") 
                yield Static("", id="exits-panel")
                yield Static("", id="combat-panel")
        yield Footer()
        yield Input(placeholder="Enter command...", id="input-field")
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        try:
            # Set border titles for the sidebar panels
            self.query_one("#inventory-panel").border_title = "Inventory"
            self.query_one("#stats-panel").border_title = "Stats"
            self.query_one("#exits-panel").border_title = "Exits"
            self.query_one("#combat-panel").border_title = "Combat"
            
            # Hide combat panel initially
            self.query_one("#combat-panel").display = False
            
            self.ui_state = UIState.READY  # Set ready state first
            self._update_all_panels_to_defaults()
            self._display_title_screen()
            
            # Ensure input field gets focus
            input_field = self.query_one("#input-field")
            input_field.focus()
            
            event_bus.emit_event(EventType.UI_READY, {}, "TextualGameUI")
            logger.info("TextualGameUI mounted successfully")
        except Exception as e:
            self.ui_state = UIState.ERROR
            logger.error(f"Error mounting TextualGameUI: {e}")
            event_bus.emit_event(EventType.UI_ERROR, {"error": str(e)}, "TextualGameUI")
            raise UIInitializationError(f"Failed to initialize UI: {e}")
    
    def shutdown(self) -> None:
        """Clean shutdown of UI resources."""
        try:
            self.ui_state = UIState.SHUTTING_DOWN
            # Unsubscribe from events
            event_bus.unsubscribe(EventType.GAME_STARTED, self._on_game_started)
            event_bus.unsubscribe(EventType.GAME_OVER, self._on_game_over)
            event_bus.unsubscribe(EventType.PLAYER_STATS_CHANGED, self._on_player_stats_changed)
            event_bus.unsubscribe(EventType.PLAYER_INVENTORY_CHANGED, self._on_player_inventory_changed)
            event_bus.unsubscribe(EventType.ROOM_ENTERED, self._on_room_entered)
            event_bus.unsubscribe(EventType.UI_STATE_CHANGED, self._on_ui_state_changed)
            event_bus.unsubscribe(EventType.COMBAT_STARTED, self._on_combat_started)
            event_bus.unsubscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
            logger.info("TextualGameUI shutdown complete")
        except Exception as e:
            logger.error(f"Error during UI shutdown: {e}")
    
    # Event handlers
    def _on_game_started(self, event):
        """Handle game started event."""
        self._current_game_state = GameState.PLAYING
        if 'player' in event.data:
            self._player_data = event.data['player']
        if 'world' in event.data:
            self._world_data = event.data['world']
    
    def _on_game_over(self, event):
        """Handle game over event."""
        self._current_game_state = GameState.GAME_OVER
        self.display_game_over()
    
    def _on_player_stats_changed(self, event):
        """Handle player stats changed event."""
        if 'player' in event.data:
            self._player_data = event.data['player']
            self._update_stats_panel()
            
            # Also update combat panel if in combat
            if self._current_game_state == GameState.IN_COMBAT and self._combat_session:
                self._update_combat_panel()
    
    def _on_player_inventory_changed(self, event):
        """Handle player inventory changed event."""
        if 'player' in event.data:
            self._player_data = event.data['player']
            self._update_inventory_panel()
    
    def _on_room_entered(self, event):
        """Handle room entered event."""
        if 'world' in event.data:
            self._world_data = event.data['world']
            self._update_exits_panel()
    
    def _on_ui_state_changed(self, event):
        """Handle UI state changed event."""
        new_state = event.data.get('new_state')
        if new_state:
            self._current_game_state = new_state
    
    def _on_combat_started(self, event):
        """Handle combat started event."""
        self._current_game_state = GameState.IN_COMBAT
        self._combat_session = event.data.get('session')
        self._show_combat_ui()
    
    def _on_combat_ended(self, event):
        """Handle combat ended event."""
        self._current_game_state = GameState.PLAYING
        self._combat_session = None
        self._hide_combat_ui()
    
    # UI Protocol implementation
    def update_output(self, content: str) -> None:
        """Update the main output display."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
        
        self.message_history.append(content)
        if len(self.message_history) > self.max_messages:
            self.message_history.pop(0)
        
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
        
        if self._player_data and hasattr(self._player_data, 'name'):
            player_name = self._player_data.name
        else:
            player_name = "Unknown Sysadmin"
            
        game_over_content = f"""[bold red]GAME OVER[/bold red]

[bold]System Critical Failure[/bold]

Brave sysadmin {player_name}, your session has been terminated.

[yellow]Press any key to return to the main menu...[/yellow]"""
        
        self.update_output(game_over_content)
        self.query_one("#input-field").focus()
    
    def update_game_state_panels(self, player: Any, world: Any) -> None:
        """Update all game state panels with current data."""
        if self.ui_state != UIState.READY:
            raise UIStateError("UI is not ready for updates")
            
        self._player_data = player
        self._world_data = world
        
        self._update_inventory_panel()
        self._update_stats_panel()
        self._update_exits_panel()
    
    def save_current_game(self) -> None:
        """Handle game saving UI feedback."""
        # Emit event to request game save
        event_bus.emit_event(EventType.GAME_SAVED, {"trigger": "ui_request"}, "TextualGameUI")
        
        # Show temporary save message
        save_text = Text("Game saved successfully!", style="green")
        self.update_output(save_text)
    
    # Watch methods for reactive variables
    def watch_header_content(self, content: str) -> None:
        if self.query("#header"):
            self.query_one("#header").update(Text(content, justify="center", style="bold cyan"))
    
    def watch_output_content(self, content: str) -> None:
        if self.query("#output-display"):
            self.query_one("#output-display").update(content)
    
    
    # Input handling
    def on_input_submitted(self, event: Input.Submitted):
        """Handle command input."""
        command = event.value.strip()
        event.input.value = ""
        
        
        if not command:
            return
            
        # Emit command event instead of direct engine access
        event_bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": command, "game_state": self._current_game_state},
            "TextualGameUI"
        )
    
    def on_key(self, event):
        """Handle any key press for debugging."""
        if event.key == "escape":
            self.exit()
    
    # Private UI methods
    def _display_title_screen(self):
        """Display the game title screen."""
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

Welcome to the Haunted Filesystem
A Terminal Adventure by Duhon Young'''
        
        title_text = Text(title_ascii, style="bold green", justify="center")
        menu_text = Text("\n\n1. New Game\n2. Load Game\n3. Exit\n\nEnter your choice: ", style="cyan")
        
        combined_text = Text()
        combined_text.append_text(title_text)
        combined_text.append_text(menu_text)
        
        self.update_output(combined_text)
    
    def _update_all_panels_to_defaults(self):
        """Set all panels to default states."""
        if self.query("#inventory-panel"):
            self.query_one("#inventory-panel").update("Inventory will appear here")
        if self.query("#stats-panel"):
            self.query_one("#stats-panel").update("Stats will appear here")
        if self.query("#exits-panel"):
            self.query_one("#exits-panel").update("Exits will appear here")
    
    def _update_inventory_panel(self):
        """Update the inventory panel with current player data."""
        if not self._player_data or not hasattr(self._player_data, 'inventory'):
            return
            
        if not self._player_data.inventory:
            content = "Empty"
        else:
            inventory_lines = [f"[yellow]• {item}[/]" for item in self._player_data.inventory]
            content = "\n".join(inventory_lines)
        
        if self.query("#inventory-panel"):
            self.query_one("#inventory-panel").update(content)
    
    def _update_stats_panel(self):
        """Update the stats panel with current player data."""
        if not self._player_data:
            return
            
        stats_lines = []
        if hasattr(self._player_data, 'name'):
            stats_lines.append(f"Name: {self._player_data.name}")
        if hasattr(self._player_data, 'player_class'):
            stats_lines.append(f"Class: {self._player_data.player_class}")
        if hasattr(self._player_data, 'health') and hasattr(self._player_data, 'max_health'):
            health_percent = self._player_data.health / self._player_data.max_health
            health_color = "red" if health_percent < 0.3 else "green"
            stats_lines.append(f"[{health_color}]Health: {self._player_data.health}[/]")
            stats_lines.append(f"[green]Max Health: {self._player_data.max_health}[/]")
        
        content = "\n".join(stats_lines)
        if self.query("#stats-panel"):
            self.query_one("#stats-panel").update(content)
    
    def _update_exits_panel(self):
        """Update the exits panel with current world data."""
        if not self._world_data or not self._player_data:
            return
            
        if hasattr(self._player_data, 'current_room') and hasattr(self._world_data, 'rooms'):
            current_room = getattr(self._player_data, 'current_room', None)
            if current_room and current_room in self._world_data.rooms:
                room_data = self._world_data.rooms[current_room]
                exits = room_data.get('exits', [])
                self.update_exits(exits)
    
    def _show_combat_ui(self):
        """Show combat UI and hide exploration panels."""
        # Hide exploration panels
        self.query_one("#inventory-panel").display = False
        self.query_one("#exits-panel").display = False
        
        # Show combat panel
        self.query_one("#combat-panel").display = True
        
        # Update combat panel content
        self._update_combat_panel()
        
        # Update placeholder text for combat
        input_field = self.query_one("#input-field")
        input_field.placeholder = "combat@system:~$ Enter command..."
    
    def _hide_combat_ui(self):
        """Hide combat UI and show exploration panels."""
        # Show exploration panels
        self.query_one("#inventory-panel").display = True
        self.query_one("#exits-panel").display = True
        
        # Hide combat panel
        self.query_one("#combat-panel").display = False
        
        # Reset placeholder text
        input_field = self.query_one("#input-field")
        input_field.placeholder = "Enter command..."
    
    def _update_combat_panel(self):
        """Update the combat panel with current combat state."""
        if not self._combat_session or not self._player_data:
            return
        
        # Get combat data
        enemy_name = self._combat_session.enemy_data.get("name", self._combat_session.enemy_id)
        enemy_health = self._combat_session.enemy_health
        enemy_max_health = self._combat_session.enemy_max_health
        
        player_health = self._player_data.health
        player_max_health = self._player_data.max_health
        
        # Create health bars
        player_bar = self._create_health_bar(player_health, player_max_health, "green")
        enemy_bar = self._create_health_bar(enemy_health, enemy_max_health, "red")
        
        # Build combat panel content
        combat_lines = [
            f"[bold red]⚔️ {enemy_name}[/bold red]",
            f"HP: {enemy_health}/{enemy_max_health}",
            enemy_bar,
            "",
            f"[bold green]🛡️ {self._player_data.name}[/bold green]",
            f"HP: {player_health}/{player_max_health}",
            player_bar,
            "",
            "[bold]Available Actions:[/bold]",
            "[dim]Type 'ls' for full list[/dim]"
        ]
        
        # Add quick attack reference
        from src.combat import combat_system
        if hasattr(combat_system, 'get_available_attacks'):
            try:
                available_attacks = combat_system.get_available_attacks(self._player_data, getattr(self._player_data, 'spells', []))
                attack_count = len([a for a in available_attacks.values() if not a.get("on_cooldown", False)])
                combat_lines.append(f"⚔️ {attack_count} attacks ready")
            except:
                pass
        
        # Add usable items count
        usable_items = []
        if hasattr(self._player_data, 'inventory'):
            for item_id, item_data in self._player_data.inventory.items():
                if item_data.get("usable") and "combat_usable" in item_data.get("tags", []):
                    usable_items.append(item_id)
        
        if usable_items:
            combat_lines.append(f"🧪 {len(usable_items)} items usable")
        
        content_text = "\n".join(combat_lines)
        
        if self.query("#combat-panel"):
            self.query_one("#combat-panel").update(Text.from_markup(content_text))
    
    def _create_health_bar(self, current, maximum, color):
        """Create ASCII health bar."""
        if maximum <= 0:
            return "[gray]▒▒▒▒▒▒▒▒▒▒[/gray]"
        
        bar_length = 10
        filled = int((current / maximum) * bar_length)
        empty = bar_length - filled
        bar = "█" * filled + "▒" * empty
        return f"[{color}]{bar}[/{color}] {current}/{maximum}"