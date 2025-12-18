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
        event_bus.subscribe(EventType.GAME_OVER, self._on_game_over)
    
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
    
    def _load_game_data_for_load(self):
        """Load game data when loading a saved game - skip world state initialization."""
        logger.info("Loading game data for save game")
        
        # Load data using centralized data_loader functions
        rooms = load_room_data()
        enemies = load_enemy_data()
        
        # Load other data with existing methods
        items = self._load_items()
        npcs = self._load_data_from_dir('data/npcs', 'npcs')
        
        # Create game world without initializing state (will be loaded from save)
        self.world = GameWorld(rooms, items, enemies, npcs, initialize_state=False)
        
        logger.info("Game data loaded successfully for save game")
    
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
            elif game_state == GameState.TUTORIAL_NAME_INPUT:
                self._handle_tutorial_name_input(command)
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
    
    def _on_game_over(self, event):
        """Handle game over event and restart game based on player choice."""
        action = event.data.get("action")
        logger.info(f"Game over event received with action: {action}")
        
        if action == "quit":
            logger.info("Player chose to quit")
            self.cleanup()
            import sys
            sys.exit(0)
            
        elif action == "start_new_game":
            logger.info("Player chose to start new game - restarting")
            self._restart_new_game()
            
        elif action == "restart_from_save":
            logger.info("Player chose to restart from save - loading most recent save")
            self._restart_from_save()
    
    def _restart_new_game(self):
        """Restart the game with a fresh state."""
        try:
            logger.info("Restarting with new game")
            
            # Reset game state
            self.game_state = GameState.STARTING
            
            # Clear event history
            event_bus.clear_history()
            
            # Create new player (this will trigger character creation)
            from src.player import Player
            self.player = Player()
            
            # Reset world state by creating a new world instance
            from src.game_world import GameWorld
            self.world = GameWorld(self.items)
            
            # Create new command handler with fresh references
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            
            # Restart the game loop
            self.game_state = GameState.PLAYING
            
            # Update UI
            self._update_ui_panels()
            
            logger.info("New game restart completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to restart new game: {e}")
            self.ui.display_message(f"[bold red]Failed to start new game: {e}[/bold red]")
    
    def _restart_from_save(self):
        """Restart the game from the most recent save."""
        try:
            logger.info("Restarting from most recent save")
            
            from src.save import load_most_recent_save
            save_data = load_most_recent_save()
            
            if not save_data:
                logger.warning("No save data found, starting new game instead")
                self._restart_new_game()
                return
            
            # Restore player state
            player_data = save_data.get("player", {})
            from src.player import Player
            self.player = Player.from_dict(player_data)
            
            # Load fresh game data
            self._load_game_data_for_load()
            
            # Restore world state from save
            world_data = save_data.get("world", {})
            self.world.set_state(world_data)
            
            # Create new command handler
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            
            # Update UI
            self._update_ui_panels()
            
            logger.info("Save game restart completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to restart from save: {e}")
            self.ui.display_message(f"[bold red]Failed to load save: {e}. Starting new game instead...[/bold red]")
            self._restart_new_game()
    
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
            self.ui.update_output(f"[bold red]Invalid choice: {command}. Please enter 1, 2, or 3.[/bold red]\n")
            # Re-show the title screen to help the player
            import time
            time.sleep(1)  # Brief pause before re-displaying
            if hasattr(self.ui, '_display_title_screen'):
                self.ui._display_title_screen()
            else:
                self.ui.update_output("\n1. New Game\n2. Load Game\n3. Exit\n\nEnter your choice: ")
    
    def _start_new_game(self):
        """Start a new game by showing class selection first."""
        
        # Show class selection directly
        self._show_class_selection()
        
    def _load_game(self):
        """Load an existing game."""
        try:
            logger.debug("Starting load game process")
            # List available save files
            save_files = save_manager.get_save_files()
            logger.debug(f"Found {len(save_files)} save files")
            if not save_files:
                self.ui.update_output("[bold yellow]No save files found. Starting new game instead...[/bold yellow]\n")
                # Give user a moment to see the message
                import time
                time.sleep(1)
                self._start_new_game()
                return
            
            # For now, load the most recent save file
            # TODO: Add UI for save file selection
            latest_save_info = save_files[0]  # get_save_files returns sorted by date
            latest_save_filename = latest_save_info["filename"]
            self.ui.update_output(f"Loading game from {latest_save_filename} (Player: {latest_save_info['player_name']})...")
            
            # Load the save data
            save_data = save_manager.load_game(latest_save_filename)
            if not save_data:
                self.ui.update_output("Failed to load save file. Starting new game instead...")
                self._start_new_game()
                return
            
            # Restore player state
            player_data = save_data.get("player", {})
            from src.player import Player
            self.player = Player(
                name=player_data.get("name", "Unknown"),
                player_class=player_data.get("player_class", "guardian")
            )
            
            # Restore player stats and inventory
            self.player.health = player_data.get("health", self.player.max_health)
            self.player.max_health = player_data.get("max_health", self.player.max_health)
            self.player.total_damage = player_data.get("total_damage", self.player.total_damage)
            self.player.permanent_health_boost = player_data.get("permanent_health_boost", 0)
            self.player.permanent_damage_boost = player_data.get("permanent_damage_boost", 0)
            self.player.inventory = player_data.get("inventory", [])
            self.player.equipped_weapon = player_data.get("equipped_weapon")
            self.player.current_room = player_data.get("current_room", "home_grove")
            self.player.spells = player_data.get("spells", [])
            
            # Load fresh game data but don't initialize world state
            self._load_game_data_for_load()
            
            # Restore world state from save
            world_data = save_data.get("world", {})
            self.world.set_state(world_data)
            
            # Create command handler
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            
            self.ui.update_output(f"Game loaded successfully! Welcome back, {self.player.name}!")
            
            # Start the game loop
            self.game_state = GameState.PLAYING
            logger.debug(f"Game state set to {self.game_state}")
            
            # Emit game started event to update UI
            event_bus.emit_event(
                EventType.GAME_STARTED,
                {"player": self.player, "world": self.world},
                "ImprovedGameEngine"
            )
            
            # Update UI panels with loaded game state
            self._update_ui_panels()
            
            # Subscribe to events
            self.cmd_handler.setup_event_subscriptions()
            
            # Show current location with room entered event
            event_bus.emit_event(
                EventType.ROOM_ENTERED,
                {"player": self.player, "world": self.world},
                "ImprovedGameEngine"
            )
            
        except Exception as e:
            logger.error(f"Error loading game: {e}")
            self.ui.update_output(f"Error loading game: {e}. Starting new game instead...")
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
            self.ui.update_output("[bold red]Invalid choice. Please enter 1, 2, or 3.[/bold red]\n")
            # Re-show the class selection to help the player
            self._show_class_selection()
            return
            
        selected_class = class_map[choice]
        self.selected_class = selected_class  # Store for later use
        
        # Show tutorial introduction with ECHO asking for name
        self._show_tutorial_introduction()
    
    def _show_class_selection(self):
        """Display class selection screen."""
        try:
            class_info = """
[bold cyan]Choose Your Spirit Class:[/bold cyan]

[bold blue]1. Guardian[/bold blue]
A stalwart defender forged from binary steel. Guardians wield physical might in a world of fragile data. Their vast health and shield mastery let them stand against corrupted daemons head-on, though subtlety is not their domain.
   • [green]High Health (120 HP)[/green]
   • [yellow]Moderate Damage (10 DMG)[/yellow]  
   • [dim]Starter Weapon: Protocol Shield[/dim]

[bold red]2. Weaver[/bold red]  
Architects of raw system energy. Weavers manipulate data streams like incantations, unleashing destructive packets of code. Fragile in health but terrifying in power, they bend the filesystem itself to strike down foes.
   • [yellow]Moderate Health (90 HP)[/yellow]
   • [green]High Damage (15 DMG)[/green]
   • [dim]Starter Weapon: Byte Blaster[/dim]

[bold green]3. Shaman[/bold green]
Spirits attuned to the wild harmony of code and nature. The Shaman class balances restoration and offense, channeling echoes of lost data into versatile abilities. Neither the strongest nor the most fragile, they thrive in adaptability.
   • [yellow]Balanced Health (100 HP)[/yellow] 
   • [red]Low Damage (8 DMG)[/red]
   • [dim]Starter Weapon: Echo Staff[/dim]

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
    
    def _show_tutorial_introduction(self):
        """Show the tutorial introduction with ECHO asking for the player's name."""
        try:
            class_names = {
                "guardian": "Guardian",
                "weaver": "Weaver", 
                "shaman": "Shaman"
            }
            
            class_descriptions = {
                "guardian": "a defender of the core systems, wielding shields and restoration protocols",
                "weaver": "an aggressive code manipulator who exploits system vulnerabilities", 
                "shaman": "a mystic who communes with lost data and heals corrupted sectors"
            }
            
            selected_class_name = class_names.get(self.selected_class, "Unknown")
            selected_class_desc = class_descriptions.get(self.selected_class, "a mysterious entity")
            
            tutorial_intro = f"""
[bold cyan]>>> ECHO SYSTEM INITIALIZING... <<<[/bold cyan]

[dim]A faint digital whisper echoes through the corrupted filesystem...[/dim]

[bold green]ECHO:[/bold green] [italic]Spirit... I sense your presence in the digital void. 
You have chosen to manifest as a [bold]{selected_class_name}[/bold] - {selected_class_desc}.

The corruption spreads deeper each nanosecond. The Daemon Overlord's influence grows stronger.
But first, I must know... what shall I call you, spirit?

The old sysadmin records are fragmented. I need a name to anchor your essence 
to this haunted filesystem.[/italic]

[bold yellow]ECHO asks for your name:[/bold yellow]"""

            self.ui.update_output(tutorial_intro)
            self.game_state = GameState.TUTORIAL_NAME_INPUT
            
            # Notify UI of state change
            event_bus.emit_event(
                EventType.UI_STATE_CHANGED,
                {"new_state": self.game_state},
                "ImprovedGameEngine"
            )
            
        except Exception as e:
            logger.error(f"Error showing tutorial introduction: {e}")
            self.ui.update_output(f"Error showing tutorial introduction: {e}")
            self.game_state = GameState.MENU
    
    def _handle_tutorial_name_input(self, name: str):
        """Handle name input during tutorial."""
        if not name.strip():
            self.ui.update_output("\n[bold green]ECHO:[/bold green] [italic]I cannot hear you clearly, spirit. Please speak your name into the void...[/italic]\n")
            return
            
        player_name = name.strip()
        
        # Show ECHO's response with personalized message
        echo_response = f"""
[bold green]ECHO:[/bold green] [italic]Ah, {player_name}... I can feel your essence stabilizing.
The filesystem recognizes you now. Your spirit-signature is being written
to the root directory logs.

Welcome, {player_name}. The corrupted pathways await your touch.
Your journey as a {self.selected_class.title()} begins in the /home grove,
where fragments of your former self still linger...[/italic]

[dim]>>> INITIALIZING PLAYER MATRIX... <<<[/dim]
[dim]>>> LOADING SPIRIT INTERFACE... <<<[/dim]
[dim]>>> TUTORIAL MODE ENABLED <<<[/dim]
"""
        
        self.ui.update_output(echo_response)
        
        # Create player and start game
        if self.create_player(player_name, self.selected_class):
            self.initialize_special_items(self.selected_class)
            self.start_game()
        else:
            self.ui.update_output("Error creating player. Returning to main menu.")
            self.game_state = GameState.MENU
    
    def initialize_special_items(self, player_class: str):
        """Create and place special enhancement items based on player class."""
        if self.world:
            self.world.place_items(player_class)
            logger.info(f"Special items initialized for class: {player_class}")
    
    def _update_ui_panels(self):
        """Update all UI panels with current game state."""
        logger.debug(f"_update_ui_panels called - ui: {self.ui is not None}, player: {self.player is not None}, world: {self.world is not None}")
        if self.ui and self.player and self.world:
            try:
                logger.debug("Calling ui.update_game_state_panels...")
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
            self.player = Player(name=name, player_class=player_class)
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            
            # Set up event subscriptions for command handler
            self.cmd_handler.setup_event_subscriptions()
            
            # Show welcome tutorial
            self.cmd_handler.show_tutorial_hint("welcome")
            
            event_bus.emit_event(
                EventType.PLAYER_CREATED,
                {"player": self.player},
                "ImprovedGameEngine"
            )
            
            # Force UI panel updates after player creation
            self._update_ui_panels()
            
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
            
            # Update UI panels with initial game state
            logger.debug("Starting game - updating UI panels...")
            self._update_ui_panels()
            
            # Emit room entered event for starting room
            if self.player and hasattr(self.player, 'current_room'):
                event_bus.emit_event(
                    EventType.ROOM_ENTERED,
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
            
            # Clean up command handler event subscriptions
            if self.cmd_handler:
                self.cmd_handler.cleanup_event_subscriptions()
                
            # Unsubscribe from events
            event_bus.unsubscribe(EventType.COMMAND_ENTERED, self._on_command_entered)
            event_bus.unsubscribe(EventType.UI_READY, self._on_ui_ready)
            event_bus.unsubscribe(EventType.UI_ERROR, self._on_ui_error)
            event_bus.unsubscribe(EventType.GAME_SAVED, self._on_save_requested)
            event_bus.unsubscribe(EventType.COMBAT_STARTED, self._on_combat_started)
            event_bus.unsubscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
            event_bus.unsubscribe(EventType.GAME_OVER, self._on_game_over)
            
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
        
    except KeyboardInterrupt:
        logger.info("Game interrupted by user (Ctrl+C)")
        print("\n[yellow]Game interrupted![/yellow]")
        
        # Try to offer saving before exit if game is running
        try:
            if hasattr(engine, 'cmd_handler') and engine.cmd_handler and hasattr(engine, 'player') and engine.player:
                print("[bold yellow]You have unsaved progress![/bold yellow]")
                print("Would you like to save before quitting? (y/n): ", end='')
                import sys
                choice = input().lower().strip()
                
                if choice == 'y':
                    from src.save import save_manager
                    world_state = engine.world.get_state() if hasattr(engine, 'world') else {}
                    save_path = save_manager.save_game(engine.player, world_state)
                    print(f"[green]Game saved to: {save_path}[/green]")
                    
        except Exception as save_error:
            logger.error(f"Failed to save on interrupt: {save_error}")
            print("[red]Failed to save game[/red]")
            
        print("[yellow]Goodbye! Thanks for playing The Haunted Filesystem.[/yellow]")
        sys.exit(0)
        
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
