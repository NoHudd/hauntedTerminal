#!/usr/bin/env python3
"""
Improved Game Engine

This is a refactored version of the game engine with:
- Proper separation of concerns
- Event-driven architecture
- Better error handling
- Proper lifecycle management
- No circular dependencies
"""

import os
import sys
import yaml
import logging
from typing import Optional, Dict, Any

# Import game components
from src.game_world import GameWorld
from src.player import Player
from src.command_handler import CommandHandler
from src.save import save_manager
from src.ui.textual_ui import TextualGameUI
from src.ui.ui_interface import UIProtocol, UIError, UIInitializationError
from src.events import event_bus, EventType
from src.game_states import GameState, DEFAULT_GAME_STATE, DEFAULT_ROOM
from src.data_loader import load_room_data, load_enemy_data

# Import debug tools
from utils.debug_tools import debug_log
from utils.error_handler import safe_execute, log_and_reraise

logger = logging.getLogger(__name__)

class GameEngineError(Exception):
    """Base exception for game engine errors."""
    pass

class DataLoadError(GameEngineError):
    """Raised when game data fails to load."""
    pass

class ImprovedGameEngine:
    """
    Improved game engine with proper architecture and error handling.
    
    Key improvements:
    - No circular dependencies
    - Event-driven communication
    - Proper error handling
    - Clean separation of concerns
    - Lifecycle management
    """
    
    def __init__(self, ui: Optional[UIProtocol] = None):
        """Initialize the game engine."""
        logger.info("Initializing ImprovedGameEngine")
        
        # Core state
        self.player: Optional[Player] = None
        self.world: Optional[GameWorld] = None
        self.cmd_handler: Optional[CommandHandler] = None
        self.current_room = DEFAULT_ROOM
        self.game_state = DEFAULT_GAME_STATE
        self.save_dir = "saves"
        self.pending_player_name = ""
        
        # UI system
        self.ui = ui or TextualGameUI()
        
        # Setup
        self._setup_directories()
        self._setup_event_subscriptions()
        
        # Load game data
        try:
            self._load_game_data()
        except Exception as e:
            logger.error(f"Failed to load game data: {e}")
            raise DataLoadError(f"Could not initialize game data: {e}")
    
    @log_and_reraise("setup directories", GameEngineError)
    def _setup_directories(self):
        """Ensure required directories exist."""
        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs("data/rooms", exist_ok=True)
        os.makedirs("data/items", exist_ok=True)
        os.makedirs("data/enemies", exist_ok=True)
        os.makedirs("data/npcs", exist_ok=True)
        logger.debug("Directories created/verified")
    
    def _setup_event_subscriptions(self):
        """Subscribe to relevant events."""
        event_bus.subscribe(EventType.COMMAND_ENTERED, self._on_command_entered)
        event_bus.subscribe(EventType.UI_READY, self._on_ui_ready)
        event_bus.subscribe(EventType.UI_ERROR, self._on_ui_error)
        event_bus.subscribe(EventType.GAME_SAVED, self._on_save_requested)
        event_bus.subscribe(EventType.COMBAT_STARTED, self._on_combat_started)
        event_bus.subscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
    
    @log_and_reraise("load game data", DataLoadError)
    def _load_game_data(self):
        """Load all game data from YAML files."""
        logger.info("Loading game data")
        
        # Load data using centralized data_loader functions
        rooms = load_room_data()
        enemies = load_enemy_data()
        
        # Load other data with existing methods
        items = self._load_items()
        npcs = self._load_data_from_dir('data/npcs', 'npcs')
        
        # Create world
        self.world = GameWorld(rooms, items, enemies, npcs)
        logger.info(f"Loaded {len(rooms)} rooms, {len(items)} items, {len(enemies)} enemies, {len(npcs)} NPCs")
    
    def _load_data_from_dir(self, directory: str, category_key: str) -> Dict[str, Any]:
        """Generic data loader for enemies and NPCs."""
        data_map = {}
        
        if not os.path.exists(directory):
            logger.warning(f"Directory {directory} does not exist")
            return data_map
            
        try:
            for filename in os.listdir(directory):
                if filename.endswith(('.yaml', '.yml')):
                    filepath = os.path.join(directory, filename)
                    with open(filepath, 'r') as file:
                        data = yaml.safe_load(file)
                        if data:
                            # Check if this is a nested structure (old format) or flat structure (new format)
                            if category_key in data:
                                # Old nested format: enemies: { enemy_id: { ... } }
                                for key, value in data.get(category_key, {}).items():
                                    value['id'] = key
                                    data_map[key] = value
                            else:
                                # New flat format: individual files with direct properties
                                # Use filename (without extension) as the ID
                                entity_id = os.path.splitext(filename)[0]
                                data['id'] = entity_id
                                data_map[entity_id] = data
                                
        except Exception as e:
            logger.error(f"Error loading data from {directory}: {e}")
            
        return data_map
    
    def _load_items(self) -> Dict[str, Any]:
        """Load all items from categorized YAML files into a single dictionary."""
        items = {}
        
        items_dir = 'data/items'
        if not os.path.exists(items_dir):
            logger.warning(f"Items directory {items_dir} does not exist")
            return items
            
        try:
            for filename in os.listdir(items_dir):
                if filename.endswith(('.yaml', '.yml')):
                    filepath = os.path.join(items_dir, filename)
                    with open(filepath, 'r') as file:
                        data = yaml.safe_load(file)
                        if data:
                            category = os.path.splitext(filename)[0]
                            for item_id, item_data in data.get(category, {}).items():
                                item_data['id'] = item_id
                                if 'type' not in item_data:
                                    item_data['type'] = category.rstrip('s')
                                items[item_id] = item_data
                                
        except Exception as e:
            logger.error(f"Error loading items: {e}")
            
        return items
    
    # Event handlers
    def _on_command_entered(self, event):
        """Handle command entered from UI."""
        command = event.data.get('command', '')
        game_state = event.data.get('game_state', self.game_state)
        
        logger.debug(f"Command entered: '{command}' (UI state: {game_state}, Engine state: {self.game_state})")
        
        try:
            if game_state == GameState.PLAYING and self.cmd_handler:
                self.cmd_handler.handle_command(command)
                self._update_ui_panels()
            elif game_state == GameState.IN_COMBAT and self.cmd_handler:
                self.cmd_handler.handle_command(command)
            elif game_state == GameState.MENU:
                self._handle_menu_command(command)
            elif game_state == GameState.WAITING_FOR_NAME:
                self._handle_name_input(command)
            elif game_state == GameState.WAITING_FOR_CLASS:
                self._handle_class_input(command)
            else:
                logger.debug(f"No specific handler for state {game_state}, defaulting to menu handler")
                self._handle_menu_command(command)
        except Exception as e:
            logger.error(f"Error handling command '{command}': {e}")
            self.ui.update_output(f"Error: {e}")
    
    def _on_ui_ready(self, event):
        """Handle UI ready event."""
        logger.info("UI is ready, starting main menu")
        self.game_state = GameState.MENU
    
    def _on_ui_error(self, event):
        """Handle UI error event."""
        error = event.data.get('error', 'Unknown UI error')
        logger.error(f"UI Error: {error}")
        # Could implement fallback UI here
    
    def _on_save_requested(self, event):
        """Handle save game request from UI."""
        try:
            if self.player and self.world:
                success = save_manager.save_game(self.player, self.world.get_state())
                if success:
                    logger.info("Game saved successfully")
                else:
                    logger.warning("Game save failed")
            else:
                logger.warning("Cannot save: no player or world data")
        except Exception as e:
            logger.error(f"Error saving game: {e}")
    
    def _on_combat_started(self, event):
        """Handle combat started event."""
        logger.info("Combat started, switching to IN_COMBAT state")
        self.game_state = GameState.IN_COMBAT
        
        # Notify UI of state change
        event_bus.emit_event(
            EventType.UI_STATE_CHANGED,
            {"new_state": self.game_state},
            "ImprovedGameEngine"
        )
    
    def _on_combat_ended(self, event):
        """Handle combat ended event."""
        logger.info("Combat ended, switching back to PLAYING state")
        self.game_state = GameState.PLAYING
        
        # Notify UI of state change
        event_bus.emit_event(
            EventType.UI_STATE_CHANGED,
            {"new_state": self.game_state},
            "ImprovedGameEngine"
        )
        
        # Update UI panels after combat
        self._update_ui_panels()
    
    def _handle_menu_command(self, command: str):
        """Handle commands in menu state."""
        logger.debug(f"Handling menu command: '{command}'")
        
        if command == "1":
            # New Game
            self._start_new_game()
        elif command == "2":
            # Load Game
            self._load_game()
        elif command == "3" or command.lower() == "exit":
            # Exit
            self.ui.update_output("Goodbye!")
            import sys
            sys.exit(0)
        else:
            self.ui.update_output(f"Invalid choice: {command}. Please enter 1, 2, or 3.")
    
    def _start_new_game(self):
        """Start a new game by prompting for player details."""
        
        # Prompt for player name
        self.ui.update_output("Enter your character name:")
        self.game_state = GameState.WAITING_FOR_NAME
        
        # Notify UI of state change
        event_bus.emit_event(
            EventType.UI_STATE_CHANGED, 
            {"new_state": self.game_state}, 
            "ImprovedGameEngine"
        )
        
    def _load_game(self):
        """Load an existing game."""
        # For now, show a message that load game isn't implemented
        self.ui.update_output("Load game feature coming soon! Starting new game instead...")
        self._start_new_game()
    
    def _handle_name_input(self, name: str):
        """Handle player name input."""
        if not name.strip():
            self.ui.update_output("Name cannot be empty. Please enter your character name:")
            return
            
        self.pending_player_name = name.strip()
        
        # Show class selection
        self._show_class_selection()
    
    def _handle_class_input(self, choice: str):
        """Handle player class selection."""
        class_map = {
            "1": "guardian", 
            "2": "weaver", 
            "3": "shaman"
        }
        
        if choice not in class_map:
            self.ui.update_output("Invalid choice. Please enter 1, 2, or 3:")
            return
            
        selected_class = class_map[choice]
        
        # Create player and start game
        if self.create_player(self.pending_player_name, selected_class):
            self.initialize_special_items(selected_class)
            self.start_game()
        else:
            self.ui.update_output("Error creating player. Returning to main menu.")
            self.game_state = GameState.MENU
    
    def _show_class_selection(self):
        """Display class selection screen."""
        try:
            class_info = """
[bold cyan]Choose Your Class:[/bold cyan]

[bold blue]1. Guardian[/bold blue] - [blue]Defenders of the core system[/blue]
   • [green]High Health (120 HP)[/green]
   • [yellow]Moderate Damage (10 DMG)[/yellow]  
   • [dim]Prefers: Safe zones, defensive equipment[/dim]
   • [italic]Playstyle: Defensive, steady progression[/italic]

[bold red]2. Weaver[/bold red] - [red]Aggressive code manipulators[/red]  
   • [yellow]Moderate Health (90 HP)[/yellow]
   • [green]High Damage (15 DMG)[/green]
   • [dim]Prefers: Dangerous zones, offensive equipment[/dim]
   • [italic]Playstyle: Aggressive, high risk/reward[/italic]

[bold green]3. Shaman[/bold green] - [green]Mystical data healers[/green]
   • [yellow]Balanced Health (100 HP)[/yellow] 
   • [red]Low Damage (8 DMG)[/red]
   • [dim]Prefers: Natural zones, mystical equipment[/dim]
   • [italic]Playstyle: Balanced, utility-focused[/italic]

[bold white]Enter your choice (1, 2, or 3):[/bold white]
            """
            
            self.ui.update_output(class_info)
            self.game_state = GameState.WAITING_FOR_CLASS
            
            # Notify UI of state change
            event_bus.emit_event(
                EventType.UI_STATE_CHANGED, 
                {"new_state": self.game_state}, 
                "ImprovedGameEngine"
            )
            
        except Exception as e:
            logger.error(f"Error showing class selection: {e}")
            self.ui.update_output(f"Error showing class selection: {e}")
            self.game_state = GameState.MENU
    
    def initialize_special_items(self, player_class: str):
        """Create and place special enhancement items based on player class."""
        if self.world:
            self.world.place_items(player_class)
            logger.info(f"Special items initialized for class: {player_class}")
    
    def _update_ui_panels(self):
        """Update all UI panels with current game state."""
        if self.ui and self.player and self.world:
            try:
                self.ui.update_game_state_panels(self.player, self.world)
                
                # Emit events for specific updates
                event_bus.emit_event(
                    EventType.PLAYER_STATS_CHANGED,
                    {"player": self.player},
                    "ImprovedGameEngine"
                )
                event_bus.emit_event(
                    EventType.PLAYER_INVENTORY_CHANGED,
                    {"player": self.player},
                    "ImprovedGameEngine"
                )
                
            except Exception as e:
                logger.error(f"Error updating UI panels: {e}")
    
    def create_player(self, name: str, player_class: str) -> bool:
        """Create a new player."""
        try:
            self.player = Player(player_class)
            self.player.name = name
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            
            # Show welcome tutorial
            self.cmd_handler.show_tutorial_hint("welcome")
            
            event_bus.emit_event(
                EventType.PLAYER_CREATED,
                {"player": self.player},
                "ImprovedGameEngine"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating player: {e}")
            return False
    
    def start_game(self):
        """Start the main game."""
        try:
            self.game_state = GameState.PLAYING
            
            event_bus.emit_event(
                EventType.GAME_STARTED,
                {"player": self.player, "world": self.world},
                "ImprovedGameEngine"
            )
            
        except Exception as e:
            logger.error(f"Error starting game: {e}")
            raise GameEngineError(f"Failed to start game: {e}")
    
    def end_game(self):
        """End the current game."""
        try:
            self.game_state = GameState.GAME_OVER
            
            event_bus.emit_event(
                EventType.GAME_OVER,
                {"player": self.player},
                "ImprovedGameEngine"
            )
            
            logger.info("Game ended")
            
        except Exception as e:
            logger.error(f"Error ending game: {e}")
    
    def run(self):
        """Main game loop that manages game states."""
        try:
            logger.info("Starting game engine")
            self.ui.run()
            
        except UIInitializationError as e:
            logger.error(f"UI initialization failed: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error in game loop: {e}")
            sys.exit(1)
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Clean up resources."""
        try:
            if hasattr(self.ui, 'shutdown'):
                self.ui.shutdown()
                
            # Unsubscribe from events
            event_bus.unsubscribe(EventType.COMMAND_ENTERED, self._on_command_entered)
            event_bus.unsubscribe(EventType.UI_READY, self._on_ui_ready)
            event_bus.unsubscribe(EventType.UI_ERROR, self._on_ui_error)
            event_bus.unsubscribe(EventType.GAME_SAVED, self._on_save_requested)
            event_bus.unsubscribe(EventType.COMBAT_STARTED, self._on_combat_started)
            event_bus.unsubscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
            
            logger.info("Game engine cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """The main entry point for the improved game."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        engine = ImprovedGameEngine()
        engine.run()
        
    except DataLoadError as e:
        logger.error(f"Data loading failed: {e}")
        print(f"Error: Could not load game data - {e}")
        sys.exit(1)
        
    except GameEngineError as e:
        logger.error(f"Game engine error: {e}")
        print(f"Error: Game engine failed - {e}")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
