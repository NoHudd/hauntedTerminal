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
from typing import Optional, Any

# Import game components
from src.game_world import GameWorld
from src.item_placer import ItemPlacer
from src.player import Player
from src.command_handler import CommandHandler
from src.game_output import GameOutput
from src.save import IncompatibleSaveError, save_manager
from src.ui.ui_interface import UIProtocol, UIInitializationError
from engine.events import EventBus, EventType
from src.game_states import GameState, DEFAULT_GAME_STATE, DEFAULT_ROOM
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
        # Which save picker is up: "continue" (LOAD GAME) or "replace" (NEW
        # GAME with every slot taken).
        self._save_picker_mode = "continue"
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

    def _initialize_game_components(self):
        """Initialize/reinitialize game components (reloadable)."""
        logger.info("Initializing game components")

        # Drop the outgoing handler's subscriptions before letting go of it.
        # Without this, F5 (restart) left the dead run's CommandHandler on the
        # bus: ENEMY_DEFEATED fired twice (loot rolled twice).
        if getattr(self, "cmd_handler", None):
            self.cmd_handler.cleanup_event_subscriptions()

        # Reset game state
        self.player: Optional[Player] = None
        self.world: Optional[GameWorld] = None
        self.cmd_handler: Optional[CommandHandler] = None
        self.current_room = DEFAULT_ROOM
        self.state_manager.set_state(DEFAULT_GAME_STATE, emit_event=False)
        self._awaiting_skip_response: bool = False

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
        self.bus.subscribe(EventType.GAME_RESTART_REQUESTED, self._on_restart_requested)

    def restart_game(self):
        """Restart game state without closing UI - reloads all game data."""
        logger.info("Restarting game")

        # Reinitialize all game components (player, world, data)
        self._initialize_game_components()

        # Emit event to UI to reset display
        self.bus.emit_event(
            EventType.GAME_OVER,
            {"reason": "restart", "message": "Game restarted. Welcome back!"},
            "GameEngine",
        )

        logger.info("Game restart complete")

    #: Where the world's content lives; tests point this at a scratch copy.
    DATA_DIR = "data"

    def _load_content(self):
        """Load and link the world's content (rooms, items, enemies, NPCs).

        link() runs the same integrity checks as `python -m engine.validate`:
        a dangling reference or a broken room tree stops the game at start
        (DataLoadError) instead of surfacing mid-run. The old per-collection
        loaders swallowed errors and returned an empty collection.
        """
        from engine.content import link, load_all

        content = link(load_all(self.DATA_DIR))
        return tuple(
            {str(key): model for key, model in collection.items()}
            for collection in (content.rooms, content.items, content.enemies, content.npcs)
        )

    def _load_game_data(self):
        """Load all game data and build a freshly-initialized world."""
        logger.info("Loading game data")
        rooms, items, enemies, npcs = self._load_content()
        self.world = GameWorld(rooms, items, enemies, npcs)
        logger.info(
            f"Loaded {len(rooms)} rooms, {len(items)} items, "
            f"{len(enemies)} enemies, {len(npcs)} NPCs"
        )

    def _load_game_data_for_load(self):
        """Load game data for a save game — world state comes from the save."""
        logger.info("Loading game data for save game")
        rooms, items, enemies, npcs = self._load_content()
        self.world = GameWorld(rooms, items, enemies, npcs, initialize_state=False)
        logger.info("Game data loaded successfully for save game")

    # Event handlers
    def _on_command_entered(self, event):
        """Handle command entered from UI."""
        command = event.data.get('command', '')
        # The engine decides what mode the game is in; the UI only sends text.
        game_state = self.state_manager.current_state

        # New command: its first output write replaces the panel (see _forward_output).
        self._fresh_command_output = True

        logger.debug(f"Command entered: '{command}' (state: {game_state})")
        
        try:
            if game_state == GameState.PLAYING and self.cmd_handler:
                self.cmd_handler.handle_command(command)
                self._update_ui_panels()
            elif game_state == GameState.IN_COMBAT and self.cmd_handler:
                self.cmd_handler.handle_command(command)
            elif game_state == GameState.MENU:
                self._handle_menu_command(command)
            elif game_state == GameState.WAITING_FOR_SAVE:
                self._handle_save_picker_input(command)
            elif game_state == GameState.WAITING_FOR_DIFFICULTY:
                self._handle_difficulty_input(command)
            elif game_state == GameState.WAITING_FOR_CLASS:
                self._handle_class_input(command)
            elif game_state == GameState.TUTORIAL_NAME_INPUT:
                self._handle_tutorial_name_input(command)
            elif game_state == GameState.GAME_OVER and self.cmd_handler:
                # The game-over screen's r / n / q; anything else re-asks.
                self.cmd_handler.flow.handle_game_over_input(command)
            else:
                logger.debug(f"No specific handler for state {game_state}, defaulting to menu handler")
                self._handle_menu_command(command)
        except Exception as e:
            logger.error(f"Error handling command '{command}': {e}")
            self.ui.update_output(f"Error: {e}")

    def _forward_output(self, content, replace=False):
        """Render one line from the domain output sink to the UI (Phase 2b).

        The FIRST write of a command replaces the output panel; subsequent
        writes from the SAME command append. Without this, multi-line commands
        (item use message + consumed, take + file list) overwrite themselves
        and only the last line is ever visible.

        Thread-safe: the game-over animation writes from a background thread, so
        use Textual's call_from_thread when the UI provides it.
        """
        first = getattr(self, "_fresh_command_output", True) or replace
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
    
    def _new_command_handler(self):
        """A CommandHandler for the current player and world, with the engine's
        combat hooks attached. Every run (new, loaded, restarted) gets one."""
        return CommandHandler(
            self.player, self.world, self.output, self.bus,
            on_combat_start=self._combat_started,
            on_combat_end=self._combat_ended,
            on_new_game=self._new_game_after_game_over,
            on_restore_save=self._restart_from_save,
        )

    def _combat_started(self):
        """Called by the combat session as a fight opens."""
        logger.info("Combat started, entering combat state")
        self.state_manager.enter_combat()
    
    def _combat_ended(self, outcome):
        """Called by CommandHandler.end_combat before it relocates the player,
        starts the game-over flow or checks for victory."""
        logger.info("Combat ended, exiting combat state")

        # Check if player was defeated - trigger game over immediately
        if outcome.get('defeat', False):
            logger.info("Player defeated in combat - triggering game over")
            self.state_manager.set_state(GameState.GAME_OVER)
            self.bus.emit_event(
                EventType.GAME_OVER,
                {
                    "reason": "defeat",
                    "message": "[bold red]GAME OVER[/bold red]\n\nYou have been defeated in combat.\n\nPress any key to continue...",
                },
                "GameEngine"
            )
            return  # Don't continue with normal combat end processing

        # Use StateManager to exit combat
        self.state_manager.exit_combat()

        # On flee, CommandHandler relocates the player and announces the room
        # they land in; this room is no longer theirs to show.
        if outcome.get("fled", False):
            self._update_ui_panels()
            return

        # The room goes out BEFORE the panel refresh. The UI leaves combat
        # mode on this same event, and it needs the fresh room view to be in
        # hand by then — when the order was reversed it was not, which is why
        # the UI used to defer its panel restore behind a 0.1s timer.
        if self.cmd_handler:
            self.cmd_handler.announce_room()

        self._update_ui_panels()
    
    def _new_game_after_game_over(self):
        """The game-over / post-win screen's "n": a new run re-offers difficulty
        and class (the old shortcut restarted as a default guardian on the same
        difficulty)."""
        logger.info("Player chose to start new game - full setup flow")
        self.state_manager.set_state(GameState.MENU, emit_event=False)
        self.bus.clear_history()
        self._start_new_game()

    def _on_restart_requested(self, event):
        """Handle game restart request from UI (F5 key)."""
        logger.info("Game restart requested from UI")
        self.restart_game()

    def _restart_from_save(self):
        """Game-over / post-win "r": reload the run being played from its last save."""
        try:
            logger.info("Restoring this run from its last save")
            # Game over only leads to the menu; a run restarts from there.
            if self.state_manager.current_state == GameState.GAME_OVER:
                self.state_manager.set_state(GameState.MENU, emit_event=False)

            run_id = save_manager.active_run_id
            save_data = save_manager.load_run(run_id) if run_id else None

            if not save_data:
                logger.warning("No save data found, starting new game instead")
                self.state_manager.set_state(GameState.MENU, emit_event=False)
                self._start_new_game()
                return

            self._enter_loaded_run(save_data)
            logger.info("Save game restart completed successfully")

        except Exception as e:
            logger.error(f"Failed to restart from save: {e}")
            self.ui.display_message(f"[bold red]Failed to load save: {e}. Starting new game instead...[/bold red]")
            self.state_manager.set_state(GameState.MENU, emit_event=False)
            self._start_new_game()

    def _enter_loaded_run(self, save_data, welcome=False):
        """Rebuild the run from a save and start playing it.

        Both load paths (title-menu Load Game, post-win restore) go through
        here, so neither can skip a step: the post-win restore used to leave
        the new command handler unsubscribed, so rooms never started fights.
        """
        from src import difficulty

        self.player = Player.from_dict(save_data.get("player", {}))
        difficulty.set_mode(save_data.get("difficulty", difficulty.DEFAULT_MODE))

        # Fresh content, then the saved world state on top of it.
        self._load_game_data_for_load()
        self.world.set_state(save_data.get("world", {}))
        # Saves from before the keys chain hold keys whose doors were never
        # revealed; reveal them so the player can see where to go.
        for key_id, item in self.player.inventory.items():
            if str(getattr(item, "type", "")).lower() == "key":
                self.world.reveal_doors(key_id)
        # They may also have a flag's key still lying on a floor (chmod_key in
        # /var). The flag hands it out now, so that copy would be a duplicate.
        for key_id in self.world.flag_granted_keys():
            self.world.item_locations.pop(key_id, None)

        # Unsubscribe the old handler first, or the dead run's handler keeps
        # reacting to ENEMY_DEFEATED with its stale player.
        if self.cmd_handler:
            self.cmd_handler.cleanup_event_subscriptions()
        self.cmd_handler = self._new_command_handler()
        self._bind_ui_refs()

        if welcome:
            # Before ROOM_ENTERED, which may open a fight and take the output.
            self.ui.update_output(f"Game loaded successfully! Welcome back, {self.player.name}!")

        self.state_manager.set_state(GameState.PLAYING)
        self.bus.emit_event(
            EventType.GAME_STARTED,
            {
                "stats": ViewBuilder.build_stats_view(self.player).to_dict(),
                "inventory": ViewBuilder.build_inventory_view(self.player).to_dict(),
            },
            "ImprovedGameEngine",
        )
        self._update_ui_panels()

        self.cmd_handler.setup_event_subscriptions()
        self.cmd_handler.arrive()

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
        """NEW GAME. With every slot taken the player first picks a run to
        replace; otherwise straight to setup."""
        if save_manager.runs_full():
            self._save_picker_mode = "replace"
            self._show_save_picker()
            return
        save_manager.begin_run()
        self._begin_setup()

    def _begin_setup(self):
        """A fresh world, then difficulty -> class -> name."""
        # Clean up stale event subscriptions from previous session
        if self.cmd_handler:
            self.cmd_handler.cleanup_event_subscriptions()
            self.cmd_handler = None

        # Reload world data so the new game starts with a fresh world state
        self._load_game_data()

        # Pick difficulty first (locked for the run), then class selection.
        self._show_difficulty_selection()

    def _load_game(self):
        """LOAD GAME: every run in the save picker, even when there are none."""
        self._save_picker_mode = "continue"
        self._show_save_picker()

    # -- save picker ---------------------------------------------------------

    def _run_rows(self, runs) -> list[dict]:
        """What the picker shows for each run (camelCase, UI-ready)."""
        from src import room_paths
        id_to_path, _ = room_paths.build_nav_tables(self.world.rooms)
        return [
            {
                "runId": run.run_id,
                "playerName": run.player_name,
                "playerClass": run.player_class,
                "difficulty": run.difficulty,
                "level": run.level,
                "roomPath": id_to_path.get(run.room_id, run.room_id),
                "health": run.health,
                "maxHealth": run.max_health,
                "savedAt": run.saved_at,
                "cleared": run.cleared,
            }
            for run in runs
        ]

    def _show_save_picker(self, notice: str = ""):
        """Enter the save picker: a typed list (headless, and behind the TUI's
        modal) plus an event the TUI turns into the picker screen."""
        rows = self._run_rows(save_manager.list_runs())
        legacy = save_manager.legacy_count()
        self.state_manager.set_state(GameState.WAITING_FOR_SAVE)
        text = self._save_picker_text(self._save_picker_mode, rows, legacy)
        self.ui.update_output(f"{notice}\n{text}" if notice else text)
        self.bus.emit_event(
            EventType.SAVE_PICKER_REQUESTED,
            {"mode": self._save_picker_mode, "runs": rows, "legacyCount": legacy},
            "ImprovedGameEngine",
        )

    @staticmethod
    def _save_picker_text(mode: str, rows: list[dict], legacy: int) -> str:
        heading = (
            "CONTINUE A RUN" if mode == "continue"
            else "SLOTS FULL — PICK A RUN TO REPLACE"
        )
        lines = [f"[bold cyan]{heading}[/bold cyan]", ""]
        if not rows:
            lines.append("No saves available")
            if legacy:
                noun = "save is" if legacy == 1 else "saves are"
                lines.append(
                    f"[dim]({legacy} old {noun} from an earlier version, "
                    "kept in saves/legacy/)[/dim]"
                )
        for row in rows:
            mark = " ✓ cleared" if row["cleared"] else ""
            lines.append(
                f"  {row['runId']}  {escape(row['playerName'])} · {row['playerClass']} · "
                f"{row['difficulty']} · {escape(row['roomPath'])} · L{row['level']}{mark}"
            )
        verbs = "[green]pick <id>[/green]"
        if mode == "continue" and rows:
            verbs += ", [yellow]delete <id>[/yellow]"
        lines += ["", f"Type {verbs} or [cyan]back[/cyan]."]
        return "\n".join(lines)

    def _handle_save_picker_input(self, command: str):
        verb, _, arg = command.strip().partition(" ")
        verb, arg = verb.lower(), arg.strip()
        known = {run.run_id for run in save_manager.list_runs()}

        if verb in ("back", "menu"):
            self.state_manager.set_state(GameState.MENU)
            self._show_title()
        elif verb == "pick" and arg in known:
            if self._save_picker_mode == "replace":
                save_manager.begin_run(replace=arg)
                self._begin_setup()
            else:
                self._continue_run(arg)
        elif verb == "delete" and arg in known and self._save_picker_mode == "continue":
            save_manager.delete_run(arg)
            self._show_save_picker()
        else:
            self._show_save_picker(
                notice=f"[bold red]Invalid choice: {escape(command.strip())}[/bold red]"
            )

    def _continue_run(self, run_id: str):
        try:
            save_data = save_manager.load_run(run_id)
        except IncompatibleSaveError as e:
            logger.warning(f"Refusing run {run_id}: {e}")
            save_data = None
        if not save_data:
            self._show_save_picker(notice="[bold red]That save could not be loaded.[/bold red]")
            return
        save_manager.resume_run(run_id)
        self._enter_loaded_run(save_data, welcome=True)

    def _show_title(self):
        """The title menu, without replaying the intro."""
        if hasattr(self.ui, "_display_title_screen"):
            self.ui._display_title_screen(skip_typewriter=True)

    @staticmethod
    def _reserved_name(name: str) -> bool:
        """A command word typed at the name prompt is a player who thinks they
        are already playing, not a name."""
        from src.commands import build_registry
        word = name.strip().lower()
        return word in build_registry() or word in {"yes", "no", "skip", "exit", "menu"}

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
            from src.move_info import class_move_lines, stat_lines
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
                hp, dmg = stat_lines(cls)
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
                body.append("✨  ", style="white")
                body.append("Moves:\n", style="dim")
                for line in class_move_lines(cls):
                    body.append("   " + line + "\n")
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

Every directory in this filesystem hides a [bold]flag[/bold] — a scrap of the system's lost memory. Capture them. Some flags hand you a [bold]key[/bold], and a directory you couldn't see before appears. Hold [bold]11[/bold] flags and [bold]/boot[/bold] opens, where the Overlord waits. That is how we end this.

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
        """Send the player's stats and inventory to the UI.

        Runs once after every command in play, so commands never send these
        views themselves (they used to, and the UI got each one twice).
        """
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
            # Idempotent: never leave a prior handler subscribed, or ENEMY_DEFEATED
            # fires on both and loot doubles.
            if self.cmd_handler:
                self.cmd_handler.cleanup_event_subscriptions()
            self.player = Player(name=name, player_class=player_class)
            self.cmd_handler = self._new_command_handler()
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
                self.cmd_handler.arrive()
            
        except Exception as e:
            logger.error(f"Error starting game: {e}")
            raise GameEngineError(f"Failed to start game: {e}")
    
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
