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
import logging

from rich.markup import escape
from typing import Optional, Dict, Any

# Import game components
from src.game_world import GameWorld
from src.item_placer import ItemPlacer
from src.player import Player
from src.command_handler import CommandHandler
from src.game_output import GameOutput
from src.save import save_manager
from src.ui.ui_interface import UIProtocol, UIInitializationError
from src.events import EventBus, EventType
from src.game_states import GameState, DEFAULT_GAME_STATE, DEFAULT_ROOM
from src.data_loader import load_room_data, load_enemy_data, load_npc_data
from src.state_manager import StateManager
from src.viewmodels.view_builder import ViewBuilder

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
    
    def __init__(self, ui: Optional[UIProtocol] = None, bus: Optional[EventBus] = None):
        """Initialize the game engine.

        The engine owns its EventBus and StateManager. Everything it builds
        (UI, world, command handler, combat) is handed this bus, so a
        subscription left behind dies with its engine instead of reacting to
        the next run's events.
        """
        logger.info("Initializing ImprovedGameEngine")
        self.bus = bus if bus is not None else EventBus()
        self.state_manager = StateManager(self.bus)

        # Non-reloadable state
        self.save_dir = "saves"
        # UI is injected by the composition root (main.py) / GameSession / tests.
        # The backend never constructs the concrete frontend.
        self.ui = ui
        if ui is not None:
            ui.attach_bus(self.bus, self.state_manager)
        # Domain output sink: command/combat text is written here and forwarded
        # live to the UI (Phase 2b). The domain no longer references the UI.
        self.output = GameOutput(forward=self._forward_output)

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

        # Drop the outgoing handler's subscriptions before letting go of it.
        # Without this, F5 (restart) left the dead run's CommandHandler on the
        # bus: ROOM_ENTERED then fired check_for_enemies twice (every enemy
        # fought twice) and ENEMY_DEFEATED fired twice (loot rolled twice).
        if getattr(self, "cmd_handler", None):
            self.cmd_handler.cleanup_event_subscriptions()

        # Reset game state
        self.player: Optional[Player] = None
        self.world: Optional[GameWorld] = None
        self.cmd_handler: Optional[CommandHandler] = None
        self.current_room = DEFAULT_ROOM
        self.state_manager.set_state(DEFAULT_GAME_STATE, emit_event=False)
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
        self.bus.subscribe(EventType.COMMAND_ENTERED, self._on_command_entered)
        self.bus.subscribe(EventType.UI_READY, self._on_ui_ready)
        self.bus.subscribe(EventType.UI_ERROR, self._on_ui_error)
        self.bus.subscribe(EventType.GAME_SAVED, self._on_save_requested)
        self.bus.subscribe(EventType.COMBAT_STARTED, self._on_combat_started)
        self.bus.subscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
        self.bus.subscribe(EventType.GAME_OVER, self._on_game_over)
        self.bus.subscribe(EventType.GAME_RESTART_REQUESTED, self._on_restart_requested)

    def restart_game(self):
        """Restart game state without closing UI - reloads all game data."""
        logger.info("Restarting game")

        # Reinitialize all game components (player, world, data)
        self._initialize_game_components()

        # Emit event to UI to reset display
        self.bus.emit_event(EventType.GAME_OVER, {"message": "Game restarted. Welcome back!"}, "GameEngine")

        logger.info("Game restart complete")

    def _load_content(self):
        """Load every content collection from data/ (rooms, items, enemies, npcs)."""
        return (
            load_room_data(),
            self._load_items(),
            load_enemy_data(),
            load_npc_data(),
        )

    def _load_game_data(self):
        """Load all game data and build a freshly-initialized world."""
        logger.info("Loading game data")
        rooms, items, enemies, npcs = self._load_content()
        self.world = GameWorld(rooms, items, enemies, npcs, bus=self.bus)
        logger.info(
            f"Loaded {len(rooms)} rooms, {len(items)} items, "
            f"{len(enemies)} enemies, {len(npcs)} NPCs"
        )

    def _load_game_data_for_load(self):
        """Load game data for a save game — world state comes from the save."""
        logger.info("Loading game data for save game")
        rooms, items, enemies, npcs = self._load_content()
        self.world = GameWorld(rooms, items, enemies, npcs, initialize_state=False, bus=self.bus)
        logger.info("Game data loaded successfully for save game")

    def _load_items(self) -> Dict[str, Any]:
        """Load all items as typed engine Item models (id -> model), validated at load.

        The engine loader enforces flat files, required ``type``, unique ids, and now
        field shapes (weapon ``damage``, consumable ``combat_effects``, …). GameWorld
        stores the typed templates; ``get_item`` dumps them back to dicts for consumers.
        """
        from engine.content.loader import load_items
        items: Dict[str, Any] = {str(iid): it for iid, it in load_items("data").items()}
        logger.info(f"Total items loaded: {len(items)}")
        return items


    # Event handlers
    def _on_command_entered(self, event):
        """Handle command entered from UI."""
        command = event.data.get('command', '')
        game_state = event.data.get('game_state', self.state_manager.current_state)

        # New command: its first output write replaces the panel (see _forward_output).
        self._fresh_command_output = True

        logger.debug(f"Command entered: '{command}' (UI state: {game_state}, Engine state: {self.state_manager.current_state})")
        
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
            elif game_state == GameState.WAITING_FOR_DIFFICULTY:
                self._handle_difficulty_input(command)
            elif game_state == GameState.WAITING_FOR_CLASS:
                self._handle_class_input(command)
            elif game_state == GameState.TUTORIAL_NAME_INPUT:
                self._handle_tutorial_name_input(command)
            elif game_state == GameState.GAME_OVER:
                # Any keypress from game over screen → return to main menu
                logger.debug("GAME_OVER state: transitioning to MENU")
                self.state_manager.set_state(GameState.MENU)
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

    def _forward_output(self, content):
        """Render one line from the domain output sink to the UI (Phase 2b).

        The FIRST write of a command replaces the output panel; subsequent
        writes from the SAME command append. Without this, multi-line commands
        (item use message + consumed, take + file list) overwrite themselves
        and only the last line is ever visible.

        Thread-safe: the game-over animation writes from a background thread, so
        use Textual's call_from_thread when the UI provides it.
        """
        first = getattr(self, "_fresh_command_output", True)
        self._fresh_command_output = False
        sink = self.ui.update_output
        if not first and hasattr(self.ui, "append_output"):
            sink = self.ui.append_output

        if hasattr(self.ui, 'call_from_thread'):
            try:
                self.ui.call_from_thread(sink, content)
                return
            except Exception:
                pass
        sink(content)

    def _on_ui_ready(self, event):
        """Handle UI ready event."""
        logger.info("UI is ready, starting main menu")
        self.state_manager.set_state(GameState.MENU)
    
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
        self.state_manager.enter_combat()
    
    def _on_combat_ended(self, event):
        """Handle combat ended event."""
        logger.info("Combat ended, exiting combat state")

        # Check if player was defeated - trigger game over immediately
        if event.data.get('defeat', False):
            logger.info("Player defeated in combat - triggering game over")
            self.state_manager.set_state(GameState.GAME_OVER)
            self.bus.emit_event(
                EventType.GAME_OVER,
                {"message": "[bold red]GAME OVER[/bold red]\n\nYou have been defeated in combat.\n\nPress any key to continue..."},
                "GameEngine"
            )
            return  # Don't continue with normal combat end processing

        # Use StateManager to exit combat
        self.state_manager.exit_combat()

        # On flee, CommandHandler relocates player + emits ROOM_ENTERED itself.
        # Emitting here would fire check_for_enemies on the room they just fled,
        # restarting combat before the flee handler can mark the enemy fled.
        if event.data.get("fled", False):
            self._update_ui_panels()
            return

        # ROOM_ENTERED goes out BEFORE the panel refresh. The UI leaves combat
        # mode on this same event, and it needs the fresh room view to be in
        # hand by then — when the order was reversed it was not, which is why
        # the UI used to defer its panel restore behind a 0.1s timer.
        if self.world and self.player:
            room_view = ViewBuilder.build_room_view(self.world, self.player.current_room)

            self.bus.emit_event(
                EventType.ROOM_ENTERED,
                {
                    "room": room_view.to_dict(),
                    "player_name": self.player.name
                },
                "ImprovedGameEngine"
            )

        self._update_ui_panels()
    
    def _on_game_over(self, event):
        """Handle game over event and restart game based on player choice."""
        action = event.data.get("action")
        logger.info(f"Game over event received with action: {action}")
        
        if action == "quit":
            logger.info("Player chose to quit")
            self._cleanup()
            self.bus.emit_event(EventType.GAME_QUIT, {}, "ImprovedGameEngine")
            
        elif action == "start_new_game":
            # Full setup flow: a new run re-offers difficulty + class (the old
            # shortcut restarted as a default guardian on the same difficulty).
            logger.info("Player chose to start new game - full setup flow")
            self.state_manager.set_state(GameState.MENU, emit_event=False)
            self.bus.clear_history()
            self._start_new_game()
            
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
            self.state_manager.set_state(GameState.MENU, emit_event=False)

            # Clear event history
            self.bus.clear_history()

            # Unsubscribe stale handlers before replacing them
            if self.cmd_handler:
                self.cmd_handler.cleanup_event_subscriptions()

            # Create new player (this will trigger character creation)
            from src.player import Player
            self.player = Player()

            # Reset world state by reloading all game data
            self._load_game_data()

            # Create new command handler with fresh references
            self.cmd_handler = CommandHandler(self.player, self.world, self.output, self.bus)
            self._bind_ui_refs()

            # Restart the game loop
            self.state_manager.set_state(GameState.PLAYING)

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
                self.state_manager.set_state(GameState.MENU, emit_event=False)
                self._start_new_game()
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

            # Create new command handler — unsubscribe the old one first, or the
            # dead run's handler keeps reacting to ROOM_ENTERED/ENEMY_DEFEATED with
            # its stale player (observed: fresh game instantly fighting the boss
            # from the previous run's room).
            if self.cmd_handler:
                self.cmd_handler.cleanup_event_subscriptions()
            self.cmd_handler = CommandHandler(self.player, self.world, self.output, self.bus)
            self._bind_ui_refs()

            # Update UI
            self._update_ui_panels()

            logger.info("Save game restart completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to restart from save: {e}")
            self.ui.display_message(f"[bold red]Failed to load save: {e}. Starting new game instead...[/bold red]")
            self.state_manager.set_state(GameState.MENU, emit_event=False)
            self._start_new_game()
    
    def _handle_menu_command(self, command: str):
        """Handle commands in menu state."""
        logger.debug(f"Handling menu command: '{command}'")
        
        if command == "1":
            # New Game
            self._start_new_game()
        elif command == "2":
            # Load Game
            self._load_game()
        elif command == "3" or command.lower() in ("exit", "quit"):
            # Exit. `quit` is accepted here too: the title screen tells players
            # "esc to quit", and ESC emits exactly that command.
            self.ui.update_output("Goodbye!")
            self.bus.emit_event(EventType.GAME_QUIT, {}, "ImprovedGameEngine")
        else:
            self.ui.update_output(f"[bold red]Invalid choice: {command}. Please enter 1, 2, or 3.[/bold red]\n")
            # Re-show the title screen to help the player. No sleep here: this
            # runs on the UI thread, so a pause freezes the whole app.
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

        # Pick difficulty first (locked for the run), then class selection.
        self._show_difficulty_selection()
        
    def _load_game(self):
        """Load an existing game."""
        try:
            logger.debug("Starting load game process")
            # List available save files
            save_files = save_manager.get_save_files()
            logger.debug(f"Found {len(save_files)} save files")
            if not save_files:
                self.ui.update_output("[bold yellow]No save files found. Starting new game instead...[/bold yellow]\n")
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
            
            # Create command handler — unsubscribe the old one first (see
            # _restart_from_save: stale handlers double every event).
            if self.cmd_handler:
                self.cmd_handler.cleanup_event_subscriptions()
            self.cmd_handler = CommandHandler(self.player, self.world, self.output, self.bus)
            self._bind_ui_refs()

            self.ui.update_output(f"Game loaded successfully! Welcome back, {self.player.name}!")

            # Start the game loop
            self.state_manager.set_state(GameState.PLAYING)
            logger.debug(f"Game state set to {self.state_manager.current_state}")

            # Emit game started event to update UI
            stats_view = ViewBuilder.build_stats_view(self.player)
            inventory_view = ViewBuilder.build_inventory_view(self.player)

            self.bus.emit_event(
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

            self.bus.emit_event(
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
    
    @staticmethod
    def _reserved_name(name: str) -> bool:
        """A command word typed at the name prompt is a player who thinks they
        are already playing, not a name."""
        from src.commands import build_registry
        word = name.strip().lower()
        return word in build_registry() or word in {"yes", "no", "skip", "exit", "menu"}

    def _handle_name_input(self, name: str):
        """Handle player name input."""
        if not name.strip():
            self.ui.update_output("Name cannot be empty. Please enter your character name:")
            return
        if self._reserved_name(name):
            self.ui.update_output(
                f"[bold yellow]'{escape(name.strip())}' is a command, not a name.[/bold yellow] "
                "Please enter your character name:"
            )
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
        "guardian": "🛡",
        "weaver":   "✨",
        "shaman":   "🌿",
    }

    _DIFFICULTY_INFO = {
        "easy":   ("🌱", "green", "Gentler enemies, faster leveling. For learning the ropes."),
        "medium": ("⚖",  "cyan",  "The intended, balanced challenge."),
        "hard":   ("🔥", "red",   "Tougher enemies and longer fights; you level slower."),
    }

    def _show_difficulty_selection(self):
        """Difficulty picker — Rich panels, mirrors class selection."""
        try:
            from src import difficulty
            from rich.panel import Panel
            from rich.console import Group
            from rich.text import Text
            from rich.align import Align
            from rich.rule import Rule

            renderables = [
                Text(""),
                Align.center(Text("⚙  CHOOSE YOUR DIFFICULTY  ⚙", style="bold cyan")),
                Rule(style="cyan"),
                Text(""),
            ]
            for i, mode in enumerate(difficulty.MODES, 1):
                icon, color, desc = self._DIFFICULTY_INFO.get(mode, ("•", "white", ""))
                body = Text(desc, style="italic")
                renderables.append(Panel(
                    body,
                    title=f"[bold {color}][{i}]  {icon}  {mode.upper()}[/bold {color}]",
                    title_align="left",
                    border_style=color,
                    padding=(1, 2),
                    expand=True,
                ))
                renderables.append(Text(""))
            renderables.append(
                Text(f"Enter your choice (1–{len(difficulty.MODES)}):", style="bold white")
            )

            group = Group(*renderables)
            if hasattr(self.ui, "update_output_renderable"):
                self.ui.update_output_renderable(group)
            else:
                from rich.console import Console
                con = Console(record=True, width=100)
                con.print(group)
                self.ui.update_output(con.export_text(styles=True))

            self.state_manager.set_state(GameState.WAITING_FOR_DIFFICULTY)
        except Exception as e:
            logger.error(f"Error showing difficulty selection: {e}")
            self.ui.update_output(f"Error showing difficulty selection: {e}")
            self.state_manager.set_state(GameState.MENU)

    def _handle_difficulty_input(self, choice: str):
        """Set the run's difficulty from the picker, then go to class selection."""
        from src import difficulty
        mode_map = {str(i): m for i, m in enumerate(difficulty.MODES, 1)}
        mode = mode_map.get(str(choice).strip())
        if not mode:
            valid = ", ".join(mode_map.keys())
            self.ui.update_output(f"[bold red]Invalid choice. Please enter {valid}.[/bold red]\n")
            self._show_difficulty_selection()
            return
        difficulty.set_mode(mode)
        self.ui.update_output(f"[bold green]Difficulty set to {mode.upper()}.[/bold green]\n")
        self._show_class_selection()

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
                d = cls.display
                color = d.color
                hp_color = d.hp_color
                dmg_color = d.dmg_color
                icon = self._CLASS_ICONS.get(class_id, "•")
                name = cls.name.upper()
                tagline = cls.description.split(" - ", 1)
                tagline_main = tagline[0] if tagline else ""
                tagline_sub = tagline[1] if len(tagline) > 1 else ""
                hp = d.hp_label
                dmg = d.dmg_label
                weapon = d.weapon_name
                pref = ", ".join(cls.preferred_zones or [])

                body = Text()
                body.append(tagline_main + "\n", style="italic")
                if tagline_sub:
                    body.append(tagline_sub + "\n", style="dim")
                body.append("\n")
                body.append("❤  ", style="red")
                body.append(hp + "\n", style=hp_color)
                body.append("⚔  ", style="yellow")
                body.append(dmg + "\n", style=dmg_color)
                body.append("🗡  ", style="white")
                body.append("Weapon: ", style="dim")
                body.append(weapon + "\n")
                if pref:
                    body.append("🗺  ", style="white")
                    body.append("Zones: ", style="dim")
                    body.append(pref)

                panel = Panel(
                    body,
                    title=f"[bold {color}][{i}]  {icon}  {name}[/bold {color}]",
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

            self.state_manager.set_state(GameState.WAITING_FOR_CLASS)

        except Exception as e:
            logger.error(f"Error showing class selection: {e}")
            self.ui.update_output(f"Error showing class selection: {e}")
            self.state_manager.set_state(GameState.MENU)
    
    def _show_tutorial_introduction(self):
        """Show the tutorial introduction with ECHO asking for the player's name."""
        try:
            from src.data_loader import load_class_data
            classes = load_class_data()
            cls = classes.get(self.selected_class)
            selected_class_name = cls.name if cls else self.selected_class.title()
            selected_class_desc = (
                cls.display.echo_description if cls else "a mysterious entity"
            )
            
            tutorial_intro = f"""[bold cyan]>>> ECHO SYSTEM INITIALIZING <<<[/bold cyan]

[dim italic]A faint digital whisper echoes through the corrupted filesystem…[/dim italic]

[bold green]🗨  ECHO[/bold green]

[italic]Spirit… I sense your presence in the digital void.
You have chosen to manifest as a [bold]{selected_class_name}[/bold] — {selected_class_desc}.

The corruption spreads deeper each nanosecond. The Daemon Overlord's influence grows stronger.

But first, I must know what to call you. The old sysadmin records are fragmented, and I need a name to anchor your essence to this haunted filesystem.[/italic]

[bold yellow]What is your name, spirit?[/bold yellow]
[dim]Type it below and press Enter[/dim]"""

            self.ui.update_output(tutorial_intro)
            self.state_manager.set_state(GameState.TUTORIAL_NAME_INPUT)

        except Exception as e:
            logger.error(f"Error showing tutorial introduction: {e}")
            self.ui.update_output(f"Error showing tutorial introduction: {e}")
            self.state_manager.set_state(GameState.MENU)
    
    def _handle_tutorial_name_input(self, name: str):
        """Handle name input during tutorial — includes skip offer flow."""
        # If awaiting skip response, handle it
        if self._awaiting_skip_response:
            self._handle_skip_response(name.strip().lower())
            return

        # Validate name
        if not name.strip() or self._reserved_name(name):
            heard = (
                f"[bold]{escape(name.strip())}[/bold] is a command — you'll use those soon.\n"
                "For now I only need your name."
                if name.strip() else "I didn't catch that."
            )
            self.ui.update_output(
                "[bold green]🗨  ECHO[/bold green]\n\n"
                f"{heard}\n\n"
                "[bold yellow]What is your name, spirit?[/bold yellow]\n"
                "[dim]Type it below and press Enter[/dim]"
            )
            return

        player_name = name.strip()
        self._pending_player_name = player_name

        # Create player (tutorial_state is initialized on the player object)
        if not self.create_player(player_name, self.selected_class):
            self.ui.update_output("Error creating player. Returning to main menu.")
            self.state_manager.set_state(GameState.MENU)
            return

        self.initialize_special_items(self.selected_class)

        # Show skip offer
        self._awaiting_skip_response = True
        self.player.tutorial_state["skip_offered"] = True
        self.ui.update_output(
            f"[bold green]🗨  ECHO[/bold green]\n\n"
            f"Welcome, [bold]{player_name}[/bold].\n"
            f"Want a quick tutorial? It covers all the commands you'll need.\n\n"
            f"[bold green]yes[/bold green] [dim]— show me around[/dim]"
            f"        "
            f"[bold yellow]skip[/bold yellow] [dim]— I know my way[/dim]"
        )

    def _handle_skip_response(self, response: str):
        """Handle yes/no response to the tutorial skip offer."""
        self._awaiting_skip_response = False
        negative_words = {"no", "skip", "n", "nope", "nah", "pass"}
        skipping = (response in negative_words or
                    response.startswith("skip") or
                    response.startswith("no"))

        if skipping:
            # The summary text lives in data/tutorial_hints.yaml as
            # "skip_summary". It used to be inlined here as a second copy, and
            # the two drifted: this one still told players to press TAB to
            # *enter* Selection Mode, which combat has entered automatically
            # since the auto-entry change (TAB now leaves it).
            #
            # After start_game, whose GAME_STARTED resets the UI and would wipe
            # it; before the tutorial is marked complete, because
            # tutorial.show_hint returns early once it is.
            self.start_game()
            self.cmd_handler.tutorial.show_hint("skip_summary")
            self.player.tutorial_state["completed"] = True
        else:
            # Tutorial path: start the game, then Step 1 (after the UI reset).
            self.start_game()
            self.cmd_handler.tutorial.show_hint("step1")
    
    def initialize_special_items(self, player_class: str):
        """Create and place special enhancement items based on player class."""
        if self.world:
            ItemPlacer(self.world).place_items(player_class)
            logger.info(f"Special items initialized for class: {player_class}")
    
    def _update_ui_panels(self):
        """Update all UI panels by emitting view-model events."""
        if self.ui and self.player and self.world:
            try:
                stats_view = ViewBuilder.build_stats_view(self.player)
                inventory_view = ViewBuilder.build_inventory_view(self.player)
                self.bus.emit_event(EventType.PLAYER_STATS_CHANGED, stats_view.to_dict(), "ImprovedGameEngine")
                self.bus.emit_event(EventType.PLAYER_INVENTORY_CHANGED, inventory_view.to_dict(), "ImprovedGameEngine")
            except Exception as e:
                logger.error(f"Error updating UI panels: {e}")
    
    def create_player(self, name: str, player_class: str) -> bool:
        """Create a new player."""
        try:
            # Idempotent: never leave a prior handler subscribed, or ROOM_ENTERED /
            # ENEMY_DEFEATED fire on both and everything doubles (fight enemies twice).
            if self.cmd_handler:
                self.cmd_handler.cleanup_event_subscriptions()
            self.player = Player(name=name, player_class=player_class)
            self.cmd_handler = CommandHandler(self.player, self.world, self.output, self.bus)
            self._bind_ui_refs()

            # Set up event subscriptions for command handler
            self.cmd_handler.setup_event_subscriptions()

            # Place class-appropriate starter items in home_grove
            if self.world:
                ItemPlacer(self.world).place_starter_items(player_class)
                logger.info(f"Placed starter items for {player_class} in home_grove")

            # Build view for player creation event
            stats_view = ViewBuilder.build_stats_view(self.player)

            self.bus.emit_event(
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
            # Whatever led here (name prompt, tutorial offer) is answered: the
            # game starts on the room itself, not under a stale prompt.
            self.ui.clear_console()
            self.state_manager.set_state(GameState.PLAYING)

            # Build views for game start
            stats_view = ViewBuilder.build_stats_view(self.player)
            inventory_view = ViewBuilder.build_inventory_view(self.player)

            self.bus.emit_event(
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

            if self.cmd_handler:
                self.cmd_handler.display_location()

            # Emit room entered event for starting room
            if self.player and hasattr(self.player, 'current_room'):
                room_view = ViewBuilder.build_room_view(self.world, self.player.current_room)

                self.bus.emit_event(
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
            self.state_manager.set_state(GameState.GAME_OVER)

            self.bus.emit_event(
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
            self.bus.unsubscribe(EventType.COMMAND_ENTERED, self._on_command_entered)
            self.bus.unsubscribe(EventType.UI_READY, self._on_ui_ready)
            self.bus.unsubscribe(EventType.UI_ERROR, self._on_ui_error)
            self.bus.unsubscribe(EventType.GAME_SAVED, self._on_save_requested)
            self.bus.unsubscribe(EventType.COMBAT_STARTED, self._on_combat_started)
            self.bus.unsubscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
            self.bus.unsubscribe(EventType.GAME_OVER, self._on_game_over)
            
            logger.info("Game engine cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main(ui):
    """Entry point: the caller (composition root) supplies the concrete UI."""
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

    # Ctrl+C is handled inside the app: Textual binds it (and Ctrl+Q) to the
    # game's own quit confirmation, so the interrupt never reaches this frame.
    # The old KeyboardInterrupt branch here offered a save via input() — which
    # would have fought the TUI for stdin and printed raw Rich markup — and was
    # unreachable in practice.
    try:
        engine = ImprovedGameEngine(ui=ui)
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
