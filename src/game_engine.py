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
from src.state_manager import state_manager
from src.ui.view_builder import ViewBuilder

# Import debug tools
from utils.debug_tools import debug_log

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

        # Non-reloadable state
        self.save_dir = "saves"
        self.ui = ui or TextualGameUI()

        # Setup
        self._setup_directories()
        self._setup_event_subscriptions()

        # Initialize reloadable game components
        self._initialize_game_components()

    def _bind_ui_refs(self):
        """Refresh UI back-refs (player, world, room aliases) for autocomplete and tutorial."""
        if not self.ui:
            return
        self.ui._player_ref = self.player
        self.ui._world_ref = self.world
        if self.cmd_handler:
            self.ui._room_aliases_ref = self.cmd_handler.room_aliases

    def _initialize_game_components(self):
        """Initialize/reinitialize game components (reloadable)."""
        logger.info("Initializing game components")

        # Reset game state
        self.player: Optional[Player] = None
        self.world: Optional[GameWorld] = None
        self.cmd_handler: Optional[CommandHandler] = None
        self.current_room = DEFAULT_ROOM
        state_manager.set_state(DEFAULT_GAME_STATE, emit_event=False)
        self.pending_player_name = ""
        self._awaiting_skip_response: bool = False
        self._pending_player_name: str = ""

        # Load game data
        try:
            self._load_game_data()
        except Exception as e:
            logger.error(f"Failed to load game data: {e}")
            raise DataLoadError(f"Could not initialize game data: {e}")
    
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
        event_bus.subscribe(EventType.GAME_RESTART_REQUESTED, self._on_restart_requested)

    def restart_game(self):
        """Restart game state without closing UI - reloads all game data."""
        logger.info("Restarting game")

        # Reinitialize all game components (player, world, data)
        self._initialize_game_components()

        # Emit event to UI to reset display
        event_bus.emit_event(EventType.GAME_OVER, {"message": "Game restarted. Welcome back!"}, "GameEngine")

        logger.info("Game restart complete")

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

        # Validate cross-file references at startup
        self._validate_data_references(rooms, items, enemies)
    
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
    
    def _validate_data_references(self, rooms, items, enemies):
        """Validate cross-file references at startup. Logs errors for broken references."""
        errors = []

        # Load class data to validate starter weapons
        try:
            import yaml as _yaml
            with open("data/classes.yaml") as f:
                class_data = _yaml.safe_load(f).get("classes", {})
            for cls_name, cls_info in class_data.items():
                weapon = cls_info.get("starter_weapon")
                if weapon and weapon not in items:
                    errors.append(f"Class '{cls_name}' starter_weapon '{weapon}' not found in items")
        except Exception as e:
            errors.append(f"Could not validate class data: {e}")

        for room_id, room in rooms.items():
            # Room item references
            for item_id in room.get("items", []):
                if item_id not in items:
                    errors.append(f"Room '{room_id}' references unknown item '{item_id}'")
            # Room enemy references
            for enemy_id in room.get("enemies", []):
                if enemy_id not in enemies:
                    errors.append(f"Room '{room_id}' references unknown enemy '{enemy_id}'")

        for enemy_id, enemy in enemies.items():
            # Enemy drop references
            for drop in enemy.get("drops", []):
                drop_item = drop.get("item")
                if drop_item and drop_item not in items:
                    errors.append(f"Enemy '{enemy_id}' drop references unknown item '{drop_item}'")

        if errors:
            for msg in errors:
                logger.error(f"[DATA VALIDATION] {msg}")
            logger.error(f"[DATA VALIDATION] {len(errors)} reference error(s) found — check YAML files")
        else:
            logger.info("[DATA VALIDATION] All cross-file references OK")

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

        for filename in os.listdir(items_dir):
            if filename.endswith(('.yaml', '.yml')):
                filepath = os.path.join(items_dir, filename)
                try:
                    with open(filepath, 'r') as file:
                        data = yaml.safe_load(file)
                        if data:
                            category = os.path.splitext(filename)[0]
                            category_items = data.get(category, {})
                            if category_items:
                                for item_id, item_data in category_items.items():
                                    if item_data:  # Make sure item_data isn't None
                                        item_data['id'] = item_id
                                        if 'type' not in item_data:
                                            item_data['type'] = category.rstrip('s')
                                        items[item_id] = item_data
                                logger.debug(f"Loaded {len(category_items)} items from {filename}")
                            else:
                                logger.warning(f"No items found in {filename} under key '{category}'")
                except Exception as e:
                    logger.error(f"Error loading items from {filename}: {e}")

        logger.info(f"Total items loaded: {len(items)}")
        return items
    
    # Event handlers
    def _on_command_entered(self, event):
        """Handle command entered from UI."""
        command = event.data.get('command', '')
        game_state = event.data.get('game_state', state_manager.current_state)

        logger.debug(f"Command entered: '{command}' (UI state: {game_state}, Engine state: {state_manager.current_state})")
        
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
            elif game_state == GameState.GAME_OVER:
                # Any keypress from game over screen → return to main menu
                logger.debug("GAME_OVER state: transitioning to MENU")
                state_manager.set_state(GameState.MENU)
                if hasattr(self.ui, '_display_title_screen'):
                    self.ui._display_title_screen()
                else:
                    self.ui.update_output("\n1. New Game\n2. Load Game\n3. Exit\n\nEnter your choice: ")
            else:
                logger.debug(f"No specific handler for state {game_state}, defaulting to menu handler")
                self._handle_menu_command(command)
        except Exception as e:
            logger.error(f"Error handling command '{command}': {e}")
            self.ui.update_output(f"Error: {e}")
    
    def _on_ui_ready(self, event):
        """Handle UI ready event."""
        logger.info("UI is ready, starting main menu")
        state_manager.set_state(GameState.MENU)
    
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
        logger.info("Combat started, entering combat state")
        state_manager.enter_combat()
    
    def _on_combat_ended(self, event):
        """Handle combat ended event."""
        logger.info("Combat ended, exiting combat state")

        # Check if player was defeated - trigger game over immediately
        if event.data.get('defeat', False):
            logger.info("Player defeated in combat - triggering game over")
            state_manager.set_state(GameState.GAME_OVER)
            event_bus.emit_event(
                EventType.GAME_OVER,
                {"message": "[bold red]GAME OVER[/bold red]\n\nYou have been defeated in combat.\n\nPress any key to continue..."},
                "GameEngine"
            )
            return  # Don't continue with normal combat end processing

        # Use StateManager to exit combat
        state_manager.exit_combat()

        # Update UI panels after combat
        self._update_ui_panels()

        # On flee, CommandHandler relocates player + emits ROOM_ENTERED itself.
        # Emitting here would fire check_for_enemies on the room they just fled,
        # restarting combat before the flee handler can mark the enemy fled.
        if event.data.get("fled", False):
            return

        # Emit ROOM_ENTERED to refresh exits panel and restore full UI state
        if self.world and self.player:
            # Build room view for current room
            room_view = ViewBuilder.build_room_view(self.world, self.player.current_room)

            event_bus.emit_event(
                EventType.ROOM_ENTERED,
                {
                    "room": room_view.to_dict(),
                    "player_name": self.player.name
                },
                "ImprovedGameEngine"
            )
    
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

    def _on_restart_requested(self, event):
        """Handle game restart request from UI (F5 key)."""
        logger.info("Game restart requested from UI")
        self.restart_game()

    def _restart_new_game(self):
        """Restart the game with a fresh state."""
        try:
            logger.info("Restarting with new game")

            # Reset game state
            state_manager.set_state(GameState.MENU, emit_event=False)

            # Clear event history
            event_bus.clear_history()

            # Unsubscribe stale handlers before replacing them
            if self.cmd_handler:
                self.cmd_handler.cleanup_event_subscriptions()

            # Create new player (this will trigger character creation)
            from src.player import Player
            self.player = Player()

            # Reset world state by reloading all game data
            self._load_game_data()

            # Create new command handler with fresh references
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            self._bind_ui_refs()

            # Restart the game loop
            state_manager.set_state(GameState.PLAYING)

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
            self._bind_ui_refs()

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
        """Start a new game by reloading world data and showing class selection."""

        # Clean up stale event subscriptions from previous session
        if self.cmd_handler:
            self.cmd_handler.cleanup_event_subscriptions()
            self.cmd_handler = None

        # Reload world data so the new game starts with a fresh world state
        self._load_game_data()

        # Show class selection
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
            self.player = Player.from_dict(player_data)
            
            # Load fresh game data but don't initialize world state
            self._load_game_data_for_load()
            
            # Restore world state from save
            world_data = save_data.get("world", {})
            self.world.set_state(world_data)
            
            # Create command handler
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            self._bind_ui_refs()

            self.ui.update_output(f"Game loaded successfully! Welcome back, {self.player.name}!")

            # Start the game loop
            state_manager.set_state(GameState.PLAYING)
            logger.debug(f"Game state set to {state_manager.current_state}")

            # Emit game started event to update UI
            stats_view = ViewBuilder.build_stats_view(self.player)
            inventory_view = ViewBuilder.build_inventory_view(self.player)

            event_bus.emit_event(
                EventType.GAME_STARTED,
                {
                    "stats": stats_view.to_dict(),
                    "inventory": inventory_view.to_dict()
                },
                "ImprovedGameEngine"
            )

            # Update UI panels with loaded game state
            self._update_ui_panels()

            # Subscribe to events
            self.cmd_handler.setup_event_subscriptions()

            # Show current location with room entered event
            room_view = ViewBuilder.build_room_view(self.world, self.player.current_room)

            event_bus.emit_event(
                EventType.ROOM_ENTERED,
                {
                    "room": room_view.to_dict(),
                    "player_name": self.player.name
                },
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
        from src.data_loader import load_class_data
        classes = load_class_data()
        class_map = {str(i): class_id for i, class_id in enumerate(classes.keys(), 1)}

        if choice not in class_map:
            valid = ", ".join(class_map.keys())
            self.ui.update_output(f"[bold red]Invalid choice. Please enter {valid}.[/bold red]\n")
            self._show_class_selection()
            return
            
        selected_class = class_map[choice]
        self.selected_class = selected_class  # Store for later use
        
        # Show tutorial introduction with ECHO asking for name
        self._show_tutorial_introduction()
    
    _CLASS_ICONS = {
        "guardian": "🛡 ",
        "weaver":   "✨",
        "shaman":   "🌿",
    }

    def _show_class_selection(self):
        """Display class selection as auto-sized Rich Panels stacked vertically.
        Rich handles box drawing + width, so emoji widths and panel resizing
        never break the borders."""
        try:
            from src.data_loader import load_class_data
            from rich.panel import Panel
            from rich.console import Group
            from rich.text import Text
            from rich.align import Align
            from rich.rule import Rule

            classes = load_class_data()

            renderables = [
                Text(""),
                Align.center(Text("⚙  CHOOSE YOUR SPIRIT CLASS  ⚙", style="bold cyan")),
                Rule(style="cyan"),
                Text(""),
            ]

            for i, (class_id, cls) in enumerate(classes.items(), 1):
                d = cls.get("display", {})
                color = d.get("color", "white")
                hp_color = d.get("hp_color", "white")
                dmg_color = d.get("dmg_color", "white")
                icon = self._CLASS_ICONS.get(class_id, "•")
                name = cls.get("name", class_id).upper()
                tagline = cls.get("description", "").split(" - ", 1)
                tagline_main = tagline[0] if tagline else ""
                tagline_sub = tagline[1] if len(tagline) > 1 else ""
                hp = d.get("hp_label", "")
                dmg = d.get("dmg_label", "")
                weapon = d.get("weapon_name", "")
                pref = ", ".join(cls.get("preferred_zones", []) or [])

                body = Text()
                body.append(tagline_main + "\n", style="italic")
                if tagline_sub:
                    body.append(tagline_sub + "\n", style="dim")
                body.append("\n")
                body.append("❤  ", style="red")
                body.append(hp + "\n", style=hp_color)
                body.append("⚔  ", style="yellow")
                body.append(dmg + "\n", style=dmg_color)
                body.append("🗡 ", style="white")
                body.append("Weapon: ", style="dim")
                body.append(weapon + "\n")
                if pref:
                    body.append("🗺 ", style="white")
                    body.append("Zones: ", style="dim")
                    body.append(pref)

                panel = Panel(
                    body,
                    title=f"[bold {color}][{i}]  {icon} {name}[/bold {color}]",
                    title_align="left",
                    border_style=color,
                    padding=(1, 2),
                    expand=True,
                )
                renderables.append(panel)
                renderables.append(Text(""))

            renderables.append(
                Text(f"Enter your choice (1–{len(classes)}):", style="bold white")
            )

            group = Group(*renderables)
            if hasattr(self.ui, "update_output_renderable"):
                self.ui.update_output_renderable(group)
            else:
                # Fallback for non-Textual UIs — render to console string.
                from rich.console import Console
                con = Console(record=True, width=100)
                con.print(group)
                self.ui.update_output(con.export_text(styles=True))

            state_manager.set_state(GameState.WAITING_FOR_CLASS)

        except Exception as e:
            logger.error(f"Error showing class selection: {e}")
            self.ui.update_output(f"Error showing class selection: {e}")
            state_manager.set_state(GameState.MENU)
    
    def _show_tutorial_introduction(self):
        """Show the tutorial introduction with ECHO asking for the player's name."""
        try:
            from src.data_loader import load_class_data
            classes = load_class_data()
            cls = classes.get(self.selected_class, {})
            selected_class_name = cls.get("name", self.selected_class.title())
            selected_class_desc = cls.get("display", {}).get("echo_description", "a mysterious entity")
            
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
            state_manager.set_state(GameState.TUTORIAL_NAME_INPUT)

        except Exception as e:
            logger.error(f"Error showing tutorial introduction: {e}")
            self.ui.update_output(f"Error showing tutorial introduction: {e}")
            state_manager.set_state(GameState.MENU)
    
    def _handle_tutorial_name_input(self, name: str):
        """Handle name input during tutorial — includes skip offer flow."""
        # If awaiting skip response, handle it
        if self._awaiting_skip_response:
            self._handle_skip_response(name.strip().lower())
            return

        # Validate name
        if not name.strip():
            self.ui.update_output(
                "\n[bold green]ECHO:[/bold green] I didn't catch that. What's your name?\n"
            )
            return

        player_name = name.strip()
        self._pending_player_name = player_name

        # Create player (tutorial_state is initialized on the player object)
        if not self.create_player(player_name, self.selected_class):
            self.ui.update_output("Error creating player. Returning to main menu.")
            state_manager.set_state(GameState.MENU)
            return

        self.initialize_special_items(self.selected_class)

        # Show skip offer
        self._awaiting_skip_response = True
        self.player.tutorial_state["skip_offered"] = True
        self.ui.update_output(
            f"\n[bold green]ECHO:[/bold green] Welcome, [bold]{player_name}[/bold]. "
            f"Want a quick tutorial? It covers all the commands you'll need.\n\n"
            f"[bold yellow](yes / skip)[/bold yellow]\n"
        )

    def _handle_skip_response(self, response: str):
        """Handle yes/no response to the tutorial skip offer."""
        self._awaiting_skip_response = False
        negative_words = {"no", "skip", "n", "nope", "nah", "pass"}
        skipping = (response in negative_words or
                    response.startswith("skip") or
                    response.startswith("no"))

        if skipping:
            # Skip tutorial: mark complete and show quick summary
            self.player.tutorial_state["completed"] = True
            self.ui.update_output(
                "\n[bold green]ECHO:[/bold green] Got it. Quick reference: "
                "[bold]ls[/bold] scans a room, [bold]take/equip[/bold] grab and ready items, "
                "[bold]attack[/bold] fights enemies. In combat, press [bold]TAB[/bold] to enter "
                "Selection Mode then [bold]1-9[/bold] to attack. "
                "[bold]flee[/bold] escapes a fight. [bold]help[/bold] if stuck. Good luck.\n"
            )
            self.start_game()
        else:
            # Tutorial path: show Step 1 hint, then start game
            self.cmd_handler.show_tutorial_hint("step1")
            self.start_game()
    
    def initialize_special_items(self, player_class: str):
        """Create and place special enhancement items based on player class."""
        if self.world:
            self.world.place_items(player_class)
            logger.info(f"Special items initialized for class: {player_class}")
    
    def _update_ui_panels(self):
        """Update all UI panels by emitting view-model events."""
        if self.ui and self.player and self.world:
            try:
                stats_view = ViewBuilder.build_stats_view(self.player)
                inventory_view = ViewBuilder.build_inventory_view(self.player)
                event_bus.emit_event(EventType.PLAYER_STATS_CHANGED, stats_view.to_dict(), "ImprovedGameEngine")
                event_bus.emit_event(EventType.PLAYER_INVENTORY_CHANGED, inventory_view.to_dict(), "ImprovedGameEngine")
            except Exception as e:
                logger.error(f"Error updating UI panels: {e}")
    
    def create_player(self, name: str, player_class: str) -> bool:
        """Create a new player."""
        try:
            self.player = Player(name=name, player_class=player_class)
            self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
            self._bind_ui_refs()

            # Set up event subscriptions for command handler
            self.cmd_handler.setup_event_subscriptions()

            # Place class-appropriate starter items in home_grove
            if self.world:
                self.world.place_starter_items(player_class)
                logger.info(f"Placed starter items for {player_class} in home_grove")

            # Build view for player creation event
            stats_view = ViewBuilder.build_stats_view(self.player)

            event_bus.emit_event(
                EventType.PLAYER_CREATED,
                stats_view.to_dict(),
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
            state_manager.set_state(GameState.PLAYING)

            # Build views for game start
            stats_view = ViewBuilder.build_stats_view(self.player)
            inventory_view = ViewBuilder.build_inventory_view(self.player)

            event_bus.emit_event(
                EventType.GAME_STARTED,
                {
                    "stats": stats_view.to_dict(),
                    "inventory": inventory_view.to_dict()
                },
                "ImprovedGameEngine"
            )

            # Update UI panels with initial game state
            logger.debug("Starting game - updating UI panels...")
            self._update_ui_panels()

            # Emit room entered event for starting room
            if self.player and hasattr(self.player, 'current_room'):
                room_view = ViewBuilder.build_room_view(self.world, self.player.current_room)

                event_bus.emit_event(
                    EventType.ROOM_ENTERED,
                    {
                        "room": room_view.to_dict(),
                        "player_name": self.player.name
                    },
                    "ImprovedGameEngine"
                )
            
        except Exception as e:
            logger.error(f"Error starting game: {e}")
            raise GameEngineError(f"Failed to start game: {e}")
    
    def end_game(self):
        """End the current game."""
        try:
            state_manager.set_state(GameState.GAME_OVER)

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
    # Setup logging - only to file, not to console (to avoid UI interference)
    from config.dev_config import DEBUG_LOG_FILE

    # Remove any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # Add file handler only
    file_handler = logging.FileHandler(DEBUG_LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
    
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
