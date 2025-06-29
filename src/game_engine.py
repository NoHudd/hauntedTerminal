#!/usr/bin/env python3
import os
import sys
import yaml
import json
import time
import random
import readchar
from rich.console import Console
from rich.live import Live

# Import game components
from src.game_world import GameWorld
from src.player import Player
from src.command_handler import CommandHandler
from src.save import save_manager
from src.ui import UISystem
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
        self.current_room = "home_grove"
        self.game_state = "menu"  # menu, playing, game_over, exit
        self.save_dir = "saves"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self.console = Console()
        self.ui = UISystem()
        self.load_game_data()
        
    def load_game_data(self):
        """Load all game data from YAML files"""
        debug_log("Loading game data")
        try:
            rooms = {}
            for filename in os.listdir('data/rooms'):
                if filename.endswith(('.yaml', '.yml')):
                    with open(f'data/rooms/{filename}', 'r') as file:
                        room_data = yaml.safe_load(file)
                        if room_data:
                            room_id = os.path.splitext(filename)[0]
                            rooms[room_id] = room_data
            
            items = self.load_items()
            enemies = self.load_data_from_dir('data/enemies', 'enemies')
            npcs = self.load_data_from_dir('data/npcs', 'npcs')

            self.world = GameWorld(rooms, items, enemies, npcs)
            self.items = self.world.items # Ensure engine has direct access to all items
            self.player = None
            self.cmd_handler = None
            
        except Exception as e:
            console.print(f"[bold red]Critical error loading game data: {e}[/bold red]")
            sys.exit(1)

    def load_data_from_dir(self, directory, category_key):
        """Generic data loader for enemies and NPCs."""
        data_map = {}
        for filename in os.listdir(directory):
            if filename.endswith(('.yaml', '.yml')):
                with open(os.path.join(directory, filename), 'r') as file:
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
        return data_map

    def load_items(self):
        """Load all items from categorized YAML files into a single dictionary."""
        items = {}
        for filename in os.listdir('data/items'):
            if filename.endswith(('.yaml', '.yml')):
                filepath = os.path.join('data/items', filename)
                with open(filepath, 'r') as file:
                    data = yaml.safe_load(file)
                    if data:
                        category = os.path.splitext(filename)[0]
                        for item_id, item_data in data.get(category, {}).items():
                            item_data['id'] = item_id
                            if 'type' not in item_data:
                                item_data['type'] = category.rstrip('s')
                            items[item_id] = item_data
        return items
    
    def initialize_special_items(self, player_class):
        """Create and place special enhancement items based on player class"""
        self.world.place_items(player_class)
    
    def display_title_screen(self):
        """Displays the game title screen in the UI."""
        title_ascii = """
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
A Terminal Adventure by Duhon Young"""
        
        from rich.text import Text
        
        # Create Rich Text with ASCII art and subtitle (no extra panel border)
        title_text = Text()
        title_text.append(title_ascii, style="bold cyan")
        
        self.ui.update_output(title_text)
        
    def display_main_menu(self):
        """Displays the main menu in the UI."""
        from rich.panel import Panel
        from rich.align import Align
        
        # Clear previous content and show menu
        menu_content = """
[bold cyan]═══════════════════════════════════════[/bold cyan]
[bold white]                MAIN MENU                [/bold white]
[bold cyan]═══════════════════════════════════════[/bold cyan]


    [bold green]1.[/bold green] [green]New Game[/green]

    [bold blue]2.[/bold blue] [blue]Load Game[/blue]

    [bold red]3.[/bold red] [red]Exit[/red]


[bold cyan]═══════════════════════════════════════[/bold cyan]
"""
        
        # Center the menu in the output panel
        centered_menu = Align.center(menu_content, vertical="middle")
        self.ui.update_output(centered_menu)
        
    def get_player_name(self):
        """Get the player's name using the UI system."""
        from rich.text import Text
        import readchar
        
        # Display the prompt
        prompt_text = Text("\nBefore we begin, please tell me your name, brave sysadmin:", style="white")
        self.ui.update_output(prompt_text)
        
        # Get input using a simple input loop
        current_input = ""
        default_name = f"User-{random.randint(100, 999)}"
        
        # Show the input prompt
        input_prompt = Text(f"\nEnter name (or press Enter for '{default_name}'): ", style="cyan")
        self.ui.update_output(input_prompt)
        
        while True:
            # Update input panel
            self.ui.update_input_panel(current_input, True)
            
            # Wait for key press
            char = readchar.readkey()
            
            if char in (readchar.key.ENTER, '\r'):
                # Use default if no input provided
                self.player.name = current_input if current_input.strip() else default_name
                break
            elif char in (readchar.key.BACKSPACE, '\x7f'):
                current_input = current_input[:-1]
            elif char.isprintable():
                current_input += char
        
        # Show confirmation
        confirm_text = Text(f"\nWelcome, {self.player.name}!\n", style="bold green")
        self.ui.update_output(confirm_text)
        time.sleep(1)
        
        # Clear console to start fresh for the actual game
        self.ui.clear_console()

    def loading_screen(self, player_class):
        """Displays a loading screen in the UI."""
        from rich.panel import Panel
        from rich.text import Text
        
        # Display initialization header
        self.ui.update_output(Panel("System Initialization", style="bold cyan"))
        
        if DEBUG_MODE:
            self.initialize_special_items(player_class)
            debug_text = Text("Debug mode: Skipping animations. System ready.", style="bold green")
            self.ui.update_output(debug_text)
            time.sleep(1)
            return

        messages = {
            "fighter": ["Loading security protocols...", "Calibrating weapon systems..."],
            "mage": ["Compiling arcane algorithms...", "Initializing spell matrices..."],
            "celtic": ["Harmonizing with ancient networks...", "Connecting to ancestral code..."]
        }.get(player_class, ["Loading system components..."])

        # Display loading messages
        loading_text = Text()
        loading_text.append("Initializing...\n\n", style="bold green")
        
        for msg in messages:
            loading_text.append(f"• {msg}\n", style="cyan")
            
        self.initialize_special_items(player_class)
        loading_text.append("\n• Initialization Complete!", style="bold green")
        
        self.ui.update_output(loading_text)
        time.sleep(2)  # Give time to read the messages

    def select_player_class(self):
        """Allows the player to select a class in the UI."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from src.data_loader import load_class_data
        
        # Display header
        self.ui.update_output(Panel("Choose Your Class", style="bold cyan"))
        
        classes_data = load_class_data()
        if not classes_data:
            error_text = Text("ERROR: No classes available. Using default.", style="bold red")
            self.ui.update_output(error_text)
            return "fighter"

        # Create class selection table
        table = Table(title="Select Your Class")
        table.add_column("Choice", style="cyan")
        table.add_column("Class", style="bold")
        table.add_column("Description")

        class_map = {str(i + 1): cid for i, cid in enumerate(classes_data.keys())}
        for choice, class_id in class_map.items():
            info = classes_data[class_id]
            table.add_row(choice, info.get('name', class_id.title()), info.get('description', ''))
        
        self.ui.update_output(table)
        
        # Use UI-based input for class selection
        choice = self.menu_input_loop(list(class_map.keys()), "Enter the number of your choice (1-3): ")
        return class_map[choice]

    def start_new_game(self):
        """Starts a new game."""
        player_class = self.select_player_class()
        self.player = Player(player_class)
        self.get_player_name()
        self.loading_screen(player_class)
        self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
        self.game_state = "playing"

    def display_load_game_menu(self):
        """Displays the load game menu and handles loading in the UI."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        
        self.ui.update_output(Panel("Load Game", style="bold cyan"))
        saves = save_manager.list_saves(self.save_dir)
        if not saves:
            no_saves_text = Text("No saved games found.", style="yellow")
            self.ui.update_output(no_saves_text)
            time.sleep(2)
            return False

        table = Table(title="Saved Games")
        table.add_column("Slot", style="cyan")
        table.add_column("Save Name")
        table.add_column("Timestamp")

        for i, (save_file, timestamp) in enumerate(saves):
            table.add_row(str(i + 1), save_file.replace('.json', ''), timestamp)
        
        self.ui.update_output(table)
        
        # Create valid choices including slot numbers and 'back'
        valid_choices = [str(i + 1) for i in range(len(saves))] + ['back']
        choice = self.menu_input_loop(valid_choices, "Enter slot to load, or 'back': ")
        
        if choice.lower() == 'back':
            return False
        
        try:
            slot = int(choice) - 1
            if 0 <= slot < len(saves):
                save_file_to_load = saves[slot][0]
                if save_manager.load_game(self, os.path.join(self.save_dir, save_file_to_load)):
                    self.cmd_handler = CommandHandler(self.player, self.world, self.ui)
                    success_text = Text("Game loaded successfully!", style="bold green")
                    self.ui.update_output(success_text)
                    time.sleep(1)
                    return True
            error_text = Text("Failed to load game.", style="red")
            self.ui.update_output(error_text)
        except (ValueError, IndexError):
            invalid_text = Text("Invalid slot.", style="yellow")
            self.ui.update_output(invalid_text)
        time.sleep(1)
        return False

    def get_short_item_description(self, item):
        """Get a short, consistent description for items used across all displays."""
        if not item:
            return ""
            
        # Determine item effect based on type and properties
        effect = ""
        
        # Healing items
        if "on_use" in item and "heal" in item["on_use"]:
            effect = f"(+{item['on_use']['heal']} HP)"
        elif "effect" in item and "heal" in item["effect"]:
            effect = f"(+{item['effect']['heal']} HP)"
        elif "combat_effects" in item and "player_heal" in item["combat_effects"]:
            effect = f"(+{item['combat_effects']['player_heal']} HP)"
        elif "boost_amount" in item and item.get("item_type") == "health_boost":
            effect = f"(+{item['boost_amount']} HP)"
        
        # Damage-dealing items
        elif "on_use" in item and "damage" in item["on_use"]:
            effect = f"(+{item['on_use']['damage']} DMG)"
        
        # Status effect items
        elif "on_use" in item and "status_effect" in item["on_use"]:
            effect_name = item["on_use"]["status_effect"].get("name", "Effect")
            effect = f"({effect_name})"
        
        # Weapons
        elif item.get("type") == "weapon" or "weapon" in str(item.get("type", "")):
            bonus = item.get("bonus_total_damage", 0)
            if bonus > 0:
                effect = f"(+{bonus} DMG)"
        
        # Upgrade items
        elif "effects" in item:
            effects = []
            if "permanent_health" in item["effects"]:
                effects.append(f"+{item['effects']['permanent_health']} HP")
            if "permanent_damage" in item["effects"]:
                effects.append(f"+{item['effects']['permanent_damage']} DMG")
            if effects:
                effect = f"(Perm: {'/'.join(effects)})"
        
        # Key items
        elif item.get("type") == "key" or "unlocks" in item:
            effect = "(Key)"
            
        return effect

    def update_game_ui_panels(self):
        """Update all game UI panels with current game state."""
        # Update stats panel
        stats_text = f"HP: {self.player.health}/{self.player.max_health}\nAttack: {self.player.total_damage}"
        if self.player.equipped_weapon:
            weapon_name = self.world.items.get(self.player.equipped_weapon, {}).get('name', self.player.equipped_weapon)
            stats_text += f"\nWeapon: {weapon_name}"
        hp_percentage = (self.player.health / self.player.max_health) * 100 if self.player.max_health > 0 else 0
        if hp_percentage < 40:
            hp_color = "bold red"
        elif hp_percentage < 80:
            hp_color = "bold yellow"
        else:
            hp_color = "bold green"
        stats_text = f"HP: [{hp_color}]{self.player.health}[/{hp_color}]/{self.player.max_health}\nAttack: [bold blue]{self.player.total_damage}[/bold blue]"
        self.ui.update_stats(stats_text)
        
        # Update inventory panel with detailed item information
        inventory_lines = []
        for item_id in self.player.inventory:
            item = self.world.items.get(item_id, {})
            item_name = item.get('name', item_id)
            
            # Build the display line with filename and effects
            display_parts = [item_id]  # Start with filename for command reference
            
            # Add equipment status
            if item_id == self.player.equipped_weapon:
                display_parts.append("[bold blue](Equipped)[/bold blue]")
            else:
                # Add item effect description
                effect = self.get_short_item_description(item)
                if effect:
                    display_parts.append(f"[bold green]{effect}[/bold green]")
            
            inventory_lines.append(f"- {' '.join(display_parts)}")
        
        inventory_text = "\n".join(inventory_lines) if inventory_lines else "Empty"
        self.ui.update_inventory(inventory_text)
        
        # Update exits panel with lock information
        current_room_data = self.world.get_room(self.player.current_room)
        exits_list = current_room_data.get('exits', [])
        
        # Prepare detailed exit information including lock status
        detailed_exits = []
        for exit_room_id in exits_list:
            exit_room_data = self.world.get_room(exit_room_id)
            if exit_room_data:
                exit_info = {
                    'name': exit_room_data.get('name', exit_room_id),
                    'room_id': exit_room_id,
                    'locked': exit_room_data.get('locked', False),
                    'key_required': exit_room_data.get('key_required', None)
                }
                detailed_exits.append(exit_info)
            else:
                # Fallback for missing room data
                detailed_exits.append({
                    'name': exit_room_id,
                    'room_id': exit_room_id,
                    'locked': False,
                    'key_required': None
                })
        
        self.ui.update_exits(detailed_exits)

    def live_game_loop(self):
        """The main, interactive game loop using Rich Live display."""
        if not self.ui:
            self.console.print("[bold red]UI not initialized. Cannot start game loop.[/bold red]")
            return

        current_input = ""
        cursor_visible = True
        last_cursor_toggle = time.time()

        with Live(self.ui.layout, screen=True, redirect_stderr=False) as live:
            self.ui.update_player_name(self.player.name)
            self.ui.update_output(self.world.get_formatted_room_description(self.player.current_room))
            # Initial UI panel update
            self.update_game_ui_panels()
            
            while self.game_state == "playing":
                # Handle cursor blinking
                if time.time() - last_cursor_toggle > 0.5:
                    cursor_visible = not cursor_visible
                    last_cursor_toggle = time.time()

                char = readchar.readkey()
                        
                if char:
                    if char in (readchar.key.ENTER, '\r'):
                        if current_input:
                            if current_input.lower() == "save":
                                self.save_current_game()
                            else:
                                self.cmd_handler.handle_command(current_input)
                            
                            # Update UI panels only after command execution
                            self.update_game_ui_panels()
                            
                            if current_input.lower() in ['quit', 'exit']:
                                self.game_state = "menu"
                            current_input = ""
                    elif char in (readchar.key.BACKSPACE, '\x7f'):
                        current_input = current_input[:-1]
                    else:
                        current_input += char
                
                # Update input panel after processing input
                self.ui.update_input_panel(current_input, cursor_visible)
                
                if self.player.is_dead():
                    self.game_state = "game_over"
                    break
                
                if self.game_state != "playing":
                    break

    def save_current_game(self):
        """Saves the current game state and provides UI feedback."""
        self.ui.update_output("[yellow]Saving game...[/yellow]")
        time.sleep(0.5) # Brief pause for effect
        if save_manager.save_game(self.player, self.world.get_state()):
            self.ui.update_output("[bold green]Game saved successfully![/bold green]")
        else:
            self.ui.update_output("[bold red]Failed to save game.[/bold red]")
        time.sleep(1.5)
        # Restore the previous room description after the message
        self.ui.update_output(self.world.get_formatted_room_description(self.player.current_room))

    def display_game_over(self):
        """Displays the game over screen in the UI."""
        from rich.panel import Panel
        from rich.text import Text
        
        # Clear the UI and show game over
        self.ui.update_output(Panel("[bold red]GAME OVER[/bold red]", title="System Critical Failure"))
        
        game_over_text = Text()
        game_over_text.append(f"Brave sysadmin {self.player.name}, your session has been terminated.\n\n", style="white")
        game_over_text.append("Press any key to return to the main menu...", style="yellow")
        
        self.ui.update_output(game_over_text)
        readchar.readkey()
        self.game_state = "menu"

    def menu_input_loop(self, valid_choices, prompt_text="Enter your choice: "):
        """Handle UI-based input for menu selections (assumes Live context is already active)."""
        from rich.text import Text
        import readchar
        
        current_input = ""
        
        # Show the prompt in the input panel instead of the output panel
        self.ui.update_input_panel(f"{prompt_text} ", True)
        
        while True:
            # Update input panel
            self.ui.update_input_panel(current_input, True)
            
            # Wait for key press
            char = readchar.readkey()
            
            if char in (readchar.key.ENTER, '\r'):
                if current_input in valid_choices:
                    return current_input
                elif current_input == "":
                    # Return default choice (first one)
                    return valid_choices[0] if valid_choices else None
                else:
                    # Invalid choice, show error in output panel
                    error_text = Text(f"Invalid choice '{current_input}'. Please enter one of: {', '.join(valid_choices)}", style="red")
                    self.ui.update_output(error_text)
                    # Reset input and show prompt again
                    current_input = ""
                    self.ui.update_input_panel(f"{prompt_text} ", True)
            elif char in (readchar.key.BACKSPACE, '\x7f'):
                current_input = current_input[:-1]
            elif char.isprintable():
                current_input += char

    def run(self):
        """Main game loop that manages game states."""
        # Initialize UI system early for all menu screens
        from src.ui import UISystem
        from rich.live import Live
        self.ui = UISystem()
        
        # Use a single Live context for all menu interactions
        with Live(self.ui.layout, screen=True, redirect_stderr=False) as live:
            # Show title screen
            self.display_title_screen()
            time.sleep(3)  # Give time to read the title
            
            # Clear console after title screen
            self.ui.clear_console()

            while self.game_state != "exit":
                if self.game_state == "menu":
                    # Show menu in UI
                    self.display_main_menu()
                    
                    # Use UI-based input for menu selection
                    choice = self.menu_input_loop(["1", "2", "3"], "Enter your choice (1-3): ")
                    
                    # Clear console after menu selection
                    self.ui.clear_console()
                    
                    if choice == "1":
                        self.start_new_game()
                    elif choice == "2":
                        if self.display_load_game_menu():
                            self.game_state = "playing"
                            break  # Exit Live context to start game loop
                    elif choice == "3":
                        self.game_state = "exit"

                elif self.game_state == "game_over":
                    self.display_game_over()
                    
                # If we're starting to play, break out of menu Live context
                if self.game_state == "playing":
                    break
            
            # Show goodbye message if exiting
            if self.game_state == "exit":
                from rich.text import Text
                goodbye_text = Text("\nThank you for playing Haunted Filesystem!", style="bold cyan")
                self.ui.update_output(goodbye_text)
                time.sleep(2)
        
        # Handle the playing state outside the menu Live context
        if self.game_state == "playing":
            self.live_game_loop()
            # After game ends, return to menu
            if self.game_state != "exit":
                self.run()  # Restart the menu system

def main():
    """The main entry point for the game."""
    try:
        engine = GameEngine()
        engine.run()
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
