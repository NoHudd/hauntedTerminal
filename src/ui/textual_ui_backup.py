#!/usr/bin/env python3
"""
Improved Textual UI Implementation

This is a refactored version of the UI that removes circular dependencies
and uses events for communication with the game engine.
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Container, VerticalScroll, Horizontal, Vertical
from textual.reactive import var
from rich.text import Text
from src.ui.ui_interface import UIProtocol, UIError, UIInitializationError, UIStateError
# Removed complex combat widgets for now
from src.events import event_bus, EventType
from src.game_states import GameState, UIState
from utils.typewriter import TypewriterPresets, create_typewriter_output_func
import logging
import random
import os
import threading
import time
from typing import Dict, Callable, Any, Optional

logger = logging.getLogger(__name__)

class TextualGameUI(App):
    """Improved Textual-based game UI with proper separation of concerns."""
    
    CSS_PATH = os.path.join(os.path.dirname(__file__), "ui.css")
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("1", "combat_hotkey_1", "Combat Hotkey 1"),
        ("2", "combat_hotkey_2", "Combat Hotkey 2"),
        ("3", "combat_hotkey_3", "Combat Hotkey 3"),
        ("4", "combat_hotkey_4", "Combat Hotkey 4"),
        ("5", "combat_hotkey_5", "Combat Hotkey 5"),
        ("6", "combat_hotkey_6", "Combat Hotkey 6"),
        ("7", "combat_hotkey_7", "Combat Hotkey 7"),
        ("8", "combat_hotkey_8", "Combat Hotkey 8"),
        ("9", "combat_hotkey_9", "Combat Hotkey 9"),
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
        self._combat_log = []  # Store recent combat actions
        
    def _setup_event_subscriptions(self):
        """Subscribe to relevant game events."""
        event_bus.subscribe(EventType.GAME_STARTED, self._on_game_started)
        event_bus.subscribe(EventType.GAME_OVER, self._on_game_over)
        event_bus.subscribe(EventType.PLAYER_STATS_CHANGED, self._on_player_stats_changed)
        event_bus.subscribe(EventType.PLAYER_INVENTORY_CHANGED, self._on_player_inventory_changed)
        event_bus.subscribe(EventType.ROOM_ENTERED, self._on_room_entered)
        event_bus.subscribe(EventType.UI_STATE_CHANGED, self._on_ui_state_changed)
        event_bus.subscribe(EventType.COMBAT_STARTED, self._on_combat_started)
        event_bus.subscribe(EventType.COMBAT_ACTION_RESULT, self._on_combat_action_result)
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
        yield Footer()
        yield Input(placeholder="Enter command...", id="input-field")
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        try:
            # Set border titles for the sidebar panels
            self.query_one("#inventory-panel").border_title = "Inventory"
            self.query_one("#stats-panel").border_title = "Stats"
            self.query_one("#exits-panel").border_title = "Exits"
            
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
            event_bus.unsubscribe(EventType.COMBAT_ACTION_RESULT, self._on_combat_action_result)
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
    
    def _on_combat_action_result(self, event):
        """Handle combat action result event with simple feedback."""
        action_data = event.data
        if action_data:
            self._combat_log.append(action_data)
            # Keep only last 5 combat actions
            if len(self._combat_log) > 5:
                self._combat_log.pop(0)
            
            # Update combat display with new action
            if self._current_game_state == GameState.IN_COMBAT:
                self._update_combat_panels()
    
    def _on_combat_ended(self, event):
        """Handle combat ended event."""
        self._current_game_state = GameState.PLAYING
        self._combat_session = None
        self._combat_log.clear()  # Clear combat log when combat ends
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
    
    # Combat hotkey action methods
    def action_combat_hotkey_1(self) -> None:
        """Handle combat hotkey 1."""
        self._execute_combat_hotkey(1)
        
    def action_combat_hotkey_2(self) -> None:
        """Handle combat hotkey 2."""
        self._execute_combat_hotkey(2)
        
    def action_combat_hotkey_3(self) -> None:
        """Handle combat hotkey 3."""
        self._execute_combat_hotkey(3)
        
    def action_combat_hotkey_4(self) -> None:
        """Handle combat hotkey 4."""
        self._execute_combat_hotkey(4)
        
    def action_combat_hotkey_5(self) -> None:
        """Handle combat hotkey 5."""
        self._execute_combat_hotkey(5)
        
    def action_combat_hotkey_6(self) -> None:
        """Handle combat hotkey 6."""
        self._execute_combat_hotkey(6)
        
    def action_combat_hotkey_7(self) -> None:
        """Handle combat hotkey 7."""
        self._execute_combat_hotkey(7)
        
    def action_combat_hotkey_8(self) -> None:
        """Handle combat hotkey 8."""
        self._execute_combat_hotkey(8)
        
    def action_combat_hotkey_9(self) -> None:
        """Handle combat hotkey 9."""
        self._execute_combat_hotkey(9)
    
    def _execute_combat_hotkey(self, hotkey_number: int):
        """Execute combat action based on hotkey number - only available attacks."""
        # Only process hotkeys during combat
        if self._current_game_state != GameState.IN_COMBAT:
            return
            
        try:
            # Get available attacks
            from src.combat import combat_system
            available_attacks = combat_system.get_available_attacks(
                self._player_data, 
                getattr(self._player_data, 'spells', [])
            )
            
            # Only include attacks that are NOT on cooldown
            available_list = []
            for attack_id, attack_data in available_attacks.items():
                if not attack_data.get('on_cooldown', False):
                    available_list.append((attack_id, attack_data))
            
            # Check if hotkey number is valid for available attacks
            if 1 <= hotkey_number <= len(available_list):
                attack_id, attack_data = available_list[hotkey_number - 1]
                
                # Emit combat action event
                event_bus.emit_event(
                    EventType.COMBAT_ACTION_SELECTED,
                    {"choice": attack_id},
                    "TextualGameUI"
                )
                
                # Show feedback with damage info
                attack_name = attack_data.get('name', attack_id)
                base_damage = self._player_data.calculate_damage() if hasattr(self._player_data, 'calculate_damage') else 0
                bonus_damage = attack_data.get('bonus_damage', 0)
                total_damage = base_damage + bonus_damage
                
                self.append_output(f"[green]⚔️ Executing {attack_name} ({total_damage} dmg)...[/green]")
            else:
                # Invalid hotkey or no attacks available
                self.update_output(f"[yellow]Hotkey [{hotkey_number}] not available. Check attack list above.[/yellow]")
            
        except Exception as e:
            logger.error(f"Error executing combat hotkey {hotkey_number}: {e}")
            self.update_output(f"[red]Error executing hotkey {hotkey_number}[/red]")
    
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

A Terminal Adventure by Duhon Young'''
        
        # Opening story text
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
        
        # Add typewriter effect for the opening story
        def display_story_with_typewriter():
            """Display opening story with typewriter effect in background thread."""
            try:
                def story_callback(text: str):
                    # Update display with title + progressive story text
                    combined_display = Text()
                    combined_display.append_text(title_text)
                    combined_display.append_text(Text.from_markup(text))
                    self.call_from_thread(self.update_output, combined_display)
                
                # Use dramatic typewriter for opening story
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
        
        # Run typewriter effect in background thread to avoid blocking UI
        story_thread = threading.Thread(target=display_story_with_typewriter, daemon=True)
        story_thread.start()
    
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
            # Import rarity system
            from src.rarity import RaritySystem
            
            inventory_lines = []
            # Sort items by rarity (highest to lowest), then by name
            sorted_items = sorted(
                self._player_data.inventory.items(),
                key=lambda x: (-RaritySystem.get_rarity_order(x[1].get("rarity", "common")), x[1].get("name", x[0]))
            )
            
            for item_id, item_data in sorted_items:
                # Check if this item is equipped
                is_equipped = (hasattr(self._player_data, 'equipped_weapon') and 
                             item_id == self._player_data.equipped_weapon)
                
                # Use the rarity system to format the item
                item_display = RaritySystem.format_inventory_item(item_id, item_data, is_equipped)
                inventory_lines.append(item_display)
                
            content = "\n".join(inventory_lines)
        
        if self.query("#inventory-panel"):
            self.query_one("#inventory-panel").update(content)
    
    def _update_stats_panel(self):
        """Update the stats panel with current player data."""
        if not self._player_data:
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
            stats_lines.append("")
            stats_lines.append(f"[{health_color}]HP: {self._player_data.health}/{self._player_data.max_health}[/]")
            stats_lines.append(health_bar)
        
        # Add attack damage information
        if hasattr(self._player_data, 'calculate_damage'):
            total_attack_damage = self._player_data.calculate_damage()
            stats_lines.append("")
            stats_lines.append(f"[cyan]Attack: {total_attack_damage}[/]")
        
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
        """Show combat UI by updating existing panels."""
        # Add combat-active class to enable combat styling
        self.add_class("combat-active")
        
        # Change exits panel to show battle info during combat
        self.query_one("#exits-panel").border_title = "Battle Status"
        
        # Update combat content in existing panels
        self._update_combat_panels()
        
        # Update placeholder text for combat
        input_field = self.query_one("#input-field")
        input_field.placeholder = "combat@system:~$ Enter command..."
    
    def _hide_combat_ui(self):
        """Hide combat UI and restore exploration panels."""
        # Remove combat-active class
        self.remove_class("combat-active")
        
        # Restore exits panel title
        self.query_one("#exits-panel").border_title = "Exits"
        
        # Update panels with regular game content
        self._update_inventory_panel()
        self._update_stats_panel()
        self._update_exits_panel()
        
        # Reset placeholder text
        input_field = self.query_one("#input-field")
        input_field.placeholder = "Enter command..."
    
    def _update_combat_panels(self):
        """Update combat UI using existing panels only."""
        if not self._combat_session or not self._player_data:
            return
        
        # Update exits panel with battle info
        self._update_combat_health_panel()
        
        # Update main output with combat log and hotkeys
        self._update_combat_main_output()
        
        # Update stats panel with hotkey reference
        self._update_combat_stats_panel()
        
        # Update inventory panel normally
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
        
        # Create animated health bars
        self._player_health_bar = AnimatedHealthBar(
            initial_health=player_health,
            max_health=player_max_health,
            entity_name=self._player_data.name,
            bar_color="green",
            bar_length=15,
            classes="animated-health-bar"
        )
        
        self._enemy_health_bar = AnimatedHealthBar(
            initial_health=enemy_health,
            max_health=enemy_max_health,
            entity_name=enemy_name,
            bar_color="red", 
            bar_length=15,
            classes="animated-health-bar"
        )
        
        # Mount health bars to the combat health display
        health_display = self.query_one("#combat-health-display")
        health_display.mount(self._player_health_bar)
        health_display.mount(self._enemy_health_bar)
    
    def _update_enhanced_combat_panels(self):
        """Update all enhanced combat panels with current data."""
        self._update_combat_health_bars()
        self._update_combat_log_panel()
        self._update_combat_actions_display()
    
    def _update_combat_health_bars(self):
        """Update health bars with current values."""
        if not self._combat_session or not self._player_data:
            return
            
        # Update player health bar
        if self._player_health_bar:
            self._player_health_bar.update_health(self._player_data.health, animate=True)
        
        # Update enemy health bar  
        if self._enemy_health_bar:
            self._enemy_health_bar.update_health(self._combat_session.enemy_health, animate=True)
    
    def _update_combat_log_panel(self):
        """Update the combat log with recent actions."""
        if not self._combat_log_panel:
            return
            
        # Combat log updates happen through the add_log_entry method
        # This is called when combat actions occur
        pass
    
    def _update_combat_actions_display(self):
        """Update the combat actions display with available options."""
        if not self._player_data:
            return
            
        # Get available attacks for hotkey display
        try:
            from src.combat import combat_system
            available_attacks = combat_system.get_available_attacks(
                self._player_data, 
                getattr(self._player_data, 'spells', [])
            )
            
            # Create action summary text
            action_lines = ["[bold cyan]⚔️ COMBAT ACTIONS[/bold cyan]", ""]
            
            # Add numbered hotkeys for attacks
            for i, (attack_id, attack_data) in enumerate(available_attacks.items()):
                if i >= 9:  # Limit to 9 hotkeys
                    break
                    
                hotkey = str(i + 1)
                attack_name = attack_data.get('name', attack_id)
                on_cooldown = attack_data.get('on_cooldown', False)
                
                if on_cooldown:
                    cooldown_remaining = attack_data.get('cooldown_remaining', 0)
                    action_lines.append(f"[dim][{hotkey}] {attack_name} (cooldown: {cooldown_remaining}t)[/dim]")
                else:
                    bonus_damage = attack_data.get('bonus_damage', 0)
                    accuracy = attack_data.get('accuracy', 100)
                    damage_text = f" (+{bonus_damage} dmg, {accuracy}% acc)" if bonus_damage > 0 else f" ({accuracy}% acc)"
                    action_lines.append(f"[green][{hotkey}] {attack_name}[/green][dim]{damage_text}[/dim]")
            
            # Add item usage
            usable_items = []
            if hasattr(self._player_data, 'inventory'):
                for item_id, item_data in self._player_data.inventory.items():
                    is_combat_usable = (
                        item_data.get("usable") and (
                            "combat_usable" in item_data.get("tags", []) or
                            item_data.get("usable_in_combat", False)
                        )
                    )
                    if is_combat_usable:
                        usable_items.append((item_id, item_data))
            
            if usable_items:
                action_lines.extend(["", "[bold yellow]💊 USABLE ITEMS[/bold yellow]"])
                for item_id, item_data in usable_items[:3]:  # Show first 3 items
                    item_name = item_data.get("name", item_id)
                    action_lines.append(f"[yellow]use {item_name}[/yellow]")
            
            action_lines.extend([
                "",
                "[dim]Type number for quick attack, or 'ls' for full list[/dim]"
            ])
            
            actions_text = Text.from_markup("\n".join(action_lines))
            self.update_output(actions_text)
            
        except Exception as e:
            logger.error(f"Error updating combat actions display: {e}")
    
    def _update_combat_panels(self):
        """Update combat UI - health in bottom panel, actions in main output."""
        if not self._combat_session or not self._player_data:
            return
        
        # Update health panel (bottom - exits panel)
        self._update_combat_health_panel()
        
        # Update inventory with detailed descriptions
        self._update_detailed_inventory_panel()
        
        # Update main output with available actions
        self._update_combat_actions_output()
        
    def _update_combat_health_panel(self):
        """Update the bottom panel (exits) with battle info during combat."""
        if not self._combat_session or not self._player_data:
            return
        
        # Get combat data
        enemy_name = self._combat_session.enemy_data.get("name", self._combat_session.enemy_id)
        enemy_health = self._combat_session.enemy_health
        enemy_max_health = self._combat_session.enemy_max_health
        
        player_health = self._player_data.health
        player_max_health = self._player_data.max_health
        
        # Get player attack stats
        player_attack = 0
        if hasattr(self._player_data, 'calculate_damage'):
            player_attack = self._player_data.calculate_damage()
        
        # Create health bars
        player_bar = self._create_health_bar(player_health, player_max_health, "green", bar_length=12)
        enemy_bar = self._create_health_bar(enemy_health, enemy_max_health, "red", bar_length=12)
        
        # Build comprehensive battle panel content
        battle_lines = [
            f"[bold red]⚔️ {enemy_name.upper()}[/bold red] - HP: [red]{enemy_health}/{enemy_max_health}[/red]",
            enemy_bar,
            "",
            f"[bold green]🛡️ {self._player_data.name.upper()}[/bold green] - HP: [green]{player_health}/{player_max_health}[/green] | ATK: [cyan]{player_attack}[/cyan]",
            player_bar
        ]
        
        # Add player class info
        if hasattr(self._player_data, 'player_class'):
            battle_lines.append(f"[dim]Class: {self._player_data.player_class.title()}[/dim]")
        
        content_text = "\n".join(battle_lines)
        
        if self.query("#exits-panel"):
            self.query_one("#exits-panel").update(Text.from_markup(content_text))
    
    def _update_combat_main_output(self):
        """Update main output panel with combat log and actions."""
        if not self._combat_session or not self._player_data:
            return
        
        output_lines = []
        
        # Combat log section
        if self._combat_log:
            output_lines.append("[bold yellow]⚔️ COMBAT LOG ⚔️[/bold yellow]")
            output_lines.append("=" * 40)
            
            # Show last 10 combat actions
            for action in self._combat_log[-10:]:
                actor = action.get('actor', 'system')
                message = action.get('message', 'Action performed')
                damage = action.get('damage', 0)
                
                if actor == 'player':
                    output_lines.append(f"[green]👤 {message}[/green]")
                elif actor == 'enemy':
                    output_lines.append(f"[red]👹 {message}[/red]")
                else:
                    output_lines.append(f"[white]📋 {message}[/white]")
            
            output_lines.append("=" * 40)
        else:
            output_lines.append("[bold yellow]⚔️ BATTLE STARTED ⚔️[/bold yellow]")
            output_lines.append("=" * 40)
            output_lines.append("[white]Combat actions will appear here...[/white]")
            output_lines.append("=" * 40)
        
        # Add hotkey instructions
        output_lines.extend([
            "",
            "[bold cyan]💡 COMBAT CONTROLS:[/bold cyan]",
            "[dim]• Press TAB to see detailed attack info[/dim]",
            "[dim]• Use number keys for quick attacks[/dim]",
            "[dim]• Type attack names or 'use item'[/dim]",
            ""
        ])
        
        # Dynamic hotkey display
        output_lines.append(self._get_dynamic_hotkey_display())
        
        content_text = "\n".join(output_lines)
        self.update_output(content_text)
    
    def _get_dynamic_hotkey_display(self):
        """Get dynamic hotkey display based on available attacks."""
        if not self._player_data:
            return ""
        
        try:
            from src.combat import combat_system
            available_attacks = combat_system.get_available_attacks(
                self._player_data, 
                getattr(self._player_data, 'spells', [])
            )
            
            hotkey_lines = ["[bold green]QUICK ATTACKS:[/bold green]"]
            
            # Only show hotkeys for available attacks
            hotkey_num = 1
            for attack_id, attack_data in available_attacks.items():
                if hotkey_num > 9:  # Limit to 9 hotkeys
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
            
            if hotkey_num == 1:  # No attacks available
                hotkey_lines.append("[dim]No attacks available[/dim]")
            
            return "\n".join(hotkey_lines)
            
        except Exception as e:
            logger.error(f"Error generating hotkey display: {e}")
            return "[dim]Attack options loading...[/dim]"
    
    def _update_combat_stats_panel(self):
        """Update stats panel with combat-specific info and controls hint."""
        if not self._player_data:
            return
        
        stats_lines = []
        
        # Player info
        if hasattr(self._player_data, 'name'):
            stats_lines.append(f"[bold green]🛡️ {self._player_data.name.upper()}[/bold green]")
        if hasattr(self._player_data, 'player_class'):
            stats_lines.append(f"Class: {self._player_data.player_class.title()}")
        
        # Health with visual bar
        if hasattr(self._player_data, 'health') and hasattr(self._player_data, 'max_health'):
            health_percent = self._player_data.health / self._player_data.max_health
            health_color = "red" if health_percent < 0.3 else ("yellow" if health_percent < 0.7 else "green")
            health_bar = self._create_health_bar(self._player_data.health, self._player_data.max_health, health_color, 8)
            stats_lines.extend([
                "",
                f"[{health_color}]HP: {self._player_data.health}/{self._player_data.max_health}[/]",
                health_bar
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
    
    def _update_detailed_inventory_panel(self):
        """Update inventory panel with detailed item descriptions during combat."""
        if not self._player_data or not hasattr(self._player_data, 'inventory'):
            return
            
        if not self._player_data.inventory:
            content = "Empty inventory"
        else:
            inventory_lines = []
            for item_id in self._player_data.inventory:
                item_data = self._player_data.inventory[item_id]
                
                # Get item info
                item_name = item_data.get("name", item_id)
                item_type = item_data.get("type", "")
                damage = item_data.get("damage", 0)
                usable = item_data.get("usable", False)
                
                # Build detailed display line
                item_display = f"[yellow]• {item_name}[/]"
                
                # Add type and stats
                if item_type == "weapon" and damage > 0:
                    item_display += f"\n  [dim]Weapon - {damage} damage[/dim]"
                elif item_type == "consumable":
                    item_display += f"\n  [dim]Consumable[/dim]"
                elif usable:
                    item_display += f"\n  [dim]Usable item[/dim]"
                
                # Check if equipped
                if hasattr(self._player_data, 'equipped_weapon') and item_id == self._player_data.equipped_weapon:
                    item_display += "\n  [cyan](equipped)[/]"
                
                # Add usability in combat - check both systems
                is_combat_usable = (
                    "combat_usable" in item_data.get("tags", []) or
                    item_data.get("usable_in_combat", False)
                )
                if is_combat_usable:
                    item_display += "\n  [green](combat ready)[/green]"
                
                inventory_lines.append(item_display)
            content = "\n\n".join(inventory_lines)
        
        if self.query("#inventory-panel"):
            self.query_one("#inventory-panel").update(Text.from_markup(content))
    
    def _update_combat_actions_output(self):
        """Update main output panel with available combat actions and combat log."""
        if not self._player_data:
            return
        
        action_lines = [
            "[bold cyan]═══ COMBAT COMMANDS ═══[/bold cyan]",
            "",
            "[bold]Basic Commands:[/bold]",
            "[yellow]• ls[/yellow] - Show all available options",
            "[yellow]• attack <name>[/yellow] - Use specific attack",
            "[yellow]• use <item>[/yellow] - Use combat item", 
            "[yellow]• flee[/yellow] - Attempt to escape",
            ""
        ]
        
        # Add available attacks
        from src.combat import combat_system
        if hasattr(combat_system, 'get_available_attacks'):
            try:
                available_attacks = combat_system.get_available_attacks(self._player_data, getattr(self._player_data, 'spells', []))
                ready_attacks = [name for name, data in available_attacks.items() if not data.get("on_cooldown", False)]
                
                if ready_attacks:
                    action_lines.append("[bold green]READY ATTACKS:[/bold green]")
                    for attack in ready_attacks:
                        attack_data = combat_system.get_attack_data(attack)
                        if attack_data:
                            damage_bonus = attack_data.get('bonus_damage', attack_data.get('damage', 0))
                            cooldown = attack_data.get('cooldown', 0)
                            attack_line = f"[cyan]• {attack}[/cyan]"
                            if damage_bonus > 0:
                                attack_line += f" [dim](+{damage_bonus} dmg)[/dim]"
                            if cooldown > 0:
                                attack_line += f" [dim]({cooldown}t cooldown)[/dim]"
                            action_lines.append(attack_line)
                        else:
                            action_lines.append(f"[cyan]• {attack}[/cyan]")
                    action_lines.append("")
            except:
                pass
        
        # Add usable items - check both tagging systems
        usable_items = []
        if hasattr(self._player_data, 'inventory'):
            for item_id, item_data in self._player_data.inventory.items():
                is_combat_usable = (
                    item_data.get("usable") and (
                        "combat_usable" in item_data.get("tags", []) or
                        item_data.get("usable_in_combat", False)
                    )
                )
                if is_combat_usable:
                    usable_items.append((item_id, item_data))
        
        if usable_items:
            action_lines.append("[bold green]COMBAT ITEMS:[/bold green]")
            for item_id, item_data in usable_items:
                item_name = item_data.get("name", item_id)
                # Check both old and new healing formats
                healing = item_data.get("healing", 0)
                if healing == 0 and "on_use" in item_data and "heal" in item_data["on_use"]:
                    healing = item_data["on_use"]["heal"]
                
                item_line = f"[green]• {item_name}[/green]"
                if healing > 0:
                    item_line += f" [dim](+{healing} HP)[/dim]"
                action_lines.append(item_line)
        
        # Add combat log section
        if self._combat_log:
            action_lines.extend([
                "",
                "━" * 40,
                "",
                "[bold yellow]COMBAT LOG:[/bold yellow]"
            ])
            
            # Show last 5 combat actions
            for action in self._combat_log[-5:]:
                actor = action.get('actor', 'Unknown')
                message = action.get('message', 'No message')
                damage = action.get('damage', 0)
                
                if actor == 'player':
                    action_lines.append(f"[green]👤 {message}[/green]")
                elif actor == 'enemy':
                    action_lines.append(f"[red]👹 {message}[/red]")
                else:
                    action_lines.append(f"[white]{message}[/white]")
        
        content_text = "\n".join(action_lines)
        
        # Update main output
        self.update_output(Text.from_markup(content_text))
    
    def _update_combat_actions_panel(self):
        """Update the right panel with available actions during combat."""
        if not self._player_data:
            return
        
        action_lines = [
            "[bold cyan]COMMANDS:[/bold cyan]",
            "[yellow]• ls[/yellow] - List all options",
            "[yellow]• attack <name>[/yellow] - Use attack",
            "[yellow]• use <item>[/yellow] - Use item",
            ""
        ]
        
        # Add available attacks
        from src.combat import combat_system
        if hasattr(combat_system, 'get_available_attacks'):
            try:
                available_attacks = combat_system.get_available_attacks(self._player_data, getattr(self._player_data, 'spells', []))
                ready_attacks = [name for name, data in available_attacks.items() if not data.get("on_cooldown", False)]
                
                if ready_attacks:
                    action_lines.append("[bold]ATTACKS READY:[/bold]")
                    for attack in ready_attacks[:5]:  # Show first 5 attacks
                        action_lines.append(f"[cyan]• {attack}[/cyan]")
                    if len(ready_attacks) > 5:
                        action_lines.append(f"[dim]+ {len(ready_attacks) - 5} more...[/dim]")
                    action_lines.append("")
            except:
                pass
        
        # Add usable items
        usable_items = []
        if hasattr(self._player_data, 'inventory'):
            for item_id, item_data in self._player_data.inventory.items():
                if item_data.get("usable") and "combat_usable" in item_data.get("tags", []):
                    usable_items.append(item_id)
        
        if usable_items:
            action_lines.append("[bold]USABLE ITEMS:[/bold]")
            for item in usable_items[:5]:  # Show first 5 items
                action_lines.append(f"[green]• {item}[/green]")
            if len(usable_items) > 5:
                action_lines.append(f"[dim]+ {len(usable_items) - 5} more...[/dim]")
        
        content_text = "\n".join(action_lines)
        
        if self.query("#stats-panel"):
            self.query_one("#stats-panel").update(Text.from_markup(content_text))
    
    def _update_combat_panel(self):
        """Legacy method - now delegates to the new split panel system."""
        self._update_combat_panels()
    
    def _create_health_bar(self, current, maximum, color, bar_length=10):
        """Create ASCII health bar with customizable length."""
        if maximum <= 0:
            empty_bar = "▒" * bar_length
            return f"[gray]{empty_bar}[/gray]"
        
        filled = int((current / maximum) * bar_length)
        empty = bar_length - filled
        bar = "█" * filled + "▒" * empty
        return f"[{color}]{bar}[/{color}]"