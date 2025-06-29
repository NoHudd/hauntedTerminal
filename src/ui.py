from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console
from rich.text import Text
from rich.table import Table
import rich.box

console = Console()

class UISystem:
    """Manages the terminal-based UI using Rich."""

    def __init__(self):
        """Initializes the UI system and creates the layout."""
        self.player_name = ""
        self.inventory_content = ""
        self.message_history = []  # Store console messages
        self.max_messages = 100  # Limit message history to prevent memory issues
        self.visible_lines = 25  # Number of lines visible in console panel
        self.layout = self.create_layout()
        self.update_all_panels_to_defaults()

    def create_layout(self):
        """Creates the UI layout structure."""
        layout = Layout()
        layout.split(
            Layout(name="header", size=1),
            Layout(ratio=1, name="main"),
            Layout(name="footer", size=3),
        )
        layout["main"].split_row(Layout(name="output", ratio=3), Layout(name="sidebar"))
        layout["main"]["sidebar"].split(Layout(name="inventory"), Layout(name="stats"), Layout(name="exits"))
        return layout

    def update_all_panels_to_defaults(self):
        """Sets the initial content for all UI panels."""
        self._update_header()
        self.update_output("Welcome to The Haunted Filesystem!")
        self.update_inventory("")
        self.update_stats("")
        self.update_exits({})
        self.update_input_panel("")

    def _update_header(self):
        """Builds and updates the header panel with a centered title."""
        title = Text("The Haunted Filesystem", justify="center", style="bold cyan")
        self.layout['header'].update(title)

    def _build_and_update_inventory_panel(self):
        """Builds the content for the inventory panel and updates it."""
        if not self.player_name and not self.inventory_content:
            # Empty panel when no player or inventory
            self.layout['main']['sidebar']['inventory'].update(Panel("", title="Inventory", border_style="yellow"))
        else:
            player_display = self.player_name if self.player_name else "[Not Set]"
            player_text = Text.assemble(("Player: ", "bold"), (f"{player_display}\n", "yellow"), "─" * 20 + "\n")
            inventory_text = Text.from_markup(self.inventory_content) if self.inventory_content else Text("")
            combined_content = Text.assemble(player_text, inventory_text)
            self.layout['main']['sidebar']['inventory'].update(Panel(combined_content, title="Inventory", border_style="yellow"))

    def update_player_name(self, name: str):
        """Updates the player name and refreshes the inventory panel."""
        self.player_name = name
        self._build_and_update_inventory_panel()

    def update_inventory(self, content: str):
        """Updates the inventory items and refreshes the panel."""
        self.inventory_content = content
        self._build_and_update_inventory_panel()

    def update_output(self, content):
        """Adds new content to the console output history."""
        # Add spacing if this isn't the first message
        if self.message_history:
            self.message_history.append("")  # Empty line for spacing
        
        # Handle different content types while preserving Rich formatting
        if isinstance(content, Panel):
            # For Panel objects, preserve the title and content separately
            title = content.title if content.title else ""
            if title:
                self.message_history.append(f"[bold cyan]═══ {title} ═══[/bold cyan]")
            # Add the panel content directly (preserving Rich formatting)
            self.message_history.append(content.renderable)
        else:
            # Add content directly (preserving Rich formatting for strings)
            self.message_history.append(content)
        
        # Keep only the most recent messages to prevent memory issues
        if len(self.message_history) > self.max_messages:
            self.message_history = self.message_history[-self.max_messages:]
        
        # Calculate how many lines each message takes and show only what fits
        visible_messages = []
        total_lines = 0
        
        # Work backwards from the most recent messages
        for message in reversed(self.message_history):
            # Estimate lines needed for this message
            if hasattr(message, '__rich_console__') or hasattr(message, '__rich__'):
                # For Rich objects, estimate based on content
                estimated_lines = 3  # Conservative estimate for Rich objects
            else:
                # For strings, count actual lines
                estimated_lines = str(message).count('\n') + 1
            
            if total_lines + estimated_lines <= self.visible_lines:
                visible_messages.insert(0, message)  # Insert at beginning to maintain order
                total_lines += estimated_lines
            else:
                break
        
        # Create console view with only visible messages
        from rich.console import Group
        if visible_messages:
            console_group = Group(*visible_messages)
        else:
            console_group = ""
        
        # Update the output panel with visible messages
        self.layout['main']['output'].update(Panel(console_group, title="Console", border_style="blue"))
    
    def clear_console(self):
        """Clears the console message history."""
        self.message_history = []
        self.layout['main']['output'].update(Panel("", title="Console", border_style="blue"))

    def update_stats(self, content):
        """Updates the player stats panel."""
        self.layout['main']['sidebar']['stats'].update(Panel(content, title="Stats", border_style="green"))

    def update_exits(self, exits):
        """Updates the exits panel with available directions."""
        if not exits:
            exit_text = "No obvious exits."
        else:
            # Handle both dictionary and list formats
            if isinstance(exits, dict):
                exit_lines = []
                for direction, room_info in exits.items():
                    # Check if room_info is a dict with lock information
                    if isinstance(room_info, dict):
                        room_name = room_info.get('name', 'Unknown')
                        room_id = room_info.get('room_id', direction)
                        if room_info.get('locked', False):
                            exit_lines.append(f"[bold white]{room_name}[/bold white] -> [bold cyan]{room_id}[/bold cyan] [bold red](Locked)[/bold red]")
                        else:
                            exit_lines.append(f"[bold white]{room_name}[/bold white] -> [bold cyan]{room_id}[/bold cyan]")
                    else:
                        # Simple string format (backward compatibility)
                        exit_lines.append(f"[bold cyan]{direction.capitalize()}[/bold cyan] -> {room_info}")
                exit_text = "\n".join(exit_lines)
            elif isinstance(exits, list):
                exit_lines = []
                for exit_info in exits:
                    if isinstance(exit_info, dict):
                        room_name = exit_info.get('name', 'Unknown')
                        room_id = exit_info.get('room_id', 'unknown')
                        if exit_info.get('locked', False):
                            exit_lines.append(f"[bold white]{room_name}[/bold white] -> [bold cyan]{room_id}[/bold cyan] [bold red](Locked)[/bold red]")
                        else:
                            exit_lines.append(f"[bold white]{room_name}[/bold white] -> [bold cyan]{room_id}[/bold cyan]")
                    else:
                        # Simple string format (backward compatibility)
                        exit_lines.append(f"[bold cyan]{exit_info}[/bold cyan]")
                exit_text = "\n".join(exit_lines)
            else:
                exit_text = "Invalid exits format"
        
        self.layout['main']['sidebar']['exits'].update(Panel(exit_text, title="Exits", border_style="blue"))

    def update_game_state_panels(self, player, world):
        """Updates all panels that display dynamic game state."""
        # Update Stats Panel with color-coded HP
        hp_percentage = (player.health / player.max_health) * 100 if player.max_health > 0 else 0
        
        # Determine HP color based on percentage
        if hp_percentage < 40:
            hp_color = "red"
        elif hp_percentage < 80:
            hp_color = "yellow"
        else:
            hp_color = "bold green"
        
        stats_text = f"HP: [{hp_color}]{player.health}[/{hp_color}]/{player.max_health}\nAttack: {player.total_damage}"
        if player.equipped_weapon:
            weapon_name = world.items.get(player.equipped_weapon, {}).get('name', player.equipped_weapon)
            stats_text += f"\nWeapon: {weapon_name}"
        self.update_stats(stats_text)

        # Update Inventory Panel
        inventory_items = [world.items.get(item_id, {}).get('name', item_id) for item_id in player.inventory]
        inventory_text = "\n".join(f"- {item}" for item in inventory_items) if inventory_items else "Empty"
        self.update_inventory(inventory_text)

        # Update Exits Panel
        exits_list = world.get_exits(player.current_room)
        if not exits_list:
            exit_text = "No obvious exits."
        else:
            exit_lines = []
            for exit_name in exits_list:
                room_data = world.get_room(exit_name)
                room_name = room_data.get("name", exit_name) if room_data else exit_name
                
                # Check if room is locked
                room_state = world.get_room_state(exit_name)
                is_locked = room_state.get("locked", False) if room_state else False
                
                # Format: "Room Name -> directory_name" with optional (Locked) in red
                display_text = f"[bold cyan]{room_name}[/bold cyan] -> {exit_name}"
                if is_locked:
                    display_text += " [bold red](Locked)[/bold red]"
                
                exit_lines.append(display_text)
            
            exit_text = "\n".join(exit_lines)
        
        # Update the exits panel directly
        from rich.panel import Panel
        self.layout['main']['sidebar']['exits'].update(Panel(exit_text, title="Exits", border_style="blue"))

    def update_input_panel(self, current_input, cursor_visible=True):
        """Updates the input panel with the current text and a cursor."""
        cursor = "█" if cursor_visible else ""
        self.layout["footer"].update(Panel(f"> {current_input}{cursor}", title="Input", border_style="cyan"))