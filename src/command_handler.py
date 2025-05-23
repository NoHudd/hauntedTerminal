#!/usr/bin/env python3
import os
import random
import readchar
from rich.panel import Panel
from rich.text import Text
from src.combat import combat_system
from debug_tools import debug_log

class CommandHandler:
    """Handles processing of player commands"""
    
    def __init__(self, player, world, console):
        """Initialize with player and world references"""
        debug_log("Initializing CommandHandler")
        self.player = player
        self.world = world
        self.console = console
        
        # Command dispatcher dictionary for easy command handling
        self.commands = {
            "help": self.show_help,
            "ls": self.list_directory,
            "cd": self.change_directory,
            "cat": self.read_file,
            "map": self.show_map,
            "inventory": self.show_inventory,
            "inv": self.show_inventory,
            "take": self.take_item,
            "drop": self.drop_item,
            "use": self.use_item,
            "examine": self.examine_item,
            "talk": self.talk_to_npc,
            "attack": self.attack_enemy,
            "look": self.look_around,
            "stats": self.show_player_stats
        }
        
        # Specify which commands require arguments
        self.commands_with_args = {
            "cd", "cat", "take", "drop", "use", "examine", "talk", "attack"
        }
        
        debug_log(f"Registered {len(self.commands)} commands")
        
    def handle_command(self, command):
        """Process a command from the player"""
        cmd_parts = command.split()
        
        if not cmd_parts:
            debug_log("Empty command received")
            return
        
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        debug_log(f"Processing command: '{cmd}' with args: {args}")
        
        # Use the command dispatcher to handle commands
        if cmd in self.commands:
            if cmd in self.commands_with_args:
                # Command expects an argument
                arg = args[0] if args else ""
                debug_log(f"Executing command '{cmd}' with arg '{arg}'")
                self.commands[cmd](arg)
            else:
                # Command doesn't take arguments
                debug_log(f"Executing command '{cmd}' with no args")
                self.commands[cmd]()
        else:
            debug_log(f"Unknown command: '{cmd}'")
            self.handle_unknown_command(command)
    
    def show_help(self):
        """Display help information"""
        help_text = """
        [bold]Available Commands:[/bold]
        - [cyan]help[/cyan]: Display this help message
        - [cyan]ls[/cyan]: List files and directories
        - [cyan]cd [directory][/cyan]: Change to specified directory
        - [cyan]cat [file][/cyan]: Read the contents of a file
        - [cyan]map[/cyan]: Show available locations
        - [cyan]inventory/inv[/cyan]: Show collected items
        - [cyan]take [item][/cyan]: Add an item to your inventory
        - [cyan]drop [item][/cyan]: Remove an item from your inventory
        - [cyan]use [item][/cyan]: Use an item from your inventory
        - [cyan]examine [item][/cyan]: Examine an item in detail
        - [cyan]talk [npc][/cyan]: Talk to an NPC
        - [cyan]attack [enemy][/cyan]: Attack an enemy
        - [cyan]look[/cyan]: Look around the current location
        - [cyan]stats[/cyan]: Display your character's stats
        """
        self.console.print(Panel(help_text, title="Help"))
    
    def display_location(self):
        """Display information about the current location"""
        room_id = self.player.current_room
        room = self.world.get_room(room_id)
        
        if not room:
            self.console.print("[bold red]Error: Invalid room![/bold red]")
            return
        
        # Mark room as visited
        self.world.set_room_visited(room_id)
        
        # Get room information
        title = Text(f"Location: {room_id}", style="bold white on dark_blue")
        description = Text(room.get("description", "No description available."))
        
        # Get exits
        exits = self.world.get_exits(room_id)
        exits_str = "Exits: " + ", ".join(exits) if exits else "No visible exits."
        
        # Create panel content
        panel_content = f"{description}\n\n{exits_str}"
        panel = Panel(panel_content, title=title)
        
        self.console.print(panel)
    
    def get_formatted_item_description(self, item):
        """Format item description to show what it does in parentheses"""
        if not item:
            return "No description available"
            
        # Get base description (try different fields with fallbacks)
        base_desc = (
            item.get("short_description") or 
            item.get("description", "").split(".")[0] or  # Take first sentence if multiple
            item.get("name") or 
            "Unknown item"
        )
        
        # Determine item effect based on type and properties
        effect = ""
        
        # Healing items
        if "on_use" in item and "heal" in item["on_use"]:
            effect = f"+{item['on_use']['heal']} Health"
        
        # Damage-dealing items
        elif "on_use" in item and "damage" in item["on_use"]:
            effect = f"+{item['on_use']['damage']} Damage"
        
        # Status effect items
        elif "on_use" in item and "status_effect" in item["on_use"]:
            effect_name = item["on_use"]["status_effect"].get("name", "Effect")
            effect = f"Status: {effect_name}"
        
        # Weapons
        elif item.get("type") == "weapon" or "weapon" in str(item.get("type", "")):
            bonus = item.get("bonus_total_damage", 0)
            if bonus > 0:
                effect = f"+{bonus} Damage"
        
        # Upgrade items
        elif "effects" in item:
            effects = []
            if "permanent_health" in item["effects"]:
                effects.append(f"+{item['effects']['permanent_health']} Health")
            if "permanent_damage" in item["effects"]:
                effects.append(f"+{item['effects']['permanent_damage']} Damage")
            if effects:
                effect = "Perm: " + "/".join(effects)
        
        # Key items
        elif item.get("type") == "key" or "unlocks" in item:
            effect = "Unlocks areas"
            
        # Add the effect in parentheses if we found one
        if effect:
            return f"{base_desc} ({effect})"
        else:
            return base_desc
    
    def list_directory(self):
        """Show files (items) and directories (exits) in the current location"""
        room_id = self.player.current_room
        
        # Show directories (exits)
        exits = self.world.get_exits(room_id)
        if exits:
            self.console.print("[bold blue]Directories:[/bold blue]")
            for exit_dir in exits:
                room_state = self.world.get_room_state(exit_dir)
                if room_state.get("locked", False):
                    self.console.print(f"  [bold blue]{exit_dir}/[/bold blue] [red](Locked)[/red]")
                else:
                    self.console.print(f"  [bold blue]{exit_dir}/[/bold blue]")
        
        # Show files (items)
        items = self.world.get_items_in_room(room_id) or []  # Use empty list if None is returned
        if items:
            self.console.print("[bold green]Files:[/bold green]")
            for item_id in items:
                item = self.world.get_item(item_id)
                description = self.get_formatted_item_description(item)
                self.console.print(f"  [green]{item_id}[/green] - {description}")
        
        # Show NPCs
        npcs = self.world.get_npcs_in_room(room_id) or []  # Use empty list if None is returned
        if npcs:
            self.console.print("[bold yellow]Processes:[/bold yellow]")
            for npc_id in npcs:
                npc = self.world.get_npc(npc_id)
                if npc:  # Make sure NPC data exists
                    # Try multiple fields for description, with fallbacks
                    description = (
                        npc.get("short_description") or 
                        npc.get("description") or 
                        npc.get("name") or 
                        "No description available"
                    )
                    self.console.print(f"  [yellow]{npc_id}[/yellow] - {description}")
        
        # Show enemies
        enemies = self.world.get_enemies_in_room(room_id) or []  # Use empty list if None is returned
        if enemies:
            self.console.print("[bold red]Corrupted Entities:[/bold red]")
            for enemy_id in enemies:
                enemy = self.world.get_enemy(enemy_id)
                if enemy:  # Make sure enemy data exists
                    # Format enemy with health/damage
                    name = enemy.get("name", enemy_id)
                    health = enemy.get("health", "??")
                    damage = enemy.get("damage", "??")
                    self.console.print(f"  [red]{enemy_id}[/red] - {name} (HP: {health}, DMG: {damage})")
                else:
                    # Enemy data couldn't be found, try checking rooms data
                    self.console.print(f"  [red]{enemy_id}[/red] - Unknown Enemy")
            # For debugging
            self.console.print(f"[dim]Debug: Found {len(enemies)} enemies in room {room_id}[/dim]")
        
        if not (exits or items or npcs or enemies):
            self.console.print("The directory is empty.")
    
    def change_directory(self, directory):
        """Change to a different directory (room)"""
        if not directory:
            debug_log("cd called with no directory specified")
            self.console.print(f"Current directory: [bold]{self.player.current_room}[/bold]")
            return
        
        current_room = self.player.current_room
        debug_log(f"Player attempting to move from {current_room} to {directory}")
        
        # Check if we can move to the destination
        can_move, reason = self.world.can_move_to(current_room, directory)
        debug_log(f"Can move to {directory}: {can_move}, reason: {reason}")
        
        # If room is hidden, it can't be accessed directly
        room_state = self.world.get_room_state(directory)
        if room_state.get("hidden", False):
            debug_log(f"Attempt to access hidden room {directory} - access denied")
            self.console.print(f"[bold red]That path doesn't appear to exist.[/bold red]")
            return
        
        # If room is locked, check if player has the right key
        if not can_move and "locked" in reason.lower():
            room_state = self.world.get_room_state(directory)
            key_required = room_state.get("key_required")
            debug_log(f"Room {directory} is locked, key required: {key_required}")
            
            # Automatically use key if player has it
            if key_required and self.player.has_item(key_required):
                debug_log(f"Player has the required key: {key_required}")
                key_item = self.player.get_item_from_inventory(key_required)
                
                # Check if key has unlocks data (new format)
                if "unlocks" in key_item and directory in key_item["unlocks"]:
                    debug_log(f"Using key {key_required} to unlock {directory} (new format)")
                    self.world.unlock_room(directory)
                    self.console.print(f"[yellow]You automatically use {key_required} to unlock {directory}.[/yellow]")
                    can_move = True
                    reason = None
                # Check if the key is usable (old format)
                elif key_item.get("usable", False):
                    debug_log(f"Using key {key_required} to unlock {directory} (old format)")
                    self.world.unlock_room(directory)
                    self.console.print(f"[yellow]You automatically use {key_required} to unlock {directory}.[/yellow]")
                    can_move = True
                    reason = None
        
        if not can_move:
            debug_log(f"Movement denied: {reason}")
            self.console.print(f"[bold red]{reason}[/bold red]")
            return
        
        # Move the player
        debug_log(f"Moving player from {current_room} to {directory}")
        self.player.move_to(directory)
        self.console.print(f"Changed to [bold]{directory}[/bold]")
        debug_log(f"Successfully moved player to {directory}")
        
        # Display the new location
        self.display_location()
        
        # Check for enemies in the new room
        debug_log(f"Checking for enemies after moving to {directory}")
        self.check_for_enemies()
    
    def read_file(self, filename):
        """Read the contents of a file (item)"""
        if not filename:
            self.console.print("[bold red]No file specified. Use 'cat [filename]'[/bold red]")
            return
        
        # Check if file is in the current room
        current_room = self.player.current_room
        items_in_room = self.world.get_items_in_room(current_room)
        
        if filename in items_in_room:
            # Item is in the room
            item = self.world.get_item(filename)
            if item:
                content = item.get("content", "This file appears to be empty or corrupted.")
                self.console.print(Panel(content, title=f"[bold]{filename}[/bold]"))
                
                # Execute any special effects defined for this item
                if "on_read" in item:
                    self.execute_effect(item["on_read"])
            else:
                self.console.print(f"[bold red]Error: Could not read {filename}[/bold red]")
        elif self.player.has_item(filename):
            # Item is in the player's inventory
            item = self.player.get_item_from_inventory(filename)
            if item:
                content = item.get("content", "This file appears to be empty or corrupted.")
                self.console.print(Panel(content, title=f"[bold]{filename}[/bold]"))
                
                # Execute any special effects defined for this item
                if "on_read" in item:
                    self.execute_effect(item["on_read"])
            else:
                self.console.print(f"[bold red]Error: Could not read {filename}[/bold red]")
        else:
            self.console.print(f"[bold red]Cannot find {filename} in this directory or your inventory.[/bold red]")
    
    def take_item(self, item_id):
        """Pick up an item and add it to inventory"""
        if not item_id:
            debug_log("take command called with no item specified")
            self.console.print("[bold red]No item specified. Use 'take [item]'[/bold red]")
            return
        
        debug_log(f"Player attempting to take item: {item_id}")
        current_room = self.player.current_room
        items_in_room = self.world.get_items_in_room(current_room)
        
        if item_id not in items_in_room:
            debug_log(f"Item {item_id} not found in room {current_room}")
            self.console.print(f"[bold red]Cannot find {item_id} in this directory.[/bold red]")
            return
        
        # Get item data
        item = self.world.get_item(item_id)
        if not item:
            debug_log(f"Error: Item data not found for {item_id}")
            self.console.print(f"[bold red]Error: Item data not found for {item_id}[/bold red]")
            return
        
        # Check if item is takeable
        if not item.get("takeable", True):
            debug_log(f"Item {item_id} is not takeable")
            self.console.print(f"[bold red]You cannot take {item_id}.[/bold red]")
            return
        
        # Add to inventory and remove from room
        success = self.player.add_to_inventory(item_id, item)
        if success:
            debug_log(f"Player took item {item_id} from room {current_room}")
            self.world.remove_item_from_room(item_id)
            self.console.print(f"Added [green]{item_id}[/green] to your inventory.")
            
            # Execute any special effects defined for taking this item
            if "on_take" in item:
                debug_log(f"Executing on_take effect for {item_id}")
                self.execute_effect(item["on_take"])
        else:
            debug_log(f"Failed to add {item_id} to inventory")
            self.console.print(f"[bold red]Could not add {item_id} to inventory.[/bold red]")
    
    def drop_item(self, item_id):
        """Drop an item from inventory into the current room"""
        if not item_id:
            self.console.print("[bold red]No item specified. Use 'drop [item]'[/bold red]")
            return
        
        if not self.player.has_item(item_id):
            self.console.print(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return
        
        # Get item data
        item = self.player.get_item_from_inventory(item_id)
        
        # Check if item is droppable
        if item.get("droppable", True) == False:
            self.console.print(f"[bold red]You cannot drop {item_id}. It's too important.[/bold red]")
            return
        
        # Remove from inventory and add to room
        success = self.player.remove_from_inventory(item_id)
        if success:
            current_room = self.player.current_room
            self.world.add_item_to_room(item_id, current_room)
            self.console.print(f"Dropped [green]{item_id}[/green] in the current directory.")
            
            # Execute any special effects defined for dropping this item
            if "on_drop" in item:
                self.execute_effect(item["on_drop"])
        else:
            self.console.print(f"[bold red]Could not drop {item_id}.[/bold red]")
    
    def use_item(self, item_id):
        """Use an item from inventory"""
        if not item_id:
            debug_log("use command called with no item specified")
            self.console.print("[bold red]No item specified. Use 'use [item]'[/bold red]")
            return
        
        debug_log(f"Player attempting to use item: {item_id}")
        
        if not self.player.has_item(item_id):
            debug_log(f"Player doesn't have item {item_id} in inventory")
            self.console.print(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return
        
        # Get item data
        item = self.player.get_item_from_inventory(item_id)
        
        # Get the item type if it exists
        item_type = item.get("type")
        debug_log(f"Using item {item_id} of type {item_type}")
        
        # Check if item is usable or is a weapon (weapons should always be usable)
        is_weapon = item_type == "weapon" or "weapon" in str(item_type) if item_type else False
        if not (item.get("usable", False) or is_weapon):
            debug_log(f"Item {item_id} is not usable")
            self.console.print(f"[bold red]You cannot use {item_id}.[/bold red]")
            return
            
        # Check class restrictions
        if not self.player.can_use_item(item):
            class_restriction = item.get("class_restriction", "")
            if isinstance(class_restriction, list):
                class_restriction = " or ".join(class_restriction)
            debug_log(f"Item {item_id} has class restriction: {class_restriction}, player is: {self.player.player_class}")
            self.console.print(f"[bold red]This item can only be used by {class_restriction} class.[/bold red]")
            return
        
        # Process item based on its type
        if item_type == "key":
            debug_log(f"Handling key item: {item_id}")
            self._handle_key_item(item_id, item)
        elif is_weapon:
            debug_log(f"Handling weapon item: {item_id}")
            self._handle_weapon_item(item_id, item)
        elif item_type == "lore":
            debug_log(f"Handling lore item: {item_id}")
            self._handle_lore_item(item_id, item)
        elif item_type == "consumable" or "heal" in item.get("on_use", {}):
            debug_log(f"Handling consumable item: {item_id}")
            self._handle_consumable_item(item_id, item)
        elif "upgrade" in item_type if item_type else False:
            debug_log(f"Handling upgrade item: {item_id}")
            self._handle_upgrade_item(item_id, item)
        elif "spell" in item_type if item_type else False:
            debug_log(f"Handling spell item: {item_id}")
            self._handle_spell_item(item_id, item)
        else:
            # Execute generic on_use effect for other items
            if "on_use" in item:
                debug_log(f"Executing generic on_use effect for item: {item_id}")
                self.execute_effect(item["on_use"])
                self.console.print(f"You used [green]{item_id}[/green].")
            else:
                debug_log(f"Item {item_id} has no on_use effect")
                self.console.print(f"Nothing happens when you try to use {item_id}.")
        
        # Check if item is consumed on use
        if item.get("consumed_on_use", False):
            debug_log(f"Item {item_id} was consumed on use")
            self.player.remove_from_inventory(item_id)
            self.console.print(f"The [green]{item_id}[/green] was consumed.")
    
    def _handle_key_item(self, item_id, item):
        """Handle the use of a key item"""
        # Get rooms this key can unlock
        unlocks = item.get("unlocks", [])
        if not unlocks:
            self.console.print(f"[yellow]This key doesn't seem to unlock anything here.[/yellow]")
            return
        
        # Get current room and its exits
        current_room = self.player.current_room
        exits = self.world.get_exits(current_room)
        
        # Check if any locked adjacent room can be unlocked by this key
        unlocked_something = False
        
        for exit_room in exits:
            room_state = self.world.get_room_state(exit_room)
            if room_state.get("locked", False) and exit_room in unlocks:
                self.world.unlock_room(exit_room)
                self.console.print(f"[green]You unlocked access to {exit_room}![/green]")
                unlocked_something = True
        
        if not unlocked_something:
            self.console.print(f"[yellow]There's nothing to unlock with {item_id} here.[/yellow]")
    
    def _handle_weapon_item(self, item_id, item):
        """Handle equipping a weapon"""
        # Get old weapon info before equipping the new one
        old_weapon_id = self.player.equipped_weapon
        old_damage = self.player.calculate_damage()
        
        # Equip the weapon - updated for new Player implementation
        self.player.equip_weapon(item_id)
        self.console.print(f"[green]You equipped {item_id}.[/green]")
        
        # Remove the old weapon from inventory if it's different from the new one
        if old_weapon_id and old_weapon_id != item_id and old_weapon_id in self.player.inventory:
            self.player.remove_from_inventory(old_weapon_id)
            self.console.print(f"[yellow]Your old weapon ({old_weapon_id}) was removed from inventory.[/yellow]")
        
        # Display the weapon's effects and new total damage
        new_damage = self.player.calculate_damage()
        damage_change = new_damage - old_damage
        
        if damage_change > 0:
            self.console.print(f"[green]Your total damage increased by {damage_change} (from {old_damage} to {new_damage}).[/green]")
        elif damage_change < 0:
            self.console.print(f"[red]Your total damage decreased by {abs(damage_change)} (from {old_damage} to {new_damage}).[/red]")
        else:
            self.console.print(f"[yellow]Your total damage remains at {new_damage}.[/yellow]")
    
    def _handle_lore_item(self, item_id, item):
        """Handle using a lore item"""
        content = item.get("content", "")
        if content:
            self.console.print(Panel(content, title=f"[bold]{item_id}[/bold]"))
        else:
            self.console.print(f"[italic]{item.get('description', 'No information available.')}[/italic]")
    
    def _handle_consumable_item(self, item_id, item):
        """Handle the use of a consumable item"""
        # Check for healing effect
        if "on_use" in item and "heal" in item["on_use"]:
            heal_amount = item["on_use"]["heal"]
            old_health = self.player.health
            self.player.heal(heal_amount)
            new_health = self.player.health
            actual_heal = new_health - old_health
            debug_log(f"Player used healing item {item_id} for {heal_amount} potential healing. Actual: {actual_heal} ({old_health} -> {new_health})")
            self.console.print(f"[green]You used {item_id} and recovered {actual_heal} health![/green]")
            
            # Execute additional effects if present
            if "on_use" in item and isinstance(item["on_use"], dict):
                for effect_key, effect_value in item["on_use"].items():
                    if effect_key != "heal":  # Skip the heal effect we already processed
                        debug_log(f"Processing additional effect: {effect_key} from consumable {item_id}")
                        # Process status effect
                        if effect_key == "status_effect":
                            effect_data = item["on_use"]["status_effect"]
                            effect_id = effect_data.get("id", item_id + "_effect")
                            effect_name = effect_data.get("name", "Unknown Effect")
                            effect_duration = effect_data.get("duration", 3)
                            debug_log(f"Applying status effect {effect_id} ({effect_name}) for {effect_duration} turns")
                            self.player.add_status_effect(effect_id, effect_data, effect_duration)
                            self.console.print(f"[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]")
        else:
            debug_log(f"Used consumable {item_id} with no healing effect")
            self.console.print(f"You used {item_id}.")
            
            # If it has other effects, process them
            if "on_use" in item:
                debug_log(f"Processing on_use effects for consumable {item_id}")
                self.execute_effect(item["on_use"])
    
    def _handle_upgrade_item(self, item_id, item):
        """Handle using an upgrade item"""
        # Process permanent stat boosts
        effects = item.get("effects", {})
        
        # Health boosts
        if "permanent_health" in effects:
            amount = effects["permanent_health"]
            new_max = self.player.increase_max_health(amount)
            self.console.print(f"[green]Your maximum health permanently increased by {amount} to {new_max}![/green]")
        
        # Damage boosts
        if "permanent_damage" in effects:
            amount = effects["permanent_damage"]
            new_damage = self.player.increase_damage(amount)
            self.console.print(f"[green]Your base damage permanently increased by {amount} to {new_damage}![/green]")
        
        # Process on_use effects if any
        if "on_use" in item:
            self.execute_effect(item["on_use"])
    
    def _handle_spell_item(self, item_id, item):
        """Handle using a spell item"""
        # Learn the spell
        if self.player.learn_spell(item):
            spell_name = item.get("name", "Unknown Spell")
            self.console.print(f"[green]You learned the {spell_name} spell![/green]")
            
            # Apply any immediate status effects if defined
            if "status_effect" in item:
                effect_data = item["status_effect"]
                effect_id = effect_data.get("id", item_id + "_effect")
                effect_name = effect_data.get("name", spell_name + " Effect")
                effect_duration = effect_data.get("duration", 3)  # Default 3 turns
                
                # Add the status effect
                self.player.add_status_effect(effect_id, effect_data, effect_duration)
                self.console.print(f"[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]")
        else:
            self.console.print(f"[red]You don't have the ability to learn this spell.[/red]")
            
    def examine_item(self, item_id):
        """Examine an item in detail"""
        if not item_id:
            self.console.print("[bold red]No item specified. Use 'examine [item]'[/bold red]")
            return
        
        # Check if item is in inventory
        if self.player.has_item(item_id):
            item = self.player.get_item_from_inventory(item_id)
            source = "inventory"
        else:
            # Check if item is in the current room
            current_room = self.player.current_room
            items_in_room = self.world.get_items_in_room(current_room)
            
            if item_id in items_in_room:
                item = self.world.get_item(item_id)
                source = "room"
            else:
                self.console.print(f"[bold red]Cannot find {item_id} in this directory or your inventory.[/bold red]")
                return
        
        # Display item details
        title = f"Examining: {item_id}"
        description = item.get("description", "No detailed description available.")
        
        # Add additional details if available
        details = []
        if item.get("usable", False):
            details.append("[green]This item can be used.[/green]")
        if item.get("consumed_on_use", False):
            details.append("[yellow]This item will be consumed when used.[/yellow]")
        if not item.get("takeable", True):
            details.append("[red]This item cannot be taken.[/red]")
        if not item.get("droppable", True):
            details.append("[red]This item cannot be dropped once taken.[/red]")
        
        # Combine all information
        content = f"{description}\n"
        if details:
            content += "\n" + "\n".join(details)
        
        self.console.print(Panel(content, title=f"[bold]{title}[/bold]"))
        
        # Execute any special effects defined for examining this item
        if "on_examine" in item:
            self.execute_effect(item["on_examine"])
    
    def talk_to_npc(self, npc_id):
        """Talk to an NPC in the current room"""
        if not npc_id:
            self.console.print("[bold red]No NPC specified. Use 'talk [npc]'[/bold red]")
            return
        
        current_room = self.player.current_room
        npcs_in_room = self.world.get_npcs_in_room(current_room)
        
        if npc_id not in npcs_in_room:
            self.console.print(f"[bold red]Cannot find {npc_id} in this directory.[/bold red]")
            return
        
        # Get NPC data
        npc = self.world.get_npc(npc_id)
        if not npc:
            self.console.print(f"[bold red]Error: NPC data not found for {npc_id}[/bold red]")
            return
        
        # Get dialogue options
        dialogues = npc.get("dialogues", [])
        if not dialogues:
            self.console.print(f"[yellow]{npc_id} has nothing to say.[/yellow]")
            return
        
        # Select a dialogue based on conditions or randomly
        # For now, just pick a random one
        dialogue = random.choice(dialogues)
        
        # Display the dialogue
        self.console.print(f"[bold yellow]{npc_id}:[/bold yellow] {dialogue}")
        
        # Execute any special effects defined for talking to this NPC
        if "on_talk" in npc:
            self.execute_effect(npc["on_talk"])
    
    def attack_enemy(self, enemy_id):
        """Attack an enemy in the current room"""
        if not enemy_id:
            self.console.print("[bold red]No enemy specified. Use 'attack [enemy]'[/bold red]")
            return
        
        current_room = self.player.current_room
        enemies_in_room = self.world.get_enemies_in_room(current_room)
        
        if enemy_id not in enemies_in_room:
            self.console.print(f"[bold red]Cannot find {enemy_id} in this directory.[/bold red]")
            return
        
        # Get enemy data
        enemy = self.world.get_enemy(enemy_id)
        if not enemy:
            self.console.print(f"[bold red]Error: Enemy data not found for {enemy_id}[/bold red]")
            return
        
        # Start combat
        self.combat(enemy_id, enemy)
    
    def look_around(self):
        """Look around the current room for details"""
        current_room = self.player.current_room
        room = self.world.get_room(current_room)
        
        if not room:
            self.console.print("[bold red]Error: Invalid room![/bold red]")
            return
        
        # Get detailed description if available
        detailed_desc = room.get("detailed_description")
        if detailed_desc:
            self.console.print(f"[italic]{detailed_desc}[/italic]")
        else:
            self.console.print(f"[italic]{room.get('description', 'No description available.')}[/italic]")
        
        # List items, NPCs, and enemies in the room
        self.list_directory()
    
    def show_inventory(self):
        """Display the player's inventory"""
        items = self.player.get_inventory_items()
        
        if not items:
            self.console.print("[italic]Your inventory is empty.[/italic]")
            return
        
        self.console.print("[bold]Inventory:[/bold]")
        for item_id in items:
            item = self.player.get_item_from_inventory(item_id)
            if item is None:
                # Handle case where item might be in inventory but doesn't have proper data
                self.console.print(f"  [green]{item_id}[/green]")
                continue
                
            # Use the formatted description
            description = self.get_formatted_item_description(item)
            
            # Mark equipped weapon
            if item_id == self.player.equipped_weapon:
                self.console.print(f"  [green]{item_id}[/green] [cyan](Equipped)[/cyan] - {description}")
            else:
                self.console.print(f"  [green]{item_id}[/green] - {description}")
    
    def show_map(self):
        """Display a map of known locations"""
        # Get all rooms the player has visited
        visited_rooms = [room_id for room_id, state in self.world.room_states.items() 
                         if state.get("visited", False)]
        
        if not visited_rooms:
            self.console.print("[italic]Your map is empty. Explore to discover locations.[/italic]")
            return
        
        self.console.print("[bold]Known Locations:[/bold]")
        for room_id in visited_rooms:
            room = self.world.get_room(room_id)
            if room:
                # Mark current location
                if room_id == self.player.current_room:
                    self.console.print(f"  [bold cyan]> {room_id}[/bold cyan] - {room.get('description', 'No description available.')}")
                else:
                    self.console.print(f"  [blue]{room_id}[/blue] - {room.get('description', 'No description available.')}")
    
    def combat(self, enemy_id, enemy):
        """Handle combat with an enemy"""
        enemy_name = enemy.get("name", enemy_id)
        enemy_health = enemy.get("health", 50)
        enemy_damage = enemy.get("damage", 10)
        is_boss = enemy.get("is_boss", False)
        
        debug_log(f"Starting combat with {enemy_name} (HP: {enemy_health}, DMG: {enemy_damage}, Boss: {is_boss})")
        
        # Enemy damage reduction (for special attacks that reduce enemy damage)
        enemy_damage_reduction = 0
        
        # Enemy status effects tracking
        enemy_status_effects = {}  # Format: {effect_id: {'duration': turns, 'effect': {effect_data}}}
        
        self.console.print(f"[bold red]Combat initiated with {enemy_name}![/bold red]")
        
        # Display enemy dialogue if available
        if "dialogue" in enemy:
            debug_log(f"Enemy {enemy_id} says: {enemy['dialogue']}")
            self.console.print(f"[bold red]{enemy_name}:[/bold red] {enemy['dialogue']}")
        
        # Combat loop
        combat_round = 0
        player_acted = False  # Initialize player_acted before use
        
        while enemy_health > 0 and self.player.is_alive():
            combat_round += 1
            debug_log(f"Combat round {combat_round} with {enemy_name}")
            player_acted = False  # Reset for this round
            
            # Display combat status
            self.console.print(f"\n[bold]Your Health:[/bold] {self.player.health}/{self.player.max_health}")
            self.console.print(f"[bold red]{enemy_name}'s Health:[/bold red] {enemy_health}")
            
            # Display active status effects
            active_effects = self.player.get_active_status_effects()
            if active_effects:
                debug_log(f"Player has {len(active_effects)} active status effects")
                self.console.print("[bold magenta]Active Status Effects:[/bold magenta]")
                for effect in active_effects:
                    self.console.print(f"  [magenta]{effect['name']} ({effect['duration']} turns)[/magenta]")
                    debug_log(f"Active effect: {effect['name']} ({effect['duration']} turns)")
            
            # PLAYER COMBAT ACTIONS IMPLEMENTATION
            # Get available attacks
            available_attacks = self.player.get_available_attacks()
            debug_log(f"Player has {len(available_attacks)} available attacks")
            
            # Show available attacks to player
            self.console.print("\n[bold]Available Actions:[/bold]")
            attack_keys = {}
            
            # Show player's base damage
            base_damage = self.player.calculate_damage()
            self.console.print(f"[bold]Base Attack Damage:[/bold] {base_damage}")
            
            # Add special attacks (starting from key 1)
            key_idx = 1
            for attack_id, attack_data in available_attacks.items():
                attack_name = attack_data.get("name", attack_id)
                bonus_damage = attack_data.get("bonus_damage", 0)
                cooldown = attack_data.get("cooldown", 0)
                on_cooldown = attack_data.get("on_cooldown", False)
                
                # Get attack description
                description = attack_data.get("description", "")
                healing = attack_data.get("healing", 0)
                enemy_dmg_reduction = attack_data.get("enemy_damage_reduction", 0)
                
                # Calculate total damage
                total_damage = base_damage + bonus_damage
                
                # Build description string
                effect_desc = []
                if bonus_damage > 0:
                    effect_desc.append(f"{base_damage} + {bonus_damage} = {total_damage} dmg")
                else:
                    effect_desc.append(f"{base_damage} dmg")
                if healing > 0:
                    effect_desc.append(f"Heal {healing} HP")
                if enemy_dmg_reduction > 0:
                    effect_desc.append(f"Reduce enemy dmg by {int(enemy_dmg_reduction * 100)}%")
                if cooldown > 0:
                    effect_desc.append(f"CD: {cooldown} turns")
                
                effects = ", ".join(effect_desc)
                
                if on_cooldown:
                    self.console.print(f"{key_idx}: [gray]{attack_name} ({effects}) - On Cooldown[/gray]")
                else:
                    self.console.print(f"{key_idx}: [cyan]{attack_name}[/cyan] - {description} ({effects})")
                    attack_keys[str(key_idx)] = attack_id
                key_idx += 1
            
            # Add usable items to the action list
            self.console.print("\n[bold]Items:[/bold]")
            usable_items = []
            
            # Get all usable items from player inventory
            for item_id in self.player.get_inventory_items():
                item = self.player.get_item_from_inventory(item_id)
                if item and item.get("usable", False) and "combat_usable" in item.get("tags", []):
                    usable_items.append((item_id, item))
            
            # Display usable items
            if usable_items:
                for i, (item_id, item_data) in enumerate(usable_items):
                    item_key = str(key_idx)
                    item_name = item_data.get("name", item_id)
                    description = self.get_formatted_item_description(item_data)
                    self.console.print(f"{key_idx}: [yellow]{item_name}[/yellow] - {description}")
                    attack_keys[item_key] = f"item:{item_id}"  # Prefix with "item:" to distinguish from attacks
                    key_idx += 1
            else:
                self.console.print("  No usable items available")
            
            # Get player choice - keep prompting until valid input
            choice = None
            while choice not in attack_keys:
                self.console.print("\nChoose your action (press the number): ", end="")
                choice = readchar.readchar()
                self.console.print(choice)
                
                if choice not in attack_keys:
                    self.console.print("[yellow]Invalid choice. Please select a valid option.[/yellow]")
                    debug_log(f"Player made invalid combat choice: '{choice}'")
            
            # Process player attack or item use
            action_id = attack_keys[choice]
            debug_log(f"Player chose action: {action_id}")
            player_acted = True
            
            # Check if this is an item or an attack
            if action_id.startswith("item:"):
                # Handle item use
                item_id = action_id.split(":")[1]
                debug_log(f"Player is using item {item_id} in combat")
                item = self.player.get_item_from_inventory(item_id)
                
                # Use the item
                self._handle_consumable_item(item_id, item)
                
                # If item is consumed on use, remove it
                if item.get("consumed_on_use", False):
                    self.player.remove_from_inventory(item_id)
                    self.console.print(f"[yellow]You used up the {item_id}.[/yellow]")
            else:
                # Use the selected attack
                attack_result = self.player.perform_attack(action_id)
                damage = attack_result["damage"]
                
                # Apply damage to enemy
                enemy_health -= damage
                
                # Display message
                self.console.print(f"[green]{attack_result['message']}[/green]")
                
                # Apply enemy damage reduction if applicable
                if attack_result.get("enemy_damage_reduction", 0) > 0:
                    enemy_damage_reduction = attack_result["enemy_damage_reduction"]
                    debug_log(f"Set enemy damage reduction to {enemy_damage_reduction}")
            
            # Check if we defeated the enemy
            if enemy_health <= 0:
                debug_log(f"Enemy {enemy_name} was defeated!")
                self.console.print(f"[bold green]You defeated {enemy_name}![/bold green]")
                
                # Add loot/rewards here if desired
                
                # Find and remove the actual enemy ID from the room
                # Try using both the original ID and looking up by name
                if not self.world.remove_enemy_from_room(enemy_id):
                    # If original ID removal failed, try to find by name
                    debug_log(f"Failed to remove enemy {enemy_id}, trying to find by name: {enemy_name}")
                    
                    # Get the current room's enemies
                    current_room = self.player.current_room
                    enemies_in_room = self.world.get_enemies_in_room(current_room)
                    
                    # Find an enemy with the matching name
                    for room_enemy_id in enemies_in_room:
                        room_enemy = self.world.get_enemy(room_enemy_id)
                        if room_enemy and room_enemy.get("name") == enemy_name:
                            debug_log(f"Found enemy with matching name: {room_enemy_id}")
                            self.world.remove_enemy_from_room(room_enemy_id)
                            break
                break
            
            # If player didn't defeat the enemy, enemy attacks
            if enemy_health > 0:
                debug_log(f"Enemy {enemy_name} attacks player")
                # Calculate damage (apply reduction if player used a defensive move)
                damage = enemy_damage
                if enemy_damage_reduction > 0:
                    original_damage = damage
                    damage = int(damage * (1 - enemy_damage_reduction))
                    debug_log(f"Enemy damage reduced: {original_damage} -> {damage} ({enemy_damage_reduction*100}% reduction)")
                    # Reset reduction after it's been applied
                    enemy_damage_reduction = 0
                    self.console.print(f"[yellow]The enemy's attack is weakened![/yellow]")
                
                self.player.take_damage(damage)
                debug_log(f"Player took {damage} damage, health now: {self.player.health}/{self.player.max_health}")
                self.console.print(f"[bold red]{enemy_name} attacks you for {damage} damage![/bold red]")
                
                # Check if player is defeated
                if not self.player.is_alive():
                    debug_log("Player was defeated in combat")
                    self.game_over()
                    break
                    
                # Update cooldowns and status effects
                debug_log("Updating player cooldowns and status effects")
                # Update player cooldowns
                self.player.update_cooldowns()
                
                # Display any status effect expiration messages
                expiration_messages = self.player.update_status_effects()
                for message in expiration_messages:
                    debug_log(f"Status effect expired: {message}")
                    self.console.print(f"[magenta]{message}[/magenta]")
                
                # Wait for player to acknowledge their turn
                self.console.print("\nPress any key to continue...")
                readchar.readchar()
        
        # Combat ended - handle aftermath
        if enemy_health <= 0:
            debug_log(f"Combat ended: Enemy {enemy_name} was defeated")
        elif not self.player.is_alive():
            debug_log(f"Combat ended: Player was defeated by {enemy_name}")
        else:
            debug_log(f"Combat ended: Player escaped from {enemy_name}")
    
    def check_for_enemies(self):
        """Check for enemies in the current room and initiate combat if necessary"""
        current_room = self.player.current_room
        debug_log(f"Checking for enemies in room {current_room}")
        enemies = self.world.get_enemies_in_room(current_room)
        
        if enemies:
            debug_log(f"Found {len(enemies)} enemies in room {current_room}: {enemies}")
            # For simplicity, just fight the first enemy
            # In a more complex game, you might want to give the player more choice
            enemy_id = enemies[0]
            debug_log(f"Selected enemy {enemy_id} for potential combat")
            enemy = self.world.get_enemy(enemy_id)
            
            if enemy:
                debug_log(f"Retrieved enemy data for {enemy_id}: {enemy.get('name', 'Unknown')}")
                auto_attack = enemy.get("auto_attack", True)
                debug_log(f"Enemy {enemy_id} auto_attack setting = {auto_attack}")
                
                if auto_attack:
                    debug_log(f"Initiating auto-combat with enemy {enemy_id}")
                    self.console.print(f"[bold red]Warning: {enemy_id} detected![/bold red]")
                    self.combat(enemy_id, enemy)
                else:
                    debug_log(f"Enemy {enemy_id} does not auto-attack - combat will not start automatically")
            else:
                debug_log(f"ERROR: Enemy {enemy_id} data not found in enemies dictionary")
                debug_log(f"Available enemy IDs: {list(self.world.enemies.keys())}")
        else:
            debug_log(f"No enemies found in room {current_room} - no combat will occur")
    
    def execute_effect(self, effect):
        """Execute a special effect defined in YAML"""
        if isinstance(effect, str):
            # Just a message
            debug_log(f"Executing effect (message only): {effect}")
            self.console.print(f"[italic]{effect}[/italic]")
        elif isinstance(effect, dict):
            # Complex effect with multiple actions
            debug_log(f"Executing complex effect: {list(effect.keys())}")
            
            # Handle messages
            if "message" in effect:
                debug_log(f"Displaying effect message: {effect['message']}")
                self.console.print(f"[italic]{effect['message']}[/italic]")
            
            # Handle health changes
            if "heal" in effect:
                amount = effect["heal"]
                old_health = self.player.health
                self.player.heal(amount)
                new_health = self.player.health
                actual_heal = new_health - old_health
                debug_log(f"Effect healed player for {amount} requested HP, actual: {actual_heal} ({old_health} -> {new_health})")
                self.console.print(f"[green]You gained {actual_heal} health![/green]")
            
            if "damage" in effect:
                amount = effect["damage"]
                old_health = self.player.health
                self.player.take_damage(amount)
                new_health = self.player.health
                debug_log(f"Effect damaged player for {amount} HP ({old_health} -> {new_health})")
                self.console.print(f"[red]You took {amount} damage![/red]")
                
                # Check if player died
                if not self.player.is_alive():
                    debug_log("Player died from effect damage")
                    self.game_over()
            
            # Handle status effects
            if "add_status_effect" in effect:
                status_data = effect["add_status_effect"]
                effect_id = status_data.get("id", "effect_" + str(random.randint(1000, 9999)))
                effect_name = status_data.get("name", "Effect")
                effect_duration = status_data.get("duration", 3)
                
                debug_log(f"Adding status effect: {effect_name} (ID: {effect_id}) for {effect_duration} turns")
                if "damage_bonus" in status_data:
                    debug_log(f"Status effect provides {status_data['damage_bonus']} damage bonus")
                if "health_bonus" in status_data:
                    debug_log(f"Status effect provides {status_data['health_bonus']} health bonus")
                
                self.player.add_status_effect(effect_id, status_data, effect_duration)
                self.console.print(f"[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]")
            
            # Handle adding items
            if "add_item" in effect:
                item_id = effect["add_item"]
                debug_log(f"Effect adds item to inventory: {item_id}")
                item = self.world.get_item(item_id)
                if item:
                    self.player.add_to_inventory(item_id, item)
                    self.console.print(f"[green]You obtained {item_id}![/green]")
                else:
                    debug_log(f"WARNING: Effect tried to add non-existent item: {item_id}")
            
            # Handle removing items
            if "remove_item" in effect:
                item_id = effect["remove_item"]
                debug_log(f"Effect removes item from inventory: {item_id}")
                if self.player.has_item(item_id):
                    self.player.remove_from_inventory(item_id)
                    self.console.print(f"[yellow]You lost {item_id}![/yellow]")
                else:
                    debug_log(f"WARNING: Effect tried to remove item {item_id} but player doesn't have it")
            
            # Handle unlocking rooms
            if "unlock_room" in effect:
                room_id = effect["unlock_room"]
                debug_log(f"Effect unlocks room: {room_id}")
                self.world.unlock_room(room_id)
                self.console.print(f"[green]You've unlocked access to {room_id}![/green]")
            
            # Handle spawning enemies
            if "spawn_enemy" in effect:
                enemy_id = effect["spawn_enemy"]
                room_id = effect.get("in_room", self.player.current_room)
                debug_log(f"Effect spawns enemy {enemy_id} in room {room_id}")
                if self.world.get_enemy(enemy_id):
                    self.world.enemy_locations[enemy_id] = room_id
                    if room_id == self.player.current_room:
                        self.console.print(f"[bold red]{enemy_id} has appeared![/bold red]")
                        debug_log(f"Enemy {enemy_id} spawned in current room, checking for combat")
                        # Check if we should immediately start combat with this enemy
                        self.check_for_enemies()
                else:
                    debug_log(f"WARNING: Effect tried to spawn non-existent enemy: {enemy_id}")
            
    def game_over(self):
        """Handle game over state"""
        debug_log("Game over - player has been defeated")
        self.console.print("[bold red]YOU HAVE BEEN DELETED[/bold red]")
        self.console.print("[bold red]GAME OVER[/bold red]")
        # For now, just exit
        exit(0)
    
    def check_game_completion(self):
        """Check if the player has completed the game"""
        # This would be based on some condition in your game design
        # For example, defeating the final boss or collecting all key items
        if self.player.current_room == "core" and "daemon_overlord.sys" not in self.world.get_enemies_in_room("core"):
            if self.player.has_item("backup.bak"):
                self.win_game()
    
    def win_game(self):
        """Handle win state"""
        self.console.print("[bold green]Congratulations! You have defeated the Daemon Overlord and restored the filesystem![/bold green]")
        self.console.print("[bold green]You are granted the title of Master Sysadmin![/bold green]")
        self.console.print("\nBut somewhere in the digital void, a whisper suggests this might not be the end...")
        self.console.print("\n[bold]THANK YOU FOR PLAYING[/bold]")
        # For now, just exit
        exit(0)
    
    def handle_unknown_command(self, command):
        """Handle unknown commands gracefully"""
        # List of predefined responses
        responses = [
            "The system seems to glitch momentarily.",
            "A static noise fills the air, but nothing happens.",
            "The command echoes in the digital void, but produces no result.",
            "The Daemon Overlord's influence seems to block that command.",
            "The filesystem shudders slightly, but nothing changes.",
            "That command isn't recognized in this haunted system.",
            "The command dissipates into digital mist.",
            "Your request seems valid, but the corrupted system can't process it.",
            "A ghostly whisper suggests trying a different approach.",
            "The Helper Script would advise using standard commands instead."
        ]
        
        self.console.print(f"[italic]{random.choice(responses)}[/italic]")
        self.console.print("[yellow]Hint: Try using standard commands like 'ls', 'cd', 'cat', or type 'help'.[/yellow]")

    def show_player_stats(self):
        """Display detailed player stats"""
        from rich.table import Table
        
        # Create a table for player stats
        table = Table(title=f"Character Stats: {self.player.name}")
        
        # Add columns
        table.add_column("Stat", style="cyan")
        table.add_column("Value", style="green")
        
        # Basic stats
        table.add_row("Class", self.player.player_class.title())
        table.add_row("Health", f"{self.player.health}/{self.player.max_health}")
        
        # Simplified damage stats - just show total damage
        table.add_row("Total Damage", str(self.player.total_damage))
        
        if self.player.equipped_weapon:
            table.add_row("Equipped Weapon", self.player.inventory.get(self.player.equipped_weapon, {}).get("name", self.player.equipped_weapon))
        
        # Available attacks
        available_attacks = self.player.get_available_attacks()
        attack_list = []
        
        for attack_id, attack_data in available_attacks.items():
            attack_name = attack_data.get("name", attack_id)
            bonus_damage = attack_data.get("bonus_damage", 0)
            attack_list.append(f"{attack_name}: +{bonus_damage} damage")
        
        table.add_row("Available Attacks", "\n".join(attack_list) if attack_list else "None")
        
        # Show active status effects
        active_effects = self.player.get_active_status_effects()
        if active_effects:
            effect_list = []
            for effect in active_effects:
                effect_list.append(f"{effect['name']} ({effect['duration']} turns): {effect['description']}")
            table.add_row("Status Effects", "\n".join(effect_list))
        
        # Display the table
        self.console.print(table) 