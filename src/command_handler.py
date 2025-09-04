#!/usr/bin/env python3
import os
import random
import logging
from rich.text import Text
from src.combat import combat_system, CombatSession
from src.events import event_bus, EventType
from src.game_states import GameState
from utils.debug_tools import debug_log

logger = logging.getLogger(__name__)

class CommandHandler:
    """Handles processing of player commands"""
    
    def __init__(self, player, world, ui):
        """Initialize with player and world references"""
        debug_log("Initializing CommandHandler")
        self.player = player
        self.world = world
        self.ui = ui
        self.current_combat_session = None
        
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
            "equip": self.equip_weapon,
            "examine": self.examine_item,
            "talk": self.talk_to_npc,
            "attack": self.attack_enemy,
            "quit": self.quit_game,
            "exit": self.quit_game
        }
        
        # Specify which commands require arguments
        self.commands_with_args = {
            "cd", "cat", "take", "drop", "use", "equip", "examine", "talk", "attack"
        }
        
        debug_log(f"Registered {len(self.commands)} commands")
    
    def show_tutorial_hint(self, hint_type, item_name=None):
        """Show contextual tutorial hints based on player progress."""
        if self.player.tutorial_state.get("completed", False):
            return  # Tutorial already completed
        
        # Get the actual weapon name for dynamic hints
        weapon_name = item_name if item_name else "rusty_sword"  # fallback
            
        hints = {
            "welcome": "[bold cyan]Welcome to the Haunted Filesystem![/bold cyan]\nYou are a sysadmin spirit exploring a corrupted system. Type [yellow]'help'[/yellow] to see available commands, or [yellow]'ls'[/yellow] to examine your surroundings.",
            "first_look": "[yellow]Tip:[/yellow] Use [cyan]'ls'[/cyan] to list files and entities in your current directory. This will help you find items to pick up!",
            "found_weapon": f"[yellow]Tutorial:[/yellow] You found a weapon! Use [cyan]'take {weapon_name}'[/cyan] to pick it up.",
            "took_weapon": f"[green]Great![/green] You picked up your first item. Now use [cyan]'equip {weapon_name}'[/cyan] to equip it as your weapon.",
            "equipped_weapon": "[green]Excellent![/green] You've equipped your first weapon. You can now use [cyan]'attack [enemy]'[/cyan] in combat, or execute weapons like scripts (e.g., [cyan]'./protocol_shield'[/cyan]) during battle. Type [cyan]'inventory'[/cyan] to see all your items.",
            "completed": "[bold green]Tutorial Complete![/bold green] You've learned the basics. Explore the filesystem, defeat corrupted entities, and restore the system!"
        }
        
        if hint_type in hints:
            self.ui.update_output(f"[dim]{hints[hint_type]}[/dim]")
    
    def create_health_bar(self, current_health, max_health, color="white"):
        """Create an ASCII health bar with the specified color."""
        if max_health <= 0:
            return f"[{color}]░░░░░░░░░░░░░░░░░░░░[/{color}] (0%)"
        
        percentage = (current_health / max_health) * 100
        filled_blocks = int((current_health / max_health) * 20)  # 20 character bar
        empty_blocks = 20 - filled_blocks
        
        health_bar = "█" * filled_blocks + "░" * empty_blocks
        return f"[{color}]{health_bar}[/{color}] ({percentage:.0f}%)"
        
    def handle_command(self, command):
        """Process a command from the player"""
        cmd_parts = command.split()
        
        if not cmd_parts:
            debug_log("Empty command received")
            return
        
        # Handle combat commands specially
        if self.current_combat_session and self.current_combat_session.awaiting_action:
            self._handle_combat_command(command.strip())
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
        - [cyan]use [item][/cyan]: Use consumables (potions, scrolls)
        - [cyan]equip [weapon][/cyan]: Equip a weapon for combat
        - [cyan]examine [item][/cyan]: Examine an item in detail
        - [cyan]talk [npc][/cyan]: Talk to an NPC
        - [cyan]attack [enemy][/cyan]: Attack an enemy
        """
        help_content = f"[bold]Help[/bold]\n\n{help_text}"
        self.ui.update_output(help_content)
    
    def display_location(self):
        """Display information about the current location"""
        room_id = self.player.current_room
        room = self.world.get_room(room_id)
        
        if not room:
            self.ui.update_output("[bold red]Error: Invalid room![/bold red]")
            return
        
        # Mark room as visited
        self.world.set_room_visited(room_id)
        
        # Get room information
        title = Text(f"Location: {room_id}", style="bold white on dark_blue")
        description = Text(room.get("description", "No description available."))
        
        # Get exits
        exits = self.world.get_exits(room_id)
        exits_str = "Exits: " + ", ".join(exits) if exits else "No visible exits."
        
        # Create content with title
        location_content = f"[bold]{title}[/bold]\n\n{description}\n\n{exits_str}"
        
        self.ui.update_output(location_content)
    
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
        """Show files (items), processes (NPCs), and corrupted entities (enemies) in the current location"""
        room_id = self.player.current_room
        output = Text()
        has_content = False
        
        # Tutorial: first ls
        if not self.player.tutorial_state.get("first_ls", False):
            self.player.tutorial_state["first_ls"] = True
        
        # Show files (items)
        items = self.world.get_items_in_room(room_id) or []
        weapon_found = False
        if items:
            output.append("Files:\n", style="bold green")
            for item_id in items:
                item = self.world.get_item(item_id)
                description = self.get_formatted_item_description(item)
                output.append(f"  {item_id}", style="green")
                output.append(f" - {description}\n")
                
                # Tutorial: found weapon
                if not self.player.tutorial_state.get("found_weapon", False) and item and item.get("type") == "weapon":
                    weapon_found = True
                    
            has_content = True
        
        # Show NPCs
        npcs = self.world.get_npcs_in_room(room_id) or []
        if npcs:
            if has_content:
                output.append("\n")
            output.append("Processes:\n", style="bold yellow")
            for npc_id in npcs:
                npc = self.world.get_npc(npc_id)
                if npc:
                    description = (
                        npc.get("short_description") or 
                        npc.get("description") or 
                        npc.get("name") or 
                        "No description available"
                    )
                    output.append(f"  {npc_id}", style="yellow")
                    output.append(f" - {description}\n")
            has_content = True

        # Show enemies
        enemies = self.world.get_enemies_in_room(room_id) or []
        if enemies:
            if has_content:
                output.append("\n")
            output.append("Corrupted Entities:\n", style="bold red")
            for enemy_id in enemies:
                enemy = self.world.get_enemy(enemy_id)
                if enemy:
                    name = enemy.get("name", enemy_id)
                    health = enemy.get("health", "??")
                    damage = enemy.get("damage", "??")
                    output.append(f"  {enemy_id}", style="red")
                    output.append(f" - {name} (HP: {health}, DMG: {damage})\n")
                else:
                    output.append(f"  {enemy_id} - Unknown Enemy\n", style="red")
            has_content = True

        if not has_content:
            output.append("No files, processes, or entities found.")

        self.ui.update_output(output)
        
        # Tutorial: first time using ls (equivalent to old "first_look")
        if not self.player.tutorial_state.get("first_look", False):
            self.player.tutorial_state["first_look"] = True
            self.show_tutorial_hint("first_look")
        
        # Tutorial: show weapon hint after ls reveals weapon
        if weapon_found:
            self.player.tutorial_state["found_weapon"] = True
            # Find the actual weapon item to show in tutorial
            weapon_item_id = None
            for item_id in items:
                item = self.world.get_item(item_id)
                if item and item.get("type") == "weapon":
                    weapon_item_id = item_id
                    break
            self.show_tutorial_hint("found_weapon", weapon_item_id)
    
    def change_directory(self, directory):
        """Change to a different directory (room)"""
        if not directory:
            debug_log("cd called with no directory specified")
            self.ui.update_output(f"Current directory: [bold]{self.player.current_room}[/bold]")
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
            self.ui.update_output(f"[bold red]That path doesn't appear to exist.[/bold red]")
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
                    self.ui.update_output(f"[yellow]You automatically use {key_required} to unlock {directory}.[/yellow]")
                    can_move = True
                    reason = None
                # Check if the key is usable (old format)
                elif key_item.get("usable", False):
                    debug_log(f"Using key {key_required} to unlock {directory} (old format)")
                    self.world.unlock_room(directory)
                    self.ui.update_output(f"[yellow]You automatically use {key_required} to unlock {directory}.[/yellow]")
                    can_move = True
                    reason = None
        
        if not can_move:
            debug_log(f"Movement denied: {reason}")
            self.ui.update_output(f"[bold red]{reason}[/bold red]")
            return
        
        # Move the player
        debug_log(f"Moving player from {current_room} to {directory}")
        self.player.move_to(directory)
        self.ui.update_output(f"Changed to [bold]{directory}[/bold]")
        debug_log(f"Successfully moved player to {directory}")
        
        # Emit room changed event
        event_bus.emit_event(
            EventType.PLAYER_MOVED,
            {"player": self.player, "from_room": current_room, "to_room": directory},
            "CommandHandler"
        )
        
        event_bus.emit_event(
            EventType.ROOM_ENTERED,
            {"room": directory, "player": self.player, "world": self.world},
            "CommandHandler"
        )
        
        # Display the new location
        self.display_location()
        
        # Check for enemies in the new room
        debug_log(f"Checking for enemies after moving to {directory}")
        self.check_for_enemies()
    
    def read_file(self, filename):
        """Read the contents of a file (item)"""
        if not filename:
            self.ui.update_output("[bold red]No file specified. Use 'cat [filename]'[/bold red]")
            return
        
        # Check if file is in the current room
        current_room = self.player.current_room
        items_in_room = self.world.get_items_in_room(current_room)
        
        if filename in items_in_room:
            # Item is in the room
            item = self.world.get_item(filename)
            if item:
                content = item.get("content", "This file appears to be empty or corrupted.")
                file_content = f"[bold]{filename}[/bold]\n\n{content}"
                self.ui.update_output(file_content)
                
                # Execute any special effects defined for this item
                if "on_read" in item:
                    self.execute_effect(item["on_read"])
            else:
                self.ui.update_output(f"[bold red]Error: Could not read {filename}[/bold red]")
        elif self.player.has_item(filename):
            # Item is in the player's inventory
            item = self.player.get_item_from_inventory(filename)
            if item:
                content = item.get("content", "This file appears to be empty or corrupted.")
                file_content = f"[bold]{filename}[/bold]\n\n{content}"
                self.ui.update_output(file_content)
                
                # Execute any special effects defined for this item
                if "on_read" in item:
                    self.execute_effect(item["on_read"])
            else:
                self.ui.update_output(f"[bold red]Error: Could not read {filename}[/bold red]")
        else:
            self.ui.update_output(f"[bold red]Cannot find {filename} in this directory or your inventory.[/bold red]")
    
    def take_item(self, item_id):
        """Pick up an item and add it to inventory"""
        if not item_id:
            debug_log("take command called with no item specified")
            self.ui.update_output("[bold red]No item specified. Use 'take [item]'[/bold red]")
            return
        
        debug_log(f"Player attempting to take item: {item_id}")
        current_room = self.player.current_room
        items_in_room = self.world.get_items_in_room(current_room)
        
        if item_id not in items_in_room:
            debug_log(f"Item {item_id} not found in room {current_room}")
            self.ui.update_output(f"[bold red]Cannot find {item_id} in this directory.[/bold red]")
            return
        
        # Get item data
        item = self.world.get_item(item_id)
        if not item:
            debug_log(f"Error: Item data not found for {item_id}")
            self.ui.update_output(f"[bold red]Error: Item data not found for {item_id}[/bold red]")
            return
        
        # Check if item is takeable
        if not item.get("takeable", True):
            debug_log(f"Item {item_id} is not takeable")
            self.ui.update_output(f"[bold red]You cannot take {item_id}.[/bold red]")
            return
        
        # Add to inventory and remove from room
        success = self.player.add_to_inventory(item_id, item)
        if success:
            debug_log(f"Player took item {item_id} from room {current_room}")
            self.world.remove_item_from_room(item_id)
            self.ui.update_output(f"Added [green]{item_id}[/green] to your inventory.")
            
            # Emit inventory changed event
            event_bus.emit_event(
                EventType.ITEM_TAKEN,
                {"item_id": item_id, "item": item, "player": self.player, "room": current_room},
                "CommandHandler"
            )
            
            event_bus.emit_event(
                EventType.PLAYER_INVENTORY_CHANGED,
                {"player": self.player},
                "CommandHandler"
            )
            
            # Execute any special effects defined for taking this item
            if "on_take" in item:
                debug_log(f"Executing on_take effect for {item_id}")
                self.execute_effect(item["on_take"])
            
            # Tutorial: took weapon
            if not self.player.tutorial_state.get("took_weapon", False) and item.get("type") == "weapon":
                self.player.tutorial_state["took_weapon"] = True
                self.show_tutorial_hint("took_weapon", item_id)
        else:
            debug_log(f"Failed to add {item_id} to inventory")
            self.ui.update_output(f"[bold red]Could not add {item_id} to inventory.[/bold red]")
    
    def drop_item(self, item_id):
        """Drop an item from inventory into the current room"""
        if not item_id:
            self.ui.update_output("[bold red]No item specified. Use 'drop [item]'[/bold red]")
            return
        
        if not self.player.has_item(item_id):
            self.ui.update_output(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return
        
        # Get item data
        item = self.player.get_item_from_inventory(item_id)
        
        # Check if item is droppable
        if item.get("droppable", True) == False:
            self.ui.update_output(f"[bold red]You cannot drop {item_id}. It's too important.[/bold red]")
            return
        
        # Remove from inventory and add to room
        success = self.player.remove_from_inventory(item_id)
        if success:
            current_room = self.player.current_room
            self.world.add_item_to_room(item_id, current_room)
            self.ui.update_output(f"Dropped [green]{item_id}[/green] in the current directory.")
            
            # Execute any special effects defined for dropping this item
            if "on_drop" in item:
                self.execute_effect(item["on_drop"])
        else:
            self.ui.update_output(f"[bold red]Could not drop {item_id}.[/bold red]")
    
    def use_item(self, item_id):
        """Use an item from inventory"""
        if not item_id:
            debug_log("use command called with no item specified")
            self.ui.update_output("[bold red]No item specified. Use 'use [item]'[/bold red]")
            return
        
        debug_log(f"Player attempting to use item: {item_id}")
        
        if not self.player.has_item(item_id):
            debug_log(f"Player doesn't have item {item_id} in inventory")
            self.ui.update_output(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return
        
        # Get item data
        item = self.player.get_item_from_inventory(item_id)
        
        # Get the item type if it exists
        item_type = item.get("type")
        debug_log(f"Using item {item_id} of type {item_type}")
        
        # Check if item is a weapon (weapons should be equipped, not used)
        is_weapon = item_type == "weapon" or "weapon" in str(item_type) if item_type else False
        if is_weapon:
            debug_log(f"Item {item_id} is a weapon, should be equipped instead of used")
            self.ui.update_output(f"[bold yellow]{item_id} is a weapon. Use 'equip {item_id}' to equip it.[/bold yellow]")
            return
            
        # Check if item is usable
        if not item.get("usable", False):
            debug_log(f"Item {item_id} is not usable")
            self.ui.update_output(f"[bold red]You cannot use {item_id}.[/bold red]")
            return
            
        # Check class restrictions
        if not self.player.can_use_item(item):
            class_restriction = item.get("class_restriction", "")
            if isinstance(class_restriction, list):
                class_restriction = " or ".join(class_restriction)
            debug_log(f"Item {item_id} has class restriction: {class_restriction}, player is: {self.player.player_class}")
            self.ui.update_output(f"[bold red]This item can only be used by {class_restriction} class.[/bold red]")
            return
        
        # Process item based on its type
        if item_type == "key":
            debug_log(f"Handling key item: {item_id}")
            self._handle_key_item(item_id, item)
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
                self.ui.update_output(f"You used [green]{item_id}[/green].")
            else:
                debug_log(f"Item {item_id} has no on_use effect")
                self.ui.update_output(f"Nothing happens when you try to use {item_id}.")
        
        # Check if item is consumed on use
        if item.get("consumed_on_use", False):
            debug_log(f"Item {item_id} was consumed on use")
            self.player.remove_from_inventory(item_id)
            self.ui.update_output(f"The [green]{item_id}[/green] was consumed.")
    
    def _handle_key_item(self, item_id, item):
        """Handle the use of a key item"""
        unlocks = item.get("unlocks")
        if not unlocks:
            self.ui.update_output(f"You examine [green]{item_id}[/green], but it doesn't seem to unlock anything here.")
            return
        
        # Check if the key unlocks a room in the current location
        current_room_id = self.player.current_room
        exits = self.world.get_exits(current_room_id)
        
        unlocked_something = False
        for room_to_unlock in unlocks:
            if room_to_unlock in exits:
                self.world.unlock_room(room_to_unlock)
                self.ui.update_output(f"[yellow]You hear a click. The path to {room_to_unlock} is now open.[/yellow]")
                unlocked_something = True
        
        if not unlocked_something:
            self.ui.update_output(f"You can't find a lock that [green]{item_id}[/green] fits here.")
    
    def _handle_weapon_item(self, item_id, item):
        """Handle equipping a weapon"""
        # Check if player can equip this weapon
        if not self.player.can_use_item(item):
            self.ui.update_output(f"[bold red]You cannot equip {item_id}.[/bold red]")
            return
        
        # Get old weapon info before equipping the new one
        old_weapon_id = self.player.equipped_weapon
        old_damage = self.player.calculate_damage()
        
        # Equip the weapon
        self.player.equip_weapon(item_id, item)
        self.ui.update_output(f"You have equipped [green]{item_id}[/green].")
        
        # Remove the old weapon from inventory if it's different from the new one
        if old_weapon_id and old_weapon_id != item_id and old_weapon_id in self.player.inventory:
            self.player.remove_from_inventory(old_weapon_id)
            self.ui.update_output(f"Your old weapon ({old_weapon_id}) was removed from inventory.")
        
        # Display the weapon's effects and new total damage
        new_damage = self.player.calculate_damage()
        damage_change = new_damage - old_damage
        
        if damage_change > 0:
            self.ui.update_output(f"[green]Your total damage increased by {damage_change} (from {old_damage} to {new_damage}).[/green]")
        elif damage_change < 0:
            self.ui.update_output(f"[red]Your total damage decreased by {abs(damage_change)} (from {old_damage} to {new_damage}).[/red]")
        else:
            self.ui.update_output(f"[yellow]Your total damage remains at {new_damage}.[/yellow]")
        
        # Tutorial: equipped weapon
        if not self.player.tutorial_state.get("equipped_weapon", False):
            self.player.tutorial_state["equipped_weapon"] = True
            self.show_tutorial_hint("equipped_weapon")
            # Mark tutorial as completed after equipping first weapon
            if not self.player.tutorial_state.get("completed", False):
                self.player.tutorial_state["completed"] = True
                self.show_tutorial_hint("completed")
    
    def _handle_lore_item(self, item_id, item):
        """Handle reading a lore item"""
        content = item.get("content", "This file appears to be empty or corrupted.")
        name = item.get("name", item_id)
        self.ui.update_output(Panel(content, title=f"[bold]{name}[/bold]"))
        if "on_read" in item:
            self.execute_effect(item["on_read"])

    def _handle_consumable_item(self, item_id, item):
        """Handle using a consumable item"""
        on_use_effects = item.get("on_use", {})
        item_name = item.get("name", item_id)
        
        # Process healing
        if "heal" in on_use_effects:
            heal_amount = on_use_effects["heal"]
            healed_for = self.player.heal(heal_amount)
            self.ui.update_output(f"You used [green]{item_name}[/green] and restored {healed_for} health.")
        else:
            self.ui.update_output(f"You used [green]{item_name}[/green].")

        # Process other effects
        for effect_key, effect_value in on_use_effects.items():
            if effect_key == "heal":
                continue  # Already handled

            debug_log(f"Processing additional effect: {effect_key} from consumable {item_id}")
            # Process status effect
            if effect_key == "status_effect":
                effect_data = effect_value
                effect_id = effect_data.get("id", item_id + "_effect")
                effect_name = effect_data.get("name", "Unknown Effect")
                effect_duration = effect_data.get("duration", 3)
                debug_log(f"Applying status effect {effect_id} ({effect_name}) for {effect_duration} turns")
                self.player.add_status_effect(effect_id, effect_data, effect_duration)
                self.ui.update_output(f"[magenta]You gained the '{effect_name}' effect for {effect_duration} turns![/magenta]")
    
    def _handle_upgrade_item(self, item_id, item):
        """Handle using an upgrade item"""
        # Process permanent stat boosts
        effects = item.get("effects", {})
        
        # Health boosts
        if "permanent_health" in effects:
            amount = effects["permanent_health"]
            new_max = self.player.increase_max_health(amount)
            self.ui.update_output(Panel(f"[green]Your maximum health permanently increased by {amount} to {new_max}![/green]", title="Character Improvement"))
        
        # Damage boosts
        if "permanent_damage" in effects:
            amount = effects["permanent_damage"]
            new_damage = self.player.increase_damage(amount)
            self.ui.update_output(Panel(f"[green]Your base damage permanently increased by {amount} to {new_damage}![/green]", title="Character Improvement"))
        
        # Process on_use effects if any
        if "on_use" in item:
            self.execute_effect(item["on_use"])
    
    def _handle_spell_item(self, item_id, item):
        """Handle using a spell item"""
        # Learn the spell
        if self.player.learn_spell(item):
            spell_name = item.get("name", "Unknown Spell")
            self.ui.update_output(Panel(f"[green]You learned the {spell_name} spell![/green]", title="Spell Learned"))
            
            # Apply any immediate status effects if defined
            if "status_effect" in item:
                effect_data = item["status_effect"]
                effect_id = effect_data.get("id", item_id + "_effect")
                effect_name = effect_data.get("name", spell_name + " Effect")
                effect_duration = effect_data.get("duration", 3)  # Default 3 turns
                
                # Add the status effect
                self.player.add_status_effect(effect_id, effect_data, effect_duration)
                self.ui.update_output(Panel(f"[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]", title="Status Effect"))
        else:
            self.ui.update_output(Panel(f"[red]You don't have the ability to learn this spell.[/red]", title="Error"))
            
    def examine_item(self, item_id):
        """Examine an item in detail"""
        if not item_id:
            self.ui.update_output(Panel("[bold red]No item specified. Use 'examine [item]'[/bold red]", title="Error"))
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
                self.ui.update_output(Panel(f"[bold red]Cannot find {item_id} in this directory or your inventory.[/bold red]", title="Error"))
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
        
        self.ui.update_output(Panel(content, title=f"[bold]{title}[/bold]"))
        
        # Execute any special effects defined for examining this item
        if "on_examine" in item:
            self.execute_effect(item["on_examine"])
    
    def talk_to_npc(self, npc_id):
        """Talk to an NPC in the current room"""
        if not npc_id:
            self.ui.update_output(Panel("[bold red]No NPC specified. Use 'talk [npc]'[/bold red]", title="Error"))
            return
        
        current_room = self.player.current_room
        npcs_in_room = self.world.get_npcs_in_room(current_room)
        
        if npc_id not in npcs_in_room:
            self.ui.update_output(Panel(f"[bold red]Cannot find {npc_id} in this directory.[/bold red]", title="Error"))
            return
        
        # Get NPC data
        npc = self.world.get_npc(npc_id)
        if not npc:
            self.ui.update_output(Panel(f"[bold red]Error: NPC data not found for {npc_id}[/bold red]", title="Error"))
            return
        
        # Get dialogue options
        dialogues = npc.get("dialogues", [])
        if not dialogues:
            self.ui.update_output(Panel(f"[yellow]{npc_id} has nothing to say.[/yellow]", title="Conversation"))
            return
        
        # Select a dialogue based on conditions or randomly
        # For now, just pick a random one
        dialogue = random.choice(dialogues)
        
        # Display the dialogue
        dialogue_text = f"[bold yellow]{npc_id}:[/bold yellow] {dialogue}"
        self.ui.update_output(Panel(dialogue_text, title="Conversation"))
        
        # Execute any special effects defined for talking to this NPC
        if "on_talk" in npc:
            self.execute_effect(npc["on_talk"])
    
    def attack_enemy(self, enemy_id):
        """Attack an enemy in the current room"""
        if not enemy_id:
            self.ui.update_output(Panel("[bold red]No enemy specified. Use 'attack [enemy]'[/bold red]", title="Error"))
            return
        
        current_room = self.player.current_room
        enemies_in_room = self.world.get_enemies_in_room(current_room)
        
        if enemy_id not in enemies_in_room:
            self.ui.update_output(Panel(f"[bold red]Cannot find {enemy_id} in this directory.[/bold red]", title="Error"))
            return
        
        # Get enemy data
        enemy = self.world.get_enemy(enemy_id)
        if not enemy:
            self.ui.update_output(Panel(f"[bold red]Error: Enemy data not found for {enemy_id}[/bold red]", title="Error"))
            return
        
        # Start combat
        self.combat(enemy_id, enemy)
    
    
    def show_inventory(self):
        """Display the player's inventory"""
        items = self.player.get_inventory_items()
        
        if not items:
            self.ui.update_output(Panel("[italic]Your inventory is empty.[/italic]", title="Inventory"))
            return
        
        inventory_content = "[bold]Inventory:[/bold]\n"
        for item_id in items:
            item = self.player.get_item_from_inventory(item_id)
            if item is None:
                # Handle case where item might be in inventory but doesn't have proper data
                inventory_content += f"  [green]{item_id}[/green]\n"
                continue
                
            # Use the formatted description
            description = self.get_formatted_item_description(item)
            
            # Mark equipped weapon
            if item_id == self.player.equipped_weapon:
                inventory_content += f"  [green]{item_id}[/green] [cyan](Equipped)[/cyan] - {description}\n"
            else:
                inventory_content += f"  [green]{item_id}[/green] - {description}\n"
    
        self.ui.update_output(Panel(inventory_content.rstrip(), title="Inventory"))
    
    def show_map(self):
        """Display a map of known locations"""
        visited_rooms = [room_id for room_id, state in self.world.room_states.items() if state.get("visited", False)]

        if not visited_rooms:
            self.ui.update_output("[italic]Your map is empty. Explore to discover locations.[/italic]")
            return

        output = Text()
        output.append("Known Locations:\n", style="bold")
        for room_id in sorted(visited_rooms):
            if room_id == self.player.current_room:
                output.append(f"  > {room_id} (You are here)\n", style="bold cyan")
            else:
                output.append(f"  - {room_id}\n", style="blue")
        self.ui.update_output(output)


    def combat(self, enemy_id, enemy):
        """Handle combat with an enemy using event-driven approach."""
        # Create and start a new combat session
        self.current_combat_session = CombatSession(self.player, enemy_id, enemy, self.ui)
        self.current_combat_session.start()
        
        # Subscribe to combat events
        event_bus.subscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
    
    def _on_combat_ended(self, event):
        """Handle combat ended event."""
        if event.data.get("session") != self.current_combat_session:
            return  # Not our combat session
            
        victory = event.data.get("victory", False)
        defeat = event.data.get("defeat", False)
        fled = event.data.get("fled", False)
        enemy_id = event.data.get("enemy_id")
        
        # Unsubscribe from combat events
        event_bus.unsubscribe(EventType.COMBAT_ENDED, self._on_combat_ended)
        
        if victory and enemy_id:
            # Remove the enemy from the room
            event_bus.emit_event(
                EventType.ENEMY_DEFEATED, 
                {"enemy_id": enemy_id, "player": self.player}, 
                "CommandHandler"
            )
            self.world.remove_enemy_from_room(enemy_id)
        
        if defeat:
            # Handle player death (e.g., game over screen)
            debug_log("Player defeated in combat")
        
        # Clear current combat session
        self.current_combat_session = None
    
    def equip_weapon(self, weapon_id):
        """Equip a weapon from inventory."""
        if not weapon_id:
            debug_log("equip command called with no weapon specified")
            self.ui.update_output("[bold red]No weapon specified. Use 'equip [weapon]'[/bold red]")
            return
        
        debug_log(f"Player attempting to equip weapon: {weapon_id}")
        
        if not self.player.has_item(weapon_id):
            debug_log(f"Player doesn't have weapon {weapon_id} in inventory")
            self.ui.update_output(f"[bold red]You don't have {weapon_id} in your inventory.[/bold red]")
            return
        
        # Get weapon data
        weapon = self.player.get_item_from_inventory(weapon_id)
        weapon_type = weapon.get("type")
        
        # Check if it's actually a weapon
        is_weapon = weapon_type == "weapon" or "weapon" in str(weapon_type) if weapon_type else False
        if not is_weapon:
            debug_log(f"Item {weapon_id} is not a weapon")
            self.ui.update_output(f"[bold red]{weapon_id} is not a weapon.[/bold red]")
            return
            
        # Check class restrictions
        if not self.player.can_use_item(weapon):
            class_restriction = weapon.get("class_restriction", "")
            if isinstance(class_restriction, list):
                class_restriction = " or ".join(class_restriction)
            debug_log(f"Weapon {weapon_id} has class restriction: {class_restriction}, player is: {self.player.player_class}")
            self.ui.update_output(f"[bold red]This weapon can only be used by {class_restriction} class.[/bold red]")
            return
        
        # Get old weapon info before equipping the new one
        old_weapon_id = self.player.equipped_weapon
        old_damage = self.player.calculate_damage()
        
        # Equip the weapon
        success = self.player.equip_weapon(weapon_id)
        if success:
            weapon_name = weapon.get("name", weapon_id)
            self.ui.update_output(f"You have equipped [green]{weapon_name}[/green].")
            
            # Display the weapon's effects and new total damage
            new_damage = self.player.calculate_damage()
            damage_change = new_damage - old_damage
            
            if damage_change > 0:
                self.ui.update_output(f"[green]Your total damage increased by {damage_change} (from {old_damage} to {new_damage}).[/green]")
            elif damage_change < 0:
                self.ui.update_output(f"[red]Your total damage decreased by {abs(damage_change)} (from {old_damage} to {new_damage}).[/red]")
            else:
                self.ui.update_output(f"[yellow]Your total damage remains at {new_damage}.[/yellow]")
            
            # Update tutorial progress
            if not self.player.tutorial_state.get("equipped_weapon", False):
                self.player.tutorial_state["equipped_weapon"] = True
                self.show_tutorial_hint("equipped_weapon")
                
        else:
            debug_log(f"Failed to equip weapon {weapon_id}")
            self.ui.update_output(f"[bold red]Failed to equip {weapon_id}.[/bold red]")
    
    def _handle_combat_command(self, command):
        """Handle commands during combat."""
        debug_log(f"Handling combat command: {command}")
        
        # Emit combat action selected event
        event_bus.emit_event(
            EventType.COMBAT_ACTION_SELECTED,
            {"choice": command},
            "CommandHandler"
        )

    def check_for_enemies(self):
        """Check for enemies in the current room and initiate combat if necessary."""
        current_room = self.player.current_room
        enemies = self.world.get_enemies_in_room(current_room)
        if enemies:
            enemy_id = enemies[0]  # For now, fight the first enemy
            enemy = self.world.get_enemy(enemy_id)
            if enemy:
                self.ui.update_output(f"[bold red]An enemy, {enemy.get('name', enemy_id)}, blocks your path![/bold red]")
                self.combat(enemy_id, enemy)

    def execute_effect(self, effect):
        """Execute a special effect from an item or event."""
        if not isinstance(effect, dict):
            self.ui.update_output(f"[italic]{effect}[/italic]")
            return

        if "message" in effect:
            self.ui.update_output(f"[italic cyan]{effect['message']}[/italic]")
        
        if "heal" in effect:
            amount = effect["heal"]
            self.player.heal(amount)
            self.ui.update_output(f"[green]You gained {amount} health![/green]")
        
        if "damage" in effect:
            amount = effect["damage"]
            self.player.take_damage(amount)
            self.ui.update_output(f"[red]You took {amount} damage![/red]")
            if not self.player.is_alive():
                self.game_over()

        if "add_status_effect" in effect:
            status_data = effect["add_status_effect"]
            effect_id = status_data.get("id", "effect_" + str(random.randint(1000, 9999)))
            effect_name = status_data.get("name", "Effect")
            effect_duration = status_data.get("duration", 3)
            self.player.add_status_effect(effect_id, status_data, effect_duration)
            self.ui.update_output(f"[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]")

        if "add_item" in effect:
            item_id = effect["add_item"]
            item = self.world.get_item(item_id)
            if item:
                self.player.add_to_inventory(item_id, item)
                self.ui.update_output(f"[green]You obtained {item.get('name', item_id)}![/green]")

        if "remove_item" in effect:
            item_id = effect["remove_item"]
            if self.player.has_item(item_id):
                item_name = self.player.inventory[item_id].get("name", item_id)
                self.player.remove_from_inventory(item_id)
                self.ui.update_output(f"[yellow]You lost {item_name}![/yellow]")

        if "unlock" in effect:
            room_id = effect["unlock"]
            self.world.unlock_room(room_id)
            self.ui.update_output(f"[yellow]A path to {room_id} has been unlocked![/yellow]")

        if "spawn_enemy" in effect:
            enemy_id = effect["spawn_enemy"]
            room_id = effect.get("in_room", self.player.current_room)
            enemy = self.world.get_enemy(enemy_id)
            if enemy:
                self.world.enemy_locations[enemy_id] = room_id
                if room_id == self.player.current_room:
                    self.ui.update_output(f"[bold red]{enemy.get('name', enemy_id)} has appeared![/bold red]")
                    self.check_for_enemies()

    def game_over(self):
        """Handle game over state"""
        self.ui.update_output("[bold red]YOU HAVE BEEN DELETED[/bold red]")
        self.ui.update_output("[bold red]GAME OVER[/bold red]")
        exit(0)

    def check_game_completion(self):
        """Check if the player has completed the game"""
        if self.player.current_room == "core" and "daemon_overlord.sys" not in self.world.get_enemies_in_room("core"):
            if self.player.has_item("backup.bak"):
                self.win_game()

    def win_game(self):
        """Handle win state"""
        self.ui.update_output("[bold green]Congratulations! You have defeated the Daemon Overlord and restored the filesystem![/bold green]")
        self.ui.update_output("[bold green]You are granted the title of Master Sysadmin![/bold green]")
        self.ui.update_output("\n[bold]THANK YOU FOR PLAYING[/bold]")
        exit(0)

    def handle_unknown_command(self, command):
        """Handle commands that are not recognized."""
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
        self.ui.update_output(f"[italic]{random.choice(responses)}[/italic]")
        self.ui.update_output("[yellow]Hint: Try using standard commands like 'ls', 'cd', 'cat', or type 'help'.[/yellow]")

    def quit_game(self):
        """Handle quit and exit commands"""
        self.ui.update_output("[yellow]Goodbye! Thanks for playing The Haunted Filesystem.[/yellow]")
        exit(0) 