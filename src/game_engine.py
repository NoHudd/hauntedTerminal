#!/usr/bin/env python3
import os
import sys
import yaml
import json
import time
import random
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
import readchar

# Import game components
from src.game_world import GameWorld
from src.player import Player
from src.command_handler import CommandHandler
from src.save import save_manager
# Import debug tools
from utils.debug_tools import debug_log
from config.dev_config import DEBUG_MODE

console = Console()

class GameEngine:
    """Main game engine that loads YAML data and runs the game loop"""
    
    def __init__(self):
        """Initialize the game engine."""
        debug_log("Initializing GameEngine")
        self.player = None
        self.current_room = "terminal_room"
        self.game_state = "menu"  # menu, playing, game_over
        self.save_dir = "saves"
        # Ensure the save directory exists
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self.game_running = True
        self.console = Console()
        self.load_game_data()
        
    def load_game_data(self):
        """Load all game data from YAML files"""
        debug_log("Loading game data")
        try:
            # Load rooms
            rooms = {}
            try:
                for filename in os.listdir('data/rooms'):
                    if filename.endswith('.yaml') or filename.endswith('.yml'):
                        try:
                            with open(f'data/rooms/{filename}', 'r') as file:
                                room_data = yaml.safe_load(file)
                                if room_data is None:
                                    self.console.print(f"[yellow]Warning: Empty room file: {filename}, skipping.[/yellow]")
                                    debug_log(f"Empty room file: {filename}, skipping")
                                    continue
                                
                                # Get the enemy ID from filename (without extension)
                                room_id = os.path.splitext(filename)[0]
                                debug_log(f"Loaded room: {room_id}")
                                rooms[room_id] = room_data
                        except Exception as e:
                            self.console.print(f"[yellow]Warning: Error loading room file {filename}: {e}[/yellow]")
                            debug_log(f"Error loading room {filename}: {e}")
            except Exception as e:
                self.console.print(f"[bold red]Error accessing rooms directory: {e}[/bold red]")
                debug_log(f"Error accessing rooms directory: {e}")
            
            # Load items using the consolidated approach
            items = self.load_items()
            
            # Load enemies
            enemies = {}
            try:
                for filename in os.listdir('data/enemies'):
                    if filename.endswith('.yaml') or filename.endswith('.yml'):
                        try:
                            with open(f'data/enemies/{filename}', 'r') as file:
                                enemy_data = yaml.safe_load(file)
                                if enemy_data is None:
                                    self.console.print(f"[yellow]Warning: Empty enemy file: {filename}, skipping.[/yellow]")
                                    debug_log(f"Empty enemy file: {filename}")
                                    continue
                                
                                # Get the enemy ID from filename (without extension)
                                enemy_id = os.path.splitext(filename)[0]
                                debug_log(f"Loading enemy: {enemy_id}")
                                
                                # If it's a category file (e.g. tier1_enemies.yaml)
                                if isinstance(enemy_data, dict) and len(enemy_data) == 1 and next(iter(enemy_data.keys())).endswith('enemies'):
                                    category = next(iter(enemy_data.keys()))
                                    for enemy_id, enemy_info in enemy_data[category].items():
                                        enemy_info['id'] = enemy_id
                                        enemies[enemy_id] = enemy_info
                                        debug_log(f"Loaded enemy from category {category}: {enemy_id}")
                                else:
                                    # Direct dictionary - this is an individual enemy
                                    # Store both with and without extension for better matching
                                    enemy_data['id'] = enemy_id
                                    
                                    # Also store without file extension for better matching with room data
                                    base_id = enemy_id.split('.')[0]
                                    if '.' in enemy_id:
                                        # If filename has extension in it (like corrupt_process.bin.yml)
                                        # Store the ID both with and without the extension
                                        clean_id = base_id  # e.g. corrupt_process
                                        full_id = enemy_id  # e.g. corrupt_process.bin
                                        
                                        # Store with both IDs to make lookup more flexible
                                        enemies[clean_id] = enemy_data
                                        enemies[full_id] = enemy_data
                                        debug_log(f"Stored enemy with multiple IDs: {clean_id}, {full_id}")
                                        
                                        # If filename is like "name.ext.yml", also store as "name.ext"
                                        if '.' in enemy_id:
                                            enemies[enemy_id] = enemy_data
                                    else:
                                        # No extension in filename, just store as is
                                        enemies[enemy_id] = enemy_data
                                    
                                    self.console.print(f"[green]Loaded enemy: {enemy_id}[/green]")
                                    debug_log(f"Loaded enemy: {enemy_id}")
                        except Exception as e:
                            self.console.print(f"[yellow]Warning: Error loading enemy file {filename}: {e}[/yellow]")
                            debug_log(f"Error loading enemy file {filename}: {e}")
            except Exception as e:
                self.console.print(f"[yellow]Warning: Error accessing enemies directory: {e}[/yellow]")
                debug_log(f"Error accessing enemies directory: {e}")
            
            # Load NPCs with similar structure as above
            npcs = {}
            try:
                for filename in os.listdir('data/npcs'):
                    if filename.endswith('.yaml') or filename.endswith('.yml'):
                        try:
                            with open(f'data/npcs/{filename}', 'r') as file:
                                npc_data = yaml.safe_load(file)
                                if npc_data is None:
                                    self.console.print(f"[yellow]Warning: Empty NPC file: {filename}, skipping.[/yellow]")
                                    debug_log(f"Empty NPC file: {filename}")
                                    continue
                                # If it's a category file
                                if isinstance(npc_data, dict) and len(npc_data) == 1 and next(iter(npc_data.keys())).endswith('npcs'):
                                    category = next(iter(npc_data.keys()))
                                    for npc_id, npc_info in npc_data[category].items():
                                        npc_info['id'] = npc_id
                                        npcs[npc_id] = npc_info
                                        debug_log(f"Loaded NPC from category {category}: {npc_id}")
                                else:
                                    # Direct dictionary of NPCs
                                    npc_id = os.path.splitext(filename)[0]
                                    npc_data['id'] = npc_id
                                    npcs[npc_id] = npc_data
                                    debug_log(f"Loaded NPC: {npc_id}")
                        except Exception as e:
                            self.console.print(f"[yellow]Warning: Error loading NPC file {filename}: {e}[/yellow]")
                            debug_log(f"Error loading NPC file {filename}: {e}")
            except Exception as e:
                self.console.print(f"[yellow]Warning: Error accessing NPCs directory: {e}[/yellow]")
                debug_log(f"Error accessing NPCs directory: {e}")
            
            # Store loaded items for later use
            self.items = items
            
            # Print summary of loaded data
            self.console.print(f"[green]Loaded {len(rooms)} rooms, {len(items)} items, {len(enemies)} enemies, and {len(npcs)} NPCs.[/green]")
            debug_log(f"Data loading complete: {len(rooms)} rooms, {len(items)} items, {len(enemies)} enemies, {len(npcs)} NPCs")
            
            # Initialize world
            self.world = GameWorld(rooms, items, enemies, npcs)
            debug_log("GameWorld initialized")
            
            # Player will be created during class selection
            self.player = None
            
            # Command handler will be initialized after player creation
            self.cmd_handler = None
            
        except Exception as e:
            self.console.print(f"[bold red]Error loading game data: {e}[/bold red]")
            debug_log(f"Critical error in load_game_data: {e}")
            sys.exit(1)
    
    def load_items(self):
        """Load all items from categorized YAML files and merge them into a single dictionary.
        
        Returns:
            dict: A merged dictionary of all items with item IDs as keys.
        """
        item_files = [
            'consumables.yaml',
            'weapons.yaml',
            'upgrades.yaml',
            'enhancements.yaml',
            'keys.yaml',
            'scrolls.yaml',
            'lore_items.yaml',
            'quest_items.yaml',
            'scripts.yaml',
            'data_fragments.yaml'
        ]
        
        items = {}
        
        # Process each category file
        for filename in item_files:
            filepath = f'data/items/{filename}'
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r') as file:
                        data = yaml.safe_load(file)
                        if data is None:
                            self.console.print(f"[yellow]Warning: Empty item file: {filename}, skipping.[/yellow]")
                            continue
                        
                        # Get the category name from the filename (without extension)
                        category = os.path.splitext(filename)[0]
                        
                        # If the file uses a category structure (e.g., {"weapons": {...}})
                        if category in data:
                            category_items = data[category]
                            # Add each item to the global items dict with its ID as the key
                            for item_id, item_data in category_items.items():
                                # Store the original ID inside the item data for reference
                                item_data['id'] = item_id
                                # If the item doesn't have a type field, add the category as its type
                                if 'type' not in item_data:
                                    item_data['type'] = category[:-1]  # Remove trailing 's' from category
                                # Add to the global items dict
                                items[item_id] = item_data
                        else:
                            # For files that don't use a category structure, assume they're a direct dict of items
                            for item_id, item_data in data.items():
                                # Store the original ID
                                item_data['id'] = item_id
                                items[item_id] = item_data
                else:
                    self.console.print(f"[yellow]Warning: Item category file {filename} not found, skipping.[/yellow]")
            except Exception as e:
                self.console.print(f"[yellow]Warning: Error loading item category {filename}: {e}[/yellow]")
        
        self.console.print(f"[green]Loaded {len(items)} items from category files[/green]")
        return items
    
    def initialize_special_items(self, player_class):
        """Create and place special enhancement items based on player class"""
        # Only place items that are class-appropriate
        self.world.place_items(player_class)
    
    def display_title_screen(self):
        """Display the game title screen"""
        # Clear the screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        title = """
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
        """
        
        self.console.print(f"[bold cyan]{title}[/bold cyan]")
        self.console.print(Panel("A Terminal Adventure by Duhon Young", title="[bold]Welcome to the Haunted Filesystem[/bold]"))
    
    def display_main_menu(self):
        """Display the main menu with options"""
        self.console.print("\n[bold]Main Menu:[/bold]")
        self.console.print("1. [green]New Game[/green]")
        self.console.print("2. [blue]Load Game[/blue]")
        self.console.print("3. [red]Exit[/red]")
        self.console.print("\nPress the number key for your choice: ", end="")
        
        # Wait for valid input without the user needing to press Enter
        while True:
            key = readchar.readchar()
            if key in ["1", "2", "3"]:
                self.console.print(key)
                return key
            # Ignore other keys
        
    def get_player_name(self):
        """Get the player's name"""
        self.console.print("\nBefore we begin, please tell me your name, brave sysadmin:")
        player_name = input("> ")
        self.player.name = player_name
        
    def typing_effect(self, text, delay=0.03):
        """Display text with a typing effect"""
        import sys
        import time
        
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay)
        print()  # New line after typing
    
    def show_loading_bar(self, progress, width=40):
        """Display a loading bar with given progress (0-100)"""
        import sys
        
        # Calculate the number of filled and empty segments
        filled = int(width * progress / 100)
        empty = width - filled
        
        # Create the loading bar
        bar = "█" * filled + "░" * empty
        
        # Print the loading bar with percentage
        sys.stdout.write(f"\r[{bar}] {progress}%")
        sys.stdout.flush()
        
        # Add a newline if the loading is complete
        if progress == 100:
            print()
    
    def loading_screen(self, player_class):
        """Display a loading screen while generating class-specific content"""
        import sys
        import time
        import random
        
        # Skip the loading screen animation in debug mode
        if DEBUG_MODE:
            debug_log("Debug mode enabled - skipping loading screen animations")
            # Just do the necessary initialization work without animation
            self.initialize_special_items(player_class)
            complete_msg = f"[bold green]System initialization complete. Debug mode active.[/bold green]"
            self.console.print(f"\n{complete_msg}")
            return
            
        # Clear any previous output (if terminal supports it)
        print("\033[H\033[J", end="")
        
        # Main loading title with typing effect
        self.typing_effect("\n[SYSTEM INITIALIZATION PROTOCOL]", delay=0.05)
        time.sleep(0.5)
        
        # Get class-specific loading messages
        loading_messages = {
            "fighter": [
                "Loading security protocols...",
                "Calibrating weapon systems...",
                "Installing tactical overlays...",
                "Scanning for combat enhancements...",
                "Setting up defense parameters..."
            ],
            "mage": [
                "Compiling arcane algorithms...",
                "Initializing spell matrices...",
                "Calibrating magical resonance...",
                "Loading grimoire references...",
                "Activating mystical interfaces..."
            ],
            "celtic": [
                "Harmonizing with ancient networks...",
                "Aligning digital ley lines...",
                "Connecting to ancestral code...",
                "Initializing natural interfaces...",
                "Calibrating harmony protocols..."
            ]
        }
        
        messages = loading_messages.get(player_class, [
            "Loading system components...",
            "Initializing game elements...",
            "Setting up the environment...",
            "Preparing special items...",
            "Generating world state..."
        ])
        
        # Add final message
        final_message = "Finalizing system initialization..."
        
        # Print all messages first
        for message in messages:
            print(f"\033[34m> {message}\033[0m")
            time.sleep(0.3)
        
        # Print final message
        print(f"\033[34m> {final_message}\033[0m")
        
        # Show single loading bar progressing from 0 to 100
        for progress in range(0, 101):
            width = 40
            filled = int(width * progress / 100)
            empty = width - filled
            
            # Create the loading bar
            bar = "█" * filled + "░" * empty
            
            # Update the loading bar
            sys.stdout.write(f"\r[{bar}] {progress}%")
            sys.stdout.flush()
            
            # Randomize the speed to make it look realistic
            speed = random.uniform(0.01, 0.04) if progress < 95 else 0.1
            time.sleep(speed)
        
        # Add a newline after the loading bar is complete
        print()
        
        # Initialize special items for the chosen class (actually perform the work)
        self.initialize_special_items(player_class)
        
        # Loading complete message with class-specific flavor
        time.sleep(0.5)  # Brief pause for effect
        complete_messages = {
            "fighter": "[bold green]Combat systems online. Ready for deployment.[/bold green]",
            "mage": "[bold green]Arcane initialization complete. Magical systems online.[/bold green]",
            "celtic": "[bold green]Ancestral connections established. Natural systems harmonized.[/bold green]"
        }
        
        complete_msg = complete_messages.get(player_class, "[bold green]System initialization complete![/bold green]")
        self.console.print(f"\n{complete_msg}")
        time.sleep(1)  # Pause briefly before continuing
    
    def select_player_class(self):
        """Let the player choose their character class"""
        # Load available classes from classes.yaml
        from src.data_loader import load_class_data
        
        classes_data = load_class_data()
        if not classes_data:
            debug_log("ERROR: No classes available. Check classes.yaml file.")
            self.console.print("[bold red]ERROR: No classes available. Check classes.yaml file.[/bold red]")
            return "guardian"  # Last resort fallback
            
        self.console.print("\n[bold]Choose Your Character Class:[/bold]")
        
        # Create a table to display class options
        table = Table(title="Available Classes")
        table.add_column("Key", justify="center", style="cyan")
        table.add_column("Class", style="green")
        table.add_column("Health", justify="center")
        table.add_column("Damage", justify="center")
        table.add_column("Special Ability", justify="center") 
        table.add_column("Description")
        
        # Create mapping of keys to class IDs
        valid_choices = {}
        key_idx = 1
        
        # Iterate through available classes and add them to the table
        for class_id, class_info in classes_data.items():
            # Get special abilities (if specified)
            abilities = class_info.get("starter_abilities", [])
            special_ability = abilities[0] if abilities else "None"
            
            # Show formal name if available, otherwise format the ID
            class_name = class_info.get("name", class_id.replace("_", " ").title())
            
            # Add class to table
            table.add_row(
                str(key_idx),                               # Key
                class_name,                                 # Class name
                str(class_info.get("base_health", 100)),    # Health
                str(class_info.get("base_damage", 5)),      # Damage
                special_ability.replace("_", " ").title(),  # Special ability
                class_info.get("description", "No description available.")  # Description
            )
            
            # Map key to class ID
            valid_choices[str(key_idx)] = class_id
            key_idx += 1
        
        self.console.print(table)
        self.console.print("\nPress the number key for your choice: ", end="")
        
        # Get single keystroke choice
        while True:
            key = readchar.readchar()
            if key in valid_choices:
                chosen_class = valid_choices[key]
                self.console.print(key)
                break
            # Ignore invalid keys
        
        # Create player with chosen class
        self.player = Player(player_class=chosen_class, current_room="root")
        
        # Get the proper name for display
        class_info = classes_data.get(chosen_class, {})
        class_display_name = class_info.get("name", chosen_class.title())
        
        # Display confirmation
        self.console.print(f"\n[bold green]You have chosen the {class_display_name} class![/bold green]")
        self.console.print(f"[italic]{self.player.class_description}[/italic]")
        
        return chosen_class
    
    def start_new_game(self):
        """Start a new game."""
        # Short introduction after title screen
        self.console.print("\nSystem breach detected. Security protocol initiated.")
        self.console.print("Initiating system recovery process...")
        
        # Select character class first
        chosen_class = self.select_player_class()
        
        # Then get player name
        self.get_player_name()
        
        # Show loading screen and generate class-specific content
        self.loading_screen(chosen_class)
        
        # Initialize the command handler with the created player
        self.cmd_handler = CommandHandler(self.player, self.world, self.console)
        
        self.console.print("\nYou find yourself in a mysterious terminal room, your adventure begins...")
        self.game_state = "playing"
    
    def display_load_game_menu(self):
        """Display a menu of saved games to load"""
        # Get saved games
        save_files = save_manager.get_save_files()
        
        if not save_files:
            self.console.print("[italic yellow]No saved games found.[/italic yellow]")
            return None
        
        self.console.print("\n[bold]Select a saved game to load:[/bold]")
        
        # Create a table to display save files
        table = Table(title="Saved Games")
        table.add_column("Key", justify="center", style="cyan")
        table.add_column("Character", style="green")
        table.add_column("Class", style="blue")
        table.add_column("Location", style="magenta")
        table.add_column("Date", style="yellow")
        
        # Add save files to table
        for i, save_info in enumerate(save_files):
            table.add_row(
                str(i+1),
                save_info["player_name"],
                save_info["player_class"].title(),
                save_info["location"],
                save_info["date"]
            )
        
        self.console.print(table)
        self.console.print("\nPress the number key to load a game (or 'x' to go back): ", end="")
        
        # Wait for valid input
        while True:
            key = readchar.readchar()
            if key.lower() == 'x':
                self.console.print(key)
                return None
            
            try:
                index = int(key) - 1
                if 0 <= index < len(save_files):
                    self.console.print(key)
                    return save_files[index]["filename"]
            except ValueError:
                pass
            # Ignore invalid keys
    
    def load_saved_game(self, filename):
        """Load a saved game"""
        save_data = save_manager.load_game(filename)
        
        if not save_data:
            self.console.print("[bold red]Error: Could not load save file.[/bold red]")
            return False
        
        # Load player data
        player_data = save_data["player"]
        self.player = Player.from_dict(player_data)
        
        # Load world state
        world_state = save_data["world"]
        self.world.set_state(world_state)
        
        # Initialize command handler with loaded data
        self.cmd_handler = CommandHandler(self.player, self.world, self.console)
        
        self.console.print(f"\n[bold green]Welcome back, {self.player.name}![/bold green]")
        self.console.print("[italic]Your adventure continues...[/italic]")
        
        self.game_state = "playing"
        return True
    
    def save_current_game(self):
        """Save the current game state"""
        if not self.player:
            return False
        
        # Get world state
        world_state = self.world.get_state()
        
        # Save the game
        save_path = save_manager.save_game(self.player, world_state)
        
        self.console.print(f"[bold green]Game saved successfully![/bold green]")
        return True
    
    def run(self):
        """Run the game"""
        debug_log("Starting game engine run loop")
        # Clear the screen at startup
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Import readline for tab completion
        try:
            import readline
            import platform
            tab_completion_enabled = True
            debug_log("Tab completion enabled")
        except ImportError:
            tab_completion_enabled = False
            debug_log("Tab completion not available (readline import failed)")
        
        # Setup tab completion if available
        if tab_completion_enabled:
            # Tab completer function
            def tab_completer(text, state):
                # Get possible completions based on current state
                if self.player and self.cmd_handler:
                    # Start with basic commands
                    commands = ["help", "ls", "cd", "cat", "map", "inventory", "inv", 
                                "take", "drop", "use", "examine", "talk", "attack", "look", "quit"]
                    
                    # Add items in inventory
                    if self.player.inventory:
                        commands.extend(self.player.get_inventory_items())
                    
                    # Add items in current room and exits
                    if self.player.current_room and hasattr(self.world, 'get_items_in_room'):
                        current_room = self.player.current_room
                        # Add items in room
                        commands.extend(self.world.get_items_in_room(current_room))
                        # Add room exits
                        commands.extend(self.world.get_exits(current_room))
                    
                    # Filter for matches to what user has typed so far
                    matches = [cmd for cmd in commands if cmd.startswith(text)]
                    
                    # Return the state-th match or None if no more matches
                    return matches[state] if state < len(matches) else None
                return None
            
            # Set up the completer function
            readline.set_completer(tab_completer)
            
            # Use different binding command based on platform
            if platform.system() == 'Darwin':  # macOS
                readline.parse_and_bind("bind ^I rl_complete")
            else:  # Linux, Windows with readline
                readline.parse_and_bind("tab: complete")
            
            # Disable autocomplete's automatic addition of spaces after completions
            readline.set_completion_append_character = ""
        
        self.display_title_screen()
        
        # Main game loop - start with main menu
        while True:
            if self.game_state == "menu":
                choice = self.display_main_menu()
                debug_log(f"Main menu choice: {choice}")
        
                if choice == "1":  # New Game
                    debug_log("Starting new game")
                    self.start_new_game()
                    # Display starting location
                    self.cmd_handler.display_location()
        
                elif choice == "2":  # Load Game
                    debug_log("Loading saved game")
                    # Display load game menu
                    save_filename = self.display_load_game_menu()
                    if save_filename:
                        debug_log(f"Selected save file: {save_filename}")
                        # Try to load the game
                        if self.load_saved_game(save_filename):
                            debug_log("Game loaded successfully")
                            # Display current location
                            self.cmd_handler.display_location()
                        else:
                            debug_log("Failed to load game")
                            # Failed to load, stay in menu
                            self.game_state = "menu"
                    else:
                        debug_log("Load game cancelled")
                        # User cancelled load, stay in menu
                        self.game_state = "menu"
                        
                elif choice == "3":  # Exit
                    debug_log("Exiting game")
                    self.console.print("[bold]Thanks for playing! Goodbye![/bold]")
                    return
            
            elif self.game_state == "playing":
                try:
                    # Get and process player command
                    command = input(f"[{self.player.current_room}]> ").strip()
                    debug_log(f"Player command: '{command}' in room: {self.player.current_room}")
                    
                    if command.lower() == "quit":
                        debug_log("Player initiated quit command")
                        self.console.print("Save Game? (y/n) ", end="")
                        save_choice = readchar.readchar().lower()
                        self.console.print(save_choice)
                        
                        if save_choice == 'y':
                            debug_log("Saving game before quit")
                            self.save_current_game()
                        
                        self.console.print("Return to main menu? (y/n) ", end="")
                        menu_choice = readchar.readchar().lower()
                        self.console.print(menu_choice)
                    
                        if menu_choice == 'y':
                            debug_log("Returning to main menu")
                            self.game_state = "menu"
                        else:
                            debug_log("Exiting game completely")
                            self.console.print("Thanks for playing! Exiting the Haunted Filesystem.")
                            return
                    else:
                        command_type = command.split()[0].lower() if command.split() else ""
                        debug_log(f"Processing command type: {command_type}")
                        self.cmd_handler.handle_command(command)
                
                except KeyboardInterrupt:
                    debug_log("KeyboardInterrupt detected")
                    self.console.print("\nUse 'quit' to exit the game properly.")
                except Exception as e:
                    debug_log(f"Error during gameplay: {e}")
                    self.console.print(f"[bold red]Error: {e}[/bold red]")
            
            elif self.game_state == "game_over":
                debug_log("Game over state reached")
                self.console.print("\nGAME OVER")
                self.console.print("Would you like to return to the main menu? (y/n): ", end="")
                restart = readchar.readchar().lower()
                self.console.print(restart)
                
                if restart == 'y':
                    debug_log("Returning to main menu after game over")
                    self.game_state = "menu"
                else:
                    debug_log("Exiting game after game over")
                    self.console.print("Goodbye!")
                    return

# Main function to start the game
def main():
    """Main function to start the game"""
    engine = GameEngine()
    engine.run()

if __name__ == "__main__":
    main() 
