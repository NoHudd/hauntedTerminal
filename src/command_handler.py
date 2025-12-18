#!/usr/bin/env python3
import os
import random
import logging
from rich.text import Text
from src.combat import combat_system, CombatSession
from src.events import event_bus, EventType
from src.game_states import GameState
from utils.debug_tools import debug_log
from utils.typewriter import TypewriterPresets, create_typewriter_output_func

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
        self.npc_dialogue_cooldown = {}  # Track when NPCs last spoke automatically
        self._in_game_over_mode = False  # Track if we're in game over screen mode
        self._in_quit_confirmation = False  # Track if we're confirming quit
        
        # Room aliases for easier navigation (filesystem paths -> full room IDs)
        self.room_aliases = {
            # Filesystem-style paths with / prefix
            "/home": "home_grove",
            "/home/grove": "home_grove",
            "/var": "var_dungeon", 
            "/var/dungeon": "var_dungeon",
            "/mnt": "mnt_forest",
            "/mnt/forest": "mnt_forest",
            "/bin": "bin_armory",
            "/bin/armory": "bin_armory", 
            "/usr": "usr_lib_arcane",
            "/usr/lib": "usr_lib_arcane",
            "/usr/lib/arcane": "usr_lib_arcane",
            "/opt": "opt_mage_tower",
            "/opt/tower": "opt_mage_tower",
            "/srv": "srv_warrior_tomb",
            "/srv/tomb": "srv_warrior_tomb",
            "/tmp": "tmp_hidden_chamber",
            "/tmp/chamber": "tmp_hidden_chamber",
            "/proc": "proc_secrets",
            "/proc/secrets": "proc_secrets",
            "/etc": "etc_hidden_configs",
            "/etc/configs": "etc_hidden_configs",
            "/dev": "dev_null_void",
            "/dev/null": "dev_null_void",
            "/ghost": "ghost_hidden",
            "/archive": "archive", 
            "/deprecated": "deprecated_dir",
            "/": "root",
            "/root": "root",
            "/core": "core",
            
            # Also keep simple names for convenience (no / prefix)
            "home": "home_grove",
            "grove": "home_grove",
            "var": "var_dungeon",
            "dungeon": "var_dungeon", 
            "mnt": "mnt_forest",
            "forest": "mnt_forest",
            "bin": "bin_armory",
            "armory": "bin_armory",
            "usr": "usr_lib_arcane", 
            "lib": "usr_lib_arcane",
            "arcane": "usr_lib_arcane",
            "opt": "opt_mage_tower",
            "tower": "opt_mage_tower",
            "srv": "srv_warrior_tomb",
            "tomb": "srv_warrior_tomb",
            "tmp": "tmp_hidden_chamber",
            "chamber": "tmp_hidden_chamber",
            "proc": "proc_secrets",
            "secrets": "proc_secrets",
            "etc": "etc_hidden_configs",
            "configs": "etc_hidden_configs", 
            "dev": "dev_null_void",
            "null": "dev_null_void",
            "void": "dev_null_void",
            "ghost": "ghost_hidden",
            "deprecated": "deprecated_dir",
            "archive": "archive",
            "root": "root",
            "core": "core"
        }
        
        # Command dispatcher dictionary for easy command handling
        self.commands = {
            "help": self.show_help,
            "shortcuts": self.show_item_shortcuts,
            "ls": self.list_directory,
            "cd": self.change_directory,
            "pwd": self.show_current_directory,
            "cat": self.read_file,
            "map": self.show_map,
            "worldmap": self.show_world_map,
            "take": self.take_item,
            "drop": self.drop_item,
            "use": self.use_item,
            "equip": self.equip_weapon,
            "examine": self.examine_item,
            "talk": self.talk_to_npc,
            "attack": self.attack_enemy,
            "find": self.find_command,
            "ps": self.ps_command,
            "keys": self.show_keys,
            "inventory": self.show_inventory,
            "inv": self.show_inventory,
            "save": self.save_game,
            "quit": self.quit_game,
            "exit": self.quit_game
        }
        
        # Specify which commands require arguments  
        self.commands_with_args = {
            "cd", "cat", "take", "drop", "use", "equip", "examine", "talk", "attack"
        }
        
        # Commands that can optionally take arguments
        self.commands_with_optional_args = {
            "ls", "find", "ps"
        }
        
        debug_log(f"Registered {len(self.commands)} commands")
    
    def setup_event_subscriptions(self):
        """Set up event subscriptions for the command handler."""
        event_bus.subscribe(EventType.ROOM_ENTERED, self._on_room_entered)
        event_bus.subscribe(EventType.ALL_ENEMIES_DEFEATED, self._on_all_enemies_defeated)
        event_bus.subscribe(EventType.ROOM_CHANGED, self._on_room_changed_for_npc)
        debug_log("CommandHandler event subscriptions set up")
    
    def cleanup_event_subscriptions(self):
        """Clean up event subscriptions for the command handler."""
        event_bus.unsubscribe(EventType.ROOM_ENTERED, self._on_room_entered)
        event_bus.unsubscribe(EventType.ALL_ENEMIES_DEFEATED, self._on_all_enemies_defeated) 
        event_bus.unsubscribe(EventType.ROOM_CHANGED, self._on_room_changed_for_npc)
        debug_log("CommandHandler event subscriptions cleaned up")
    
    def _on_room_entered(self, event):
        """Handle room entered event to respawn fled enemies."""
        room_id = event.data.get("room")
        if room_id:
            debug_log(f"Player entered room {room_id}, checking for fled enemies to respawn")
            self.world.respawn_fled_enemies(room_id)
            # Check for enemies after respawning fled ones
            self.check_for_enemies()
    
    def _on_all_enemies_defeated(self, event):
        """Handle all enemies defeated event to trigger NPC guidance."""
        debug_log(f"_on_all_enemies_defeated event received: {event.data}")
        room_id = event.data.get("room")
        if room_id:
            debug_log(f"All enemies defeated in {room_id}, checking for NPCs to provide guidance")
            self._trigger_automatic_npc_dialogue(room_id, "post_combat")
    
    def _on_room_changed_for_npc(self, event):
        """Handle room change event to trigger initial NPC guidance."""
        debug_log(f"_on_room_changed_for_npc event received: {event.data}")
        to_room = event.data.get("to_room")
        if to_room:
            debug_log(f"Player moved to {to_room}, checking for NPCs to provide guidance")
            # Check cooldown to avoid spam (allow one greeting per room per session)
            cooldown_key = f"first_visit_{to_room}"
            if cooldown_key not in self.npc_dialogue_cooldown:
                self.npc_dialogue_cooldown[cooldown_key] = True
                self._trigger_automatic_npc_dialogue(to_room, "first_visit")
            else:
                debug_log(f"NPC greeting cooldown active for {to_room}, skipping")
    
    def _trigger_automatic_npc_dialogue(self, room_id, context):
        """Automatically trigger NPC dialogue for guidance."""
        debug_log(f"_trigger_automatic_npc_dialogue called: room={room_id}, context={context}")
        npcs_in_room = self.world.get_npcs_in_room(room_id)
        debug_log(f"NPCs found in {room_id}: {npcs_in_room}")
        if not npcs_in_room:
            debug_log(f"No NPCs in {room_id}, skipping automatic dialogue")
            return
        
        debug_log(f"Found {len(npcs_in_room)} NPCs in {room_id} for {context} dialogue")
        
        # Get the first NPC (could be enhanced to pick most relevant)
        npc_id = npcs_in_room[0]
        npc_data = self.world.get_npc(npc_id)
        
        if not npc_data:
            return
        
        # Select appropriate dialogue based on context
        dialogues = npc_data.get("dialogues", [])
        if not dialogues:
            return
        
        # Choose dialogue based on context
        if context == "post_combat":
            # Use encouraging/guiding dialogue after combat
            dialogue_index = len(dialogues) - 1 if len(dialogues) > 1 else 0
        else:  # first_visit
            # Use welcoming/introductory dialogue
            dialogue_index = 0
        
        selected_dialogue = dialogues[dialogue_index]
        npc_name = npc_data.get("name", npc_id)
        
        # Format and display the automatic dialogue
        output = Text()
        output.append(f"\n[bold cyan]🗨️  {npc_name} speaks:[/bold cyan]\n")
        output.append(f"[italic cyan]\"{selected_dialogue}\"[/italic cyan]\n")
        
        if context == "post_combat":
            output.append(f"\n[dim]The {npc_name} offers guidance now that the area is safe.[/dim]")
        else:
            output.append(f"\n[dim]Use 'talk {npc_id}' to converse further with the {npc_name}.[/dim]")
        
        self.ui.update_output(output)
        debug_log(f"Triggered automatic dialogue for {npc_id} in context {context}")
    
    def _get_discoverable_hidden_rooms(self, current_room_id):
        """Get hidden rooms that can be discovered from the current location."""
        discoverable_rooms = {}
        
        # Define discovery rules based on the hidden rooms guide
        discovery_rules = {
            "usr_lib_arcane": {
                "etc_hidden_configs": "Configuration directory (accessible via ls -a)"
            },
            "bin_armory": {
                "dev_null_void": "The mysterious /dev/null (try 'find /dev -name null')"
            },
            "mnt_forest": {
                "proc_secrets": "Process information chamber (try 'ps' command)"
            }
        }
        
        # Check if current room has discoverable hidden rooms
        if current_room_id in discovery_rules:
            for hidden_room_id, hint in discovery_rules[current_room_id].items():
                # Only show if the room is still hidden
                room_state = self.world.get_room_state(hidden_room_id)
                if room_state and room_state.get("hidden", False):
                    discoverable_rooms[hidden_room_id] = hint
        
        return discoverable_rooms

    def _get_hidden_room_hint(self, room_id):
        """Get a helpful hint for accessing hidden rooms."""
        hints = {
            "opt_mage_tower": "🔒 This area requires an 'opt_key' and is restricted to mages. Try exploring to find keys!",
            "srv_warrior_tomb": "🔒 This area requires an 'opt_key' and is restricted to fighters.",
            "tmp_hidden_chamber": "🔒 This hidden area requires a 'tmp_key' to access.",
            "etc_hidden_configs": "💡 Try using 'ls -a' in the Arcane Library to discover hidden directories.",
            "dev_null_void": "💡 Try using 'find /dev -name null' in the Binary Armory.",
            "proc_secrets": "💡 Try using 'ps' command in the Mount Forest to discover process secrets."
        }
        return hints.get(room_id, "This area might be discoverable through exploration.")

    def _get_room_status_indicator(self, room_id):
        """Get status indicator for a room in the map."""
        room_state = self.world.get_room_state(room_id)
        if not room_state:
            return ""
        
        indicators = []
        
        # Check if locked
        if room_state.get("locked", False):
            key_required = room_state.get("key_required")
            if key_required and self.player.has_item(key_required):
                indicators.append("🔓")  # Locked but player has key
            else:
                indicators.append("🔒")  # Locked
        
        # Check class restrictions
        if room_state.get("class_restriction"):
            class_restriction = room_state.get("class_restriction")
            if self.player.player_class == class_restriction:
                indicators.append("✅")  # Player class matches
            else:
                indicators.append("⚔️")  # Class restricted
        
        # Check if hidden (shouldn't appear here, but just in case)
        if room_state.get("hidden", False):
            indicators.append("❓")
            
        return " ".join(indicators) if indicators else ""

    def _get_player_keys(self):
        """Get list of keys in player inventory."""
        keys = []
        for item_id, item_data in self.player.inventory.items():
            if item_data and (item_data.get("type") == "key" or "key" in item_id.lower()):
                keys.append(item_id)
        return keys

    def show_tutorial_hint(self, hint_type, item_name=None):
        """Show contextual tutorial hints based on player progress."""
        if self.player.tutorial_state.get("completed", False):
            return  # Tutorial already completed
        
        # Get the actual weapon name for dynamic hints
        if item_name:
            weapon_name = item_name
        else:
            # Get class-specific starter weapon
            class_starter_weapons = {
                "guardian": "protocol_shield",
                "weaver": "byte_blaster", 
                "shaman": "echo_staff"
            }
            weapon_name = class_starter_weapons.get(self.player.player_class, "protocol_shield")
            
        # Get player name for personalization
        player_name = self.player.name if hasattr(self.player, 'name') and self.player.name else "spirit"
        
        hints = {
            "welcome": f"[bold green]ECHO>[/bold green] [italic]Ah, {player_name}... you have manifested in the /home grove. This sector remains stable—a sanctuary in the digital chaos.\n\nYour spirit-form is adapting to the command interface. Try [bold]ls[/bold] to scan this directory's contents.\nRemember: files are fragments of power. Some hold tools, others hold secrets.[/italic]",
            "first_look": f"[bold green]ECHO>[/bold green] [italic]Good, {player_name}. You're learning to see through the corruption.\nTo claim artifacts, use [bold]take <filename>[/bold]. To wield tools of power, use [bold]equip <item>[/bold].\nYour possessions appear in the inventory panel—the void claims careless spirits.[/italic]",
            "found_weapon": f"[bold green]ECHO>[/bold green] [italic]Excellent, {player_name}! I sense a weapon resonating with your {self.player.player_class.title()} essence.\nThe [bold]{weapon_name}[/bold] pulses with familiar energy. Use [bold]take {weapon_name}[/bold] to bind it to your spirit.[/italic]",
            "took_weapon": f"[bold green]ECHO>[/bold green] [italic]The weapon recognizes you, {player_name}. When darkness manifests as corrupted processes, you must be ready.\nUse [bold]equip {weapon_name}[/bold] to channel its power. Every battle is a struggle for the filesystem's soul.[/italic]",
            "equipped_weapon": f"[bold green]ECHO>[/bold green] [italic]Well done, {player_name}. Your essence and weapon are now synchronized.\nIn combat, use [bold]attack [enemy][/bold] to strike, or execute weapon abilities as commands.\nCheck the inventory panel to review your spiritual arsenal.[/italic]",
            "completed": f"[bold green]ECHO> Tutorial Complete, {player_name}![/bold green] [italic]The basic interface is now yours to command.\nThe corrupted directories await your cleansing touch. Purge the malevolent code and restore the root filesystem.\n\nMay your commands ring true in the digital void...[/italic]"
        }
        
        if hint_type in hints:
            hint_text = f"[dim]{hints[hint_type]}[/dim]"
            
            # Use typewriter effect for tutorial hints (faster than narrative)
            output_callback = create_typewriter_output_func(
                lambda text: self.ui.update_output(f"[dim cyan]>>> Echo transmitting...[/dim cyan]\n\n{text}")
            )
            
            try:
                TypewriterPresets.SYSTEM.type_text_sync(hint_text, output_callback)
                # Final clean output
                self.ui.update_output(hint_text)
            except Exception as e:
                # Fallback to instant display if typewriter fails
                debug_log(f"Typewriter effect failed for tutorial hint {hint_type}: {e}")
                self.ui.update_output(hint_text)
    
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
        
        # Handle game over mode specially
        if self._in_game_over_mode:
            result = self._handle_game_over_choice(command.strip())
            if result == "quit":
                import sys
                sys.exit(0)
            elif result == "restart_from_save" or result == "start_new_game":
                # Signal the game engine to restart
                event_bus.emit_event(
                    EventType.GAME_OVER,
                    {"action": result},
                    "CommandHandler"
                )
            return

        # Check if player is dead and trigger game over if not already handled
        if self.player and not self.player.is_alive() and not self._in_game_over_mode:
            debug_log("Player is dead but not in game over mode - triggering game over screen")
            self._show_game_over_screen()
            return
        
        # Handle quit confirmation mode specially
        if self._in_quit_confirmation:
            self._handle_quit_confirmation(command.strip())
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
            elif cmd in self.commands_with_optional_args:
                # Command can optionally take arguments
                arg = args[0] if args else ""
                debug_log(f"Executing command '{cmd}' with optional arg '{arg}'")
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
        - [cyan]shortcuts[/cyan]: Show item shortcuts and typing tips
        - [cyan]ls[/cyan]: List files and directories
        - [cyan]cd [directory][/cyan]: Change to specified directory
        - [cyan]pwd[/cyan]: Show current directory
        - [cyan]cat [file][/cyan]: Read the contents of a file
        - [cyan]map[/cyan]: Show available locations
        - [cyan]worldmap[/cyan]: Show ASCII world layout
        - [cyan]keys[/cyan]: Show key progression system
        - [cyan]take [item][/cyan]: Add an item to your inventory
        - [cyan]drop [item][/cyan]: Remove an item from your inventory
        - [cyan]use [item][/cyan]: Use consumables (potions, scrolls)
        - [cyan]equip [weapon][/cyan]: Equip a weapon for combat
        - [cyan]examine [item][/cyan]: Examine an item in detail
        - [cyan]talk [npc][/cyan]: Talk to an NPC
        - [cyan]attack [enemy][/cyan]: Attack an enemy
        - [cyan]find [path] -name [pattern][/cyan]: Search for files and directories
        - [cyan]ps[/cyan]: Show running processes
        - [cyan]inventory[/cyan] or [cyan]inv[/cyan]: Show detailed inventory with rarities
        - [cyan]save[/cyan]: Save your current progress
        - [cyan]quit[/cyan] or [cyan]exit[/cyan]: Quit the game (offers to save)
        
        [bold]Navigation Tips:[/bold]
        - Use filesystem paths: [yellow]cd /var[/yellow], [yellow]cd /home[/yellow], [yellow]cd /bin[/yellow]
        - Or simple names: [yellow]cd var[/yellow], [yellow]cd home[/yellow], [yellow]cd bin[/yellow]
        """
        help_content = f"[bold]Help[/bold]\n\n{help_text}"
        self.ui.update_output(help_content)
    
    def show_item_shortcuts(self):
        """Display available item shortcuts and typing tips."""
        shortcuts_text = """[bold cyan]Item Shortcuts & Typing Tips:[/bold cyan]

[bold]Health & Healing:[/bold]
- [yellow]hp[/yellow] or [yellow]heal[/yellow] → health potion
- [yellow]health[/yellow] → any health potion 
- [yellow]potion[/yellow] → any potion

[bold]Weapons:[/bold]
- [yellow]staff[/yellow] → echo_staff
- [yellow]shield[/yellow] → protocol_shield  
- [yellow]blaster[/yellow] → byte_blaster

[bold]Other Items:[/bold]
- [yellow]strength[/yellow] → strength_potion
- [yellow]swift[/yellow] → swiftness_tonic
- [yellow]fortitude[/yellow] → fortitude_elixir

[bold]Partial Matching:[/bold]
You can type just the beginning of an item name:
- [yellow]health_pot[/yellow] → health_potion_minor
- [yellow]echo[/yellow] → echo_staff

[bold cyan]Usage Examples:[/bold cyan]
- [green]take hp[/green] (instead of take health_potion_minor)
- [green]use heal[/green] (instead of use health_potion_minor)
- [green]take staff[/green] (instead of take echo_staff)"""
        self.ui.update_output(shortcuts_text)
    
    def show_current_directory(self):
        """Display the current directory (room) name"""
        self.ui.update_output(f"Current directory: [bold]{self.player.current_room}[/bold]")
    
    def get_atmospheric_description(self, room_id):
        """Get enhanced atmospheric description for key locations"""
        atmospheric_descriptions = {
            "home_grove": "[dim italic]A sanctuary of code-trees and branching directories. Streams of green text flow gently like rivers of syntax. This is where new spirits awaken, free from daemon corruption. Safe, quiet, but humming with potential.[/dim italic]",
            "var_dungeon": "[dim italic]A labyrinth of shifting directories and volatile processes. Error messages echo through dripping tunnels of corrupted logs. Here, daemons nest in unstable caches, waiting to ambush unwary explorers. Proceed with caution.[/dim italic]",
            "core": "[dim italic]The heart of the machine. Data storms crackle like thunder, illuminating endless monoliths of code. The Daemon Overlord resides here, rewriting the root with every cycle. This is the system's last stand.[/dim italic]",
            "mnt_forest": "[dim italic]Mounted drives tower like digital trees, their data branches swaying with the flow of network packets. Ancient filesystem paths wind through shadowed directories where forgotten files rest in peace.[/dim italic]",
            "bin_armory": "[dim italic]Executable files line the walls like weapons in an arsenal. Command-line tools gleam with binary precision, while system utilities hum with dormant power. The air crackles with potential processes.[/dim italic]",
            "usr_lib_arcane": "[dim italic]Libraries of mystical functions stretch endlessly into the digital horizon. Arcane algorithms whisper their secrets, and shared objects pulse with collective knowledge accumulated across countless runtime cycles.[/dim italic]"
        }
        
        return atmospheric_descriptions.get(room_id, "")

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
        
        # Get atmospheric enhancement
        atmospheric = self.get_atmospheric_description(room_id)
        
        # Get exits
        exits = self.world.get_exits(room_id)
        exits_str = "Exits: " + ", ".join(exits) if exits else "No visible exits."
        
        # Create content with title and atmospheric description
        location_content = f"[bold]{title}[/bold]\n\n{description}"
        if atmospheric:
            location_content += f"\n\n{atmospheric}"
        location_content += f"\n\n{exits_str}"
        
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
    
    def _check_enemies_blocking_exploration(self, room_id):
        """Check if enemies are present and blocking exploration. Returns (has_enemies, output_text)"""
        enemies = self.world.get_enemies_in_room(room_id) or []
        if not enemies:
            return False, None
        
        output = Text()
        output.append("[bold red]⚠️  COMBAT REQUIRED  ⚠️[/bold red]\n\n")
        output.append("Hostile entities are present! You must defeat all enemies before exploring.\n\n")
        
        output.append("Corrupted Entities:\n", style="bold red") 
        for enemy_id in enemies:
            enemy = self.world.get_enemy(enemy_id, self.player.player_class)
            if enemy:
                name = enemy.get("name", enemy_id)
                health = enemy.get("health", "??")
                output.append(f"  {enemy_id}", style="red")
                output.append(f" - {name} (HP: {health})\n")
        
        output.append("\nUse [cyan]attack [enemy][/cyan] to engage in combat.")
        return True, output

    def list_directory(self, args=""):
        """Show files (items), processes (NPCs), and corrupted entities (enemies) in the current location"""
        room_id = self.player.current_room
        output = Text()
        has_content = False
        show_hidden = args == "-a"  # Check for -a flag
        
        # Tutorial: first ls
        if not self.player.tutorial_state.get("first_ls", False):
            self.player.tutorial_state["first_ls"] = True
        
        # Check for enemies first - if enemies present, block exploration
        has_enemies, enemy_output = self._check_enemies_blocking_exploration(room_id)
        if has_enemies:
            self.ui.update_output(enemy_output)
            return
        
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
                enemy = self.world.get_enemy(enemy_id, self.player.player_class)
                if enemy:
                    name = enemy.get("name", enemy_id)
                    health = enemy.get("health", "??")
                    damage = enemy.get("damage", "??")
                    output.append(f"  {enemy_id}", style="red")
                    output.append(f" - {name} (HP: {health}, DMG: {damage})\n")
                else:
                    output.append(f"  {enemy_id} - Unknown Enemy\n", style="red")
            has_content = True

        # Show hidden directories when using ls -a
        if show_hidden:
            hidden_rooms = self._get_discoverable_hidden_rooms(room_id)
            if hidden_rooms:
                if has_content:
                    output.append("\n")
                output.append("Hidden Directories (discoverable):\n", style="bold yellow")
                for hidden_room_id, hint in hidden_rooms.items():
                    output.append(f"  .{hidden_room_id}", style="dim yellow")
                    output.append(f" - {hint}\n", style="dim")
                has_content = True
                
                # Discover the rooms when using ls -a
                for hidden_room_id in hidden_rooms:
                    if self.world.discover_room(hidden_room_id):
                        output.append(f"\n[bold green]Discovered hidden directory: {hidden_room_id}![/bold green]\n")

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
        
        # Check if directory is an alias and resolve to full room ID
        original_directory = directory
        if directory.lower() in self.room_aliases:
            directory = self.room_aliases[directory.lower()]
            debug_log(f"Resolved alias '{original_directory}' to '{directory}'")
        
        current_room = self.player.current_room
        debug_log(f"Player attempting to move from {current_room} to {directory}")
        
        # Check if we can move to the destination
        can_move, reason = self.world.can_move_to(current_room, directory)
        debug_log(f"Can move to {directory}: {can_move}, reason: {reason}")
        
        # If room is hidden, it can't be accessed directly
        room_state = self.world.get_room_state(directory)
        if room_state.get("hidden", False):
            debug_log(f"Attempt to access hidden room {directory} - access denied")
            
            # Provide helpful hints based on the room
            hint_message = self._get_hidden_room_hint(directory)
            self.ui.update_output(f"[bold red]That path doesn't appear to exist.[/bold red]")
            if hint_message:
                self.ui.update_output(f"[dim yellow]{hint_message}[/dim yellow]")
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
            
            # Provide helpful hints for locked rooms
            if "locked" in reason.lower():
                room_state = self.world.get_room_state(directory)
                key_required = room_state.get("key_required") if room_state else None
                class_restriction = room_state.get("class_restriction") if room_state else None
                
                if key_required:
                    self.ui.update_output(f"[yellow]💡 Hint: This area requires '{key_required}' to unlock.[/yellow]")
                if class_restriction:
                    self.ui.update_output(f"[cyan]⚔️ Class Restriction: Only {class_restriction}s can enter this area.[/cyan]")
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
        
        current_room = self.player.current_room
        
        # Check for enemies first - block item taking if enemies present
        has_enemies, enemy_output = self._check_enemies_blocking_exploration(current_room)
        if has_enemies:
            self.ui.update_output(enemy_output)
            return
        
        # Try to resolve shortcuts and partial matches
        actual_item_id = self._resolve_item_shortcut(item_id, "room")
        if not actual_item_id:
            debug_log(f"Item {item_id} not found in room after shortcut resolution")
            self.ui.update_output(f"[bold red]Cannot find {item_id} in this directory.[/bold red]")
            return
        
        debug_log(f"Player attempting to take item: {actual_item_id} (from input: {item_id})")
        items_in_room = self.world.get_items_in_room(current_room)
        
        if actual_item_id not in items_in_room:
            debug_log(f"Item {actual_item_id} not found in room {current_room}")
            self.ui.update_output(f"[bold red]Cannot find {item_id} in this directory.[/bold red]")
            return
        
        # Get item data
        item = self.world.get_item(actual_item_id)
        if not item:
            debug_log(f"Error: Item data not found for {actual_item_id}")
            self.ui.update_output(f"[bold red]Error: Item data not found for {item_id}[/bold red]")
            return
        
        # Check if item is takeable
        if not item.get("takeable", True):
            debug_log(f"Item {actual_item_id} is not takeable")
            self.ui.update_output(f"[bold red]You cannot take {item_id}.[/bold red]")
            return
        
        # Check class restrictions
        if not self.player.can_use_item(item):
            class_restriction = self._get_class_restriction_text(item)
            debug_log(f"Item {actual_item_id} is class-restricted, player class {self.player.player_class} not allowed")
            self.ui.update_output(f"[bold red]Only {class_restriction} spirits can wield {item_id}. Your essence is incompatible.[/bold red]")
            return
        
        # Add to inventory and remove from room
        success = self.player.add_to_inventory(actual_item_id, item)
        if success:
            debug_log(f"Player took item {actual_item_id} from room {current_room}")
            self.world.remove_item_from_room(actual_item_id)
            
            # Import rarity system and format item name with rarity
            from src.rarity import RaritySystem
            item_name = item.get("name", actual_item_id)
            rarity = item.get("rarity", "common")
            formatted_name = RaritySystem.format_item_name_with_rarity(item_name, rarity, show_emoji=False)
            
            self.ui.update_output(f"Added {formatted_name} to your inventory.")
            
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
                self.show_tutorial_hint("took_weapon", actual_item_id)
        else:
            debug_log(f"Failed to add {actual_item_id} to inventory")
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
        
        # Try to resolve shortcuts and partial matches for inventory items
        actual_item_id = self._resolve_item_shortcut(item_id, "inventory")
        if not actual_item_id:
            debug_log(f"Item {item_id} not found in inventory after shortcut resolution")
            self.ui.update_output(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return
        
        debug_log(f"Player attempting to use item: {actual_item_id} (from input: {item_id})")
        
        if not self.player.has_item(actual_item_id):
            debug_log(f"Player doesn't have item {actual_item_id} in inventory")
            self.ui.update_output(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return
        
        # Get item data
        item = self.player.get_item_from_inventory(actual_item_id)
        
        # Get the item type if it exists
        item_type = item.get("type")
        debug_log(f"Using item {actual_item_id} of type {item_type}")
        
        # Check if item is a weapon (weapons should be equipped, not used)
        is_weapon = item_type == "weapon" or "weapon" in str(item_type) if item_type else False
        if is_weapon:
            debug_log(f"Item {actual_item_id} is a weapon, should be equipped instead of used")
            self.ui.update_output(f"[bold yellow]{item_id} is a weapon. Use 'equip {item_id}' to equip it.[/bold yellow]")
            return
            
        # Check if item is usable
        if not item.get("usable", False):
            debug_log(f"Item {actual_item_id} is not usable")
            self.ui.update_output(f"[bold red]You cannot use {item_id}.[/bold red]")
            return
            
        # Check class restrictions
        if not self.player.can_use_item(item):
            class_restriction = self._get_class_restriction_text(item)
            debug_log(f"Item {actual_item_id} has class restriction: {class_restriction}, player is: {self.player.player_class}")
            self.ui.update_output(f"[bold red]This item can only be used by {class_restriction} class.[/bold red]")
            return
        
        # Process item based on its type
        if item_type == "key":
            debug_log(f"Handling key item: {actual_item_id}")
            self._handle_key_item(actual_item_id, item)
        elif item_type == "lore":
            debug_log(f"Handling lore item: {actual_item_id}")
            self._handle_lore_item(actual_item_id, item)
        elif item_type == "consumable" or "heal" in item.get("on_use", {}):
            debug_log(f"Handling consumable item: {actual_item_id}")
            self._handle_consumable_item(actual_item_id, item)
        elif "upgrade" in item_type if item_type else False:
            debug_log(f"Handling upgrade item: {actual_item_id}")
            self._handle_upgrade_item(actual_item_id, item)
        elif "spell" in item_type if item_type else False:
            debug_log(f"Handling spell item: {actual_item_id}")
            self._handle_spell_item(actual_item_id, item)
        else:
            # Execute generic on_use effect for other items
            if "on_use" in item:
                debug_log(f"Executing generic on_use effect for item: {actual_item_id}")
                self.execute_effect(item["on_use"])
                item_name = item.get("name", item_id)
                self.ui.update_output(f"You used [green]{item_name}[/green].")
            else:
                debug_log(f"Item {actual_item_id} has no on_use effect")
                self.ui.update_output(f"Nothing happens when you try to use {item_id}.")
        
        # Check if item is consumed on use
        if item.get("consumed_on_use", False):
            debug_log(f"Item {actual_item_id} was consumed on use")
            self.player.remove_from_inventory(actual_item_id)
            item_name = item.get("name", item_id)
            self.ui.update_output(f"The [green]{item_name}[/green] was consumed.")
    
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
        
        # Import rarity system
        from src.rarity import RaritySystem
        
        # Display item details with rarity
        item_name = item.get("name", item_id)
        rarity = item.get("rarity", "common")
        formatted_name = RaritySystem.format_item_name_with_rarity(item_name, rarity, show_emoji=False)
        
        title = f"Examining: {formatted_name}"
        description = item.get("description", "No detailed description available.")
        
        # Add additional details if available
        details = []
        
        # Add rarity information
        details.append(f"[bold]Rarity:[/bold] [{RaritySystem.get_rarity_color(rarity)}]{rarity.title()}[/{RaritySystem.get_rarity_color(rarity)}]")
        
        # Add item type and damage
        item_type = item.get("type", "unknown")
        details.append(f"[bold]Type:[/bold] {item_type.title()}")
        
        if item_type == "weapon":
            damage = item.get("damage", 0)
            if damage > 0:
                details.append(f"[bold]Damage:[/bold] {damage}")
        elif item_type == "consumable":
            healing = item.get("healing", 0)
            if healing > 0:
                details.append(f"[bold]Healing:[/bold] {healing} HP")
        
        # Add usage information
        if item.get("usable", False):
            details.append("[green]This item can be used.[/green]")
        if item.get("consumed_on_use", False) or item.get("consumable", False):
            details.append("[yellow]This item will be consumed when used.[/yellow]")
        if not item.get("takeable", True):
            details.append("[red]This item cannot be taken.[/red]")
        if not item.get("droppable", True):
            details.append("[red]This item cannot be dropped once taken.[/red]")
        
        # Add class restrictions
        if "class_restriction" in item:
            allowed_classes = item["class_restriction"]
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            details.append(f"[bold]Class Restriction:[/bold] {', '.join(allowed_classes).title()}")
        elif "allowed_classes" in item:
            allowed_classes = item["allowed_classes"]
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            details.append(f"[bold]Allowed Classes:[/bold] {', '.join(allowed_classes).title()}")
        
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
        
        # Display the dialogue with typewriter effect
        npc_name = npc.get("name", npc_id)
        dialogue_text = f"[bold yellow]{npc_name}:[/bold yellow] {dialogue}"
        
        # Use typewriter effect for NPC dialogue
        output_callback = create_typewriter_output_func(
            lambda text: self.ui.update_output(f"[dim cyan]>>> Conversation in progress...[/dim cyan]\n\n{text}")
        )
        
        try:
            TypewriterPresets.DIALOGUE.type_text_sync(dialogue_text, output_callback)
            # Final output with conversation styling
            self.ui.update_output(f"[bold]Conversation[/bold]\n\n{dialogue_text}")
        except Exception as e:
            # Fallback to instant display if typewriter fails
            debug_log(f"Typewriter effect failed for NPC {npc_id}: {e}")
            self.ui.update_output(f"[bold]Conversation[/bold]\n\n{dialogue_text}")
        
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
        
        # Get enemy data with class-based scaling
        enemy = self.world.get_enemy(enemy_id, self.player.player_class)
        if not enemy:
            self.ui.update_output(Panel(f"[bold red]Error: Enemy data not found for {enemy_id}[/bold red]", title="Error"))
            return
        
        # Start combat
        self.combat(enemy_id, enemy)
    
    
    def show_inventory(self):
        """Display the player's inventory with rarity colors and sorting"""
        items = self.player.get_inventory_items()
        
        if not items:
            self.ui.update_output(Panel("[italic]Your inventory is empty.[/italic]", title="Inventory"))
            return
        
        # Import rarity system
        from src.rarity import RaritySystem
        
        inventory_content = "[bold]Inventory:[/bold]\n"
        
        # Sort items by rarity (highest to lowest), then by name
        sorted_items = sorted(
            [(item_id, self.player.get_item_from_inventory(item_id)) for item_id in items],
            key=lambda x: (-RaritySystem.get_rarity_order(x[1].get("rarity", "common")) if x[1] else 0, x[1].get("name", x[0]) if x[1] else x[0])
        )
        
        for item_id, item in sorted_items:
            if item is None:
                # Handle case where item might be in inventory but doesn't have proper data
                inventory_content += f"  [green]{item_id}[/green]\n"
                continue
            
            # Check if this item is equipped
            is_equipped = (item_id == self.player.equipped_weapon)
            
            # Format with rarity system
            formatted_item = RaritySystem.format_inventory_item(item_id, item, is_equipped)
            
            # Use the formatted description
            description = self.get_formatted_item_description(item)
            
            inventory_content += f"  {formatted_item}\n    [dim]{description}[/dim]\n"
    
        self.ui.update_output(Panel(inventory_content.rstrip(), title="Inventory"))
    
    def show_map(self):
        """Display an enhanced map of known locations with status indicators"""
        visited_rooms = [room_id for room_id, state in self.world.room_states.items() if state.get("visited", False)]
        
        # Only show rooms that are accessible from visited rooms (not hidden from visited areas)
        discovered_rooms = []
        for visited_room in visited_rooms:
            exits = self.world.get_exits(visited_room)
            for exit_room in exits:
                room_state = self.world.get_room_state(exit_room)
                if (exit_room not in visited_rooms and 
                    room_state and not room_state.get("hidden", False)):
                    discovered_rooms.append(exit_room)
        
        # Remove duplicates
        discovered_rooms = list(set(discovered_rooms))

        if not visited_rooms and not discovered_rooms:
            self.ui.update_output("[italic]Your map is empty. Explore to discover locations.[/italic]")
            return

        output = Text()
        output.append("🗺️  SYSTEM MAP\n", style="bold cyan")
        output.append("=" * 50 + "\n", style="dim")
        
        # Show visited rooms
        if visited_rooms:
            output.append("\n✅ EXPLORED AREAS:\n", style="bold green")
            for room_id in sorted(visited_rooms):
                status_indicator = self._get_room_status_indicator(room_id)
                if room_id == self.player.current_room:
                    output.append(f"  ➤ {room_id} {status_indicator} [bold cyan](YOU ARE HERE)[/bold cyan]\n")
                else:
                    output.append(f"  • {room_id} {status_indicator}\n", style="green")
        
        # Show discovered but unvisited rooms
        unvisited_discovered = [room for room in discovered_rooms if room not in visited_rooms]
        if unvisited_discovered:
            output.append("\n🔍 DISCOVERED AREAS:\n", style="bold yellow")
            for room_id in sorted(unvisited_discovered):
                status_indicator = self._get_room_status_indicator(room_id)
                output.append(f"  • {room_id} {status_indicator}\n", style="yellow")
        
        # Show key inventory
        keys = self._get_player_keys()
        if keys:
            output.append("\n🔑 YOUR KEYS:\n", style="bold blue")
            for key_id in keys:
                output.append(f"  • {key_id}\n", style="blue")
        
        # Show hint
        output.append(f"\n[dim]💡 Use 'ls -a', 'find', and 'ps' to discover hidden areas![/dim]")
        
        self.ui.update_output(output)

    def show_world_map(self):
        """Display an ASCII world map showing spatial relationships."""
        output = Text()
        output.append("🗺️  FILESYSTEM WORLD MAP\n", style="bold cyan")
        output.append("=" * 60 + "\n", style="dim")
        
        # Get current room status for display
        current_room = self.player.current_room
        
        # Create ASCII map layout
        ascii_map = """
                    ┌─[root]─────────────────────────┐
                    │                               │
            ┌─[bin_armory]                 [usr_lib_arcane]─┐
            │       │                           │           │
      [dev_null_void]└──────────┬─────────────────┘    [etc_hidden]
                               │                       (hidden)
                        [home_grove]
                         │       │
                   [var_dungeon] [mnt_forest]────┬─────────────────┐
                         │            │          │                 │
                [tmp_hidden_chamber]   │    [opt_mage_tower]  [srv_warrior_tomb]
                      (hidden)         │      (🔒 mage)        (🔒 fighter)
                                       │
                                 [proc_secrets]
                                   (hidden)
        """
        
        # Color and highlight the map based on player progress
        lines = ascii_map.strip().split('\n')
        for line in lines:
            formatted_line = self._format_map_line(line, current_room)
            output.append(formatted_line + "\n")
        
        # Add legend
        output.append("\n" + "─" * 60 + "\n", style="dim")
        output.append("📍 LEGEND:\n", style="bold yellow")
        output.append("  ➤ YOUR LOCATION    🔒 Locked Area    (hidden) Not Discovered\n", style="dim")
        output.append("  ✅ Visited         🔍 Discovered     ❓ Unknown\n", style="dim")
        
        self.ui.update_output(output)

    def _format_map_line(self, line, current_room):
        """Format a single line of the ASCII map with colors and status."""
        # Extract room names from brackets
        import re
        rooms_in_line = re.findall(r'\[([^\]]+)\]', line)
        
        formatted_line = line
        for room_id in rooms_in_line:
            original = f"[{room_id}]"
            
            # Determine room status and color
            if room_id == current_room:
                replacement = f"[bold cyan]➤[{room_id}]←[/bold cyan]"
            elif self._is_room_visited(room_id):
                replacement = f"[green]✅[{room_id}][/green]"
            elif self._is_room_discovered(room_id):
                replacement = f"[yellow]🔍[{room_id}][/yellow]"
            else:
                replacement = f"[dim]❓[{room_id}][/dim]"
            
            formatted_line = formatted_line.replace(original, replacement)
        
        return formatted_line

    def _is_room_visited(self, room_id):
        """Check if a room has been visited."""
        room_state = self.world.get_room_state(room_id)
        return room_state and room_state.get("visited", False)

    def _is_room_discovered(self, room_id):
        """Check if a room has been discovered (not hidden)."""
        room_state = self.world.get_room_state(room_id)
        return room_state and not room_state.get("hidden", False)

    def find_command(self, args=""):
        """Implement find command for discovering hidden areas."""
        if not args:
            self.ui.update_output("[yellow]Usage: find [path] -name [pattern][/yellow]")
            return
        
        # Parse find command arguments
        parts = args.split()
        if len(parts) >= 3 and parts[1] == "-name":
            path = parts[0]
            pattern = parts[2]
            
            # Specific discovery: find /dev -name null
            if path == "/dev" and pattern == "null":
                if self.player.current_room == "bin_armory":
                    if self.world.discover_room("dev_null_void"):
                        self.ui.update_output("[bold green]Found: /dev/null_void[/bold green]")
                        self.ui.update_output("A mysterious void where deleted data accumulates...")
                        self.ui.update_output("[yellow]You can now access it with: cd dev_null_void[/yellow]")
                    else:
                        self.ui.update_output("[dim]Found: /dev/null_void (already discovered)[/dim]")
                else:
                    self.ui.update_output("[red]find: '/dev': No such file or directory[/red]")
            else:
                self.ui.update_output(f"[red]find: '{path}': No such file or directory[/red]")
        else:
            self.ui.update_output("[yellow]Usage: find [path] -name [pattern][/yellow]")

    def ps_command(self, args=""):
        """Implement ps command for discovering process-related areas."""
        if self.player.current_room == "mnt_forest":
            # Show some fake processes
            self.ui.update_output("PID  PPID  CMD")
            self.ui.update_output("  1     0  /sbin/init")
            self.ui.update_output(" 42     1  [mount_daemon]")
            self.ui.update_output("127     1  /proc/secrets_handler")
            self.ui.update_output("...")
            
            # Discover the proc_secrets room
            if self.world.discover_room("proc_secrets"):
                self.ui.update_output("\n[bold green]Discovered hidden process chamber: proc_secrets[/bold green]")
                self.ui.update_output("The secrets_handler process reveals a hidden chamber...")
                self.ui.update_output("[yellow]You can now access it with: cd proc_secrets[/yellow]")
            else:
                self.ui.update_output("\n[dim]Process chamber already discovered: proc_secrets[/dim]")
        else:
            # Show generic ps output for other rooms
            self.ui.update_output("PID  PPID  CMD")
            self.ui.update_output("  1     0  /sbin/init")
            self.ui.update_output(" 23     1  [kthreadd]")
            self.ui.update_output(" 42     1  [ksoftirqd/0]")

    def show_keys(self):
        """Display key progression and unlock information."""
        output = Text()
        output.append("🔑 KEY PROGRESSION SYSTEM\n", style="bold cyan")
        output.append("=" * 50 + "\n", style="dim")
        
        # Define key progression chain
        key_info = {
            "lib_key": {
                "name": "Library Key",
                "found_in": "usr_lib_arcane",
                "unlocks": ["var_dungeon"],
                "description": "Unlocks the Variable Dungeon"
            },
            "tmp_key": {
                "name": "Temporary Key", 
                "found_in": "var_dungeon",
                "unlocks": ["tmp_hidden_chamber"],
                "description": "Unlocks the hidden temporary chamber"
            },
            "opt_key": {
                "name": "Optional Key",
                "found_in": "tmp_hidden_chamber", 
                "unlocks": ["opt_mage_tower", "srv_warrior_tomb"],
                "description": "Unlocks class-restricted areas"
            }
        }
        
        # Show progression status
        output.append("📋 PROGRESSION STATUS:\n", style="bold yellow")
        
        for key_id, info in key_info.items():
            has_key = self.player.has_item(key_id)
            key_symbol = "✅" if has_key else "❌"
            
            output.append(f"\n{key_symbol} {info['name']} ({key_id})\n", style="bold" if has_key else "dim")
            output.append(f"   📍 Found in: {info['found_in']}\n", style="green" if has_key else "dim")
            output.append(f"   🚪 Unlocks: {', '.join(info['unlocks'])}\n", style="blue" if has_key else "dim")
            output.append(f"   💡 {info['description']}\n", style="italic")
        
        # Show current keys in inventory
        player_keys = self._get_player_keys()
        if player_keys:
            output.append("\n🎒 KEYS IN INVENTORY:\n", style="bold green")
            for key in player_keys:
                output.append(f"  • {key}\n", style="green")
        else:
            output.append("\n[dim]No keys currently in inventory.[/dim]\n")
        
        # Show progression hints
        output.append("\n💡 PROGRESSION HINTS:\n", style="bold magenta")
        output.append("1. Start by exploring usr_lib_arcane to find the lib_key\n", style="dim")
        output.append("2. Use lib_key to unlock var_dungeon and find tmp_key\n", style="dim")
        output.append("3. Use tmp_key to access tmp_hidden_chamber and find opt_key\n", style="dim")
        output.append("4. Use opt_key to access class-restricted end-game areas\n", style="dim")
        
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
            
            # Check for remaining enemies after victory
            remaining_enemies = self.world.get_enemies_in_room(self.player.current_room)
            if remaining_enemies:
                debug_log(f"Remaining enemies in room after victory: {remaining_enemies}")
                self.ui.update_output(f"\n[bold yellow]⚠️  Additional hostile entities detected! ⚠️[/bold yellow]")
                # Clear combat session first, then start new combat
                self.current_combat_session = None
                # Small delay before next combat to let victory message show
                self.check_for_enemies()
            else:
                debug_log("All enemies defeated in room")
                self.ui.update_output(f"\n[bold green]✓ Area secured - all hostile entities eliminated![/bold green]")
        
        if defeat:
            # Handle player death with game over screen
            debug_log("Player defeated in combat - showing game over screen")
            self._show_game_over_screen()
        
        if fled and enemy_id:
            # Mark enemy as fled instead of removing it completely
            fled_from_room = self.player.current_room
            self.world.mark_enemy_as_fled(enemy_id, fled_from_room)
            
            # Force player back to previous room when fleeing
            if self.player.previous_room:
                debug_log(f"Player fled from {fled_from_room} back to {self.player.previous_room}")
                self.ui.update_output(f"[bold magenta]You were forced back to {self.player.previous_room}![/bold magenta]")
                
                # Move player to previous room
                self.player.move_to(self.player.previous_room)
                
                # Emit room changed event for UI updates
                event_bus.emit_event(
                    EventType.ROOM_CHANGED,
                    {"player": self.player, "from_room": fled_from_room, "to_room": self.player.current_room},
                    "CommandHandler"
                )
                
                # Show new room info
                self.pwd()
                self.ls()
            else:
                debug_log("Player fled but no previous room available")
                self.ui.update_output("[yellow]You fled but couldn't find your way back...[/yellow]")
        
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
            class_restriction = self._get_class_restriction_text(weapon)
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
        debug_log(f"Checking for enemies in room: {current_room}")
        
        # Don't start new combat if already in combat
        if self.current_combat_session and self.current_combat_session.awaiting_action:
            debug_log("Already in combat, skipping enemy check")
            return
            
        enemies = self.world.get_enemies_in_room(current_room)
        debug_log(f"Enemies found in {current_room}: {enemies}")
        
        if enemies:
            enemy_id = enemies[0]  # For now, fight the first enemy
            debug_log(f"Attempting to get enemy data for: {enemy_id}")
            enemy = self.world.get_enemy(enemy_id, self.player.player_class)
            debug_log(f"Enemy data retrieved: {enemy is not None}")
            
            if enemy:
                enemy_name = enemy.get('name', enemy_id)
                enemy_description = enemy.get('description', 'A menacing presence')
                debug_log(f"Starting combat with {enemy_name} ({enemy_id})")
                
                # Enhanced enemy detection notice
                detection_message = f"""
[bold red]⚠️  HOSTILE ENTITY DETECTED  ⚠️[/bold red]

[red]System Alert:[/red] A corrupted process has manifested in this sector!

[bold yellow]Entity:[/bold yellow] [bold red]{enemy_name}[/bold red]
[bold yellow]Status:[/bold yellow] {enemy_description}

[bold red]BATTLE INITIATED![/bold red]
[dim]Prepare your commands - this corruption must be purged![/dim]
"""
                self.ui.update_output(detection_message)
                self.combat(enemy_id, enemy)
            else:
                debug_log(f"ERROR: Enemy data not found for {enemy_id}")
                self.ui.update_output(f"[bold red]System error: Cannot load enemy data for {enemy_id}[/bold red]")
        else:
            debug_log(f"No enemies found in room {current_room}")

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
            enemy = self.world.get_enemy(enemy_id, self.player.player_class)
            if enemy:
                self.world.enemy_locations[enemy_id] = room_id
                if room_id == self.player.current_room:
                    self.ui.update_output(f"[bold red]{enemy.get('name', enemy_id)} has appeared![/bold red]")
                    self.check_for_enemies()

    def _show_game_over_screen(self):
        """Show ASCII game over screen with options."""
        game_over_ascii = """
[bold red]
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ██████╗  █████╗ ███╗   ███╗███████╗     ██████╗ ██╗   ██╗███████╗██████╗ ║
║  ██╔════╝ ██╔══██╗████╗ ████║██╔════╝    ██╔═══██╗██║   ██║██╔════╝██╔══██╗║
║  ██║  ███╗███████║██╔████╔██║█████╗      ██║   ██║██║   ██║█████╗  ██████╔╝║
║  ██║   ██║██╔══██║██║╚██╔╝██║██╔══╝      ██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗║
║  ╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗    ╚██████╔╝ ╚████╔╝ ███████╗██║  ██║║
║   ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝     ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝║
║                                                                  ║
║                    >>> SEGMENTATION FAULT <<<                    ║
║                                                                  ║
║              Your essence scatters through broken memory.        ║
║           The filesystem quakes as the Daemon Overlord          ║
║                      grows stronger...                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
[/bold red]

[dim]The digital void echoes with the sound of your defeat.[/dim]
[italic cyan]Even the greatest sysadmins must sometimes face corruption...[/italic cyan]

[bold white]Options:[/bold white]
  [bold green]r[/bold green] - Restart from your last save
  [bold yellow]n[/bold yellow] - Start a new game
  [bold red]q[/bold red] - Quit to shell

[bold white]What would you like to do?[/bold white] """

        self.ui.update_output(game_over_ascii)
        
        # Set up game over mode to handle player input
        self._in_game_over_mode = True
        debug_log("Game over screen displayed, waiting for player choice")

    def _handle_game_over_choice(self, choice):
        """Handle player choice from game over screen."""
        choice = choice.lower().strip()
        
        if choice == 'r':
            # Restart from last save
            debug_log("Player chose to restart from last save")
            self.ui.update_output("\n[bold cyan]Attempting to restore from backup...[/bold cyan]")
            
            # Try to load the most recent save
            try:
                from src.save import load_most_recent_save
                save_data = load_most_recent_save()
                if save_data:
                    # Import GameEngine to restart properly
                    from src.game_engine import GameEngine
                    self.ui.update_output("[green]Backup found! Restoring system state...[/green]")
                    self._in_game_over_mode = False
                    # Signal to restart with save data
                    self.ui.update_output("[bold green]System restored from backup![/bold green]\n")
                    return "restart_from_save"
                else:
                    self.ui.update_output("[bold red]No backup found. Starting new game instead...[/bold red]")
                    return self._handle_game_over_choice('n')
            except Exception as e:
                debug_log(f"Failed to load save: {e}")
                self.ui.update_output("[bold red]Backup corrupted. Starting new game instead...[/bold red]")
                return self._handle_game_over_choice('n')
                
        elif choice == 'n':
            # Start new game
            debug_log("Player chose to start new game")
            self.ui.update_output("\n[bold cyan]Initializing new system...[/bold cyan]")
            self.ui.update_output("[green]Creating fresh filesystem...[/green]")
            self._in_game_over_mode = False
            return "start_new_game"
            
        elif choice == 'q':
            # Quit game
            debug_log("Player chose to quit")
            self.ui.update_output("\n[dim]System shutdown initiated...[/dim]")
            self.ui.update_output("[bold red]Connection terminated.[/bold red]")
            return "quit"
            
        else:
            # Invalid choice
            self.ui.update_output(f"\n[bold red]Invalid option: '{choice}'[/bold red]")
            self.ui.update_output("[bold white]Please choose:[/bold white] [green]r[/green] (restart), [yellow]n[/yellow] (new game), or [red]q[/red] (quit)")
            return None

    def game_over(self):
        """Handle game over state"""
        debug_log("game_over() called - showing game over screen")
        self._show_game_over_screen()

    def check_game_completion(self):
        """Check if the player has completed the game"""
        if self.player.current_room == "core" and "daemon_overlord.sys" not in self.world.get_enemies_in_room("core"):
            if self.player.has_item("backup.bak"):
                self.win_game()

    def win_game(self):
        """Handle win state"""
        victory_message = """
[bold green]>>> PROCESS TERMINATED <<<[/bold green]
The Daemon Overlord collapses into fragments of corrupted code.
Silence falls across the filesystem.
Directories heal, symlinks reconnect, and lost files whisper back into being.

You have restored the root.
The machine breathes once more.
The spirits sing your name in system logs eternal.

[cyan]>>> SYSTEM RESTORED <<<[/cyan]
Filesystems mount clean. Permissions reset.
A chorus of processes awaken, singing in harmony.

The haunted machine is whole again.
And you, spirit, are free.

[bold]THANK YOU FOR PLAYING[/bold]
        """
        self.ui.update_output(victory_message)
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

    def _resolve_item_shortcut(self, item_input, location="room"):
        """Resolve item shortcuts and partial matches to actual item IDs."""
        # Define common shortcuts
        shortcuts = {
            # Health potions
            "hp": ["health_potion_minor", "health_potion_major"],
            "health": ["health_potion_minor", "health_potion_major"], 
            "potion": ["health_potion_minor", "health_potion_major", "strength_potion", "swiftness_tonic", "fortitude_elixir"],
            "heal": ["health_potion_minor", "health_potion_major"],
            
            # Weapons  
            "staff": ["echo_staff"],
            "shield": ["protocol_shield"],
            "blaster": ["byte_blaster"],
            
            # Other consumables
            "strength": ["strength_potion"],
            "swift": ["swiftness_tonic"],
            "fortitude": ["fortitude_elixir"],
            "focus": ["focus_draught"]
        }
        
        # Get available items based on location
        if location == "room":
            current_room = self.player.current_room
            available_items = self.world.get_items_in_room(current_room)
        elif location == "inventory":
            available_items = list(self.player.inventory.keys())
        else:
            available_items = []
        
        debug_log(f"Resolving item shortcut '{item_input}' in {location}, available items: {available_items}")
        
        # First, check if it's an exact match
        if item_input in available_items:
            return item_input
        
        # Check shortcuts
        if item_input.lower() in shortcuts:
            shortcut_items = shortcuts[item_input.lower()]
            for shortcut_item in shortcut_items:
                if shortcut_item in available_items:
                    debug_log(f"Shortcut '{item_input}' resolved to '{shortcut_item}'")
                    return shortcut_item
        
        # Check partial matches (starts with the input)
        partial_matches = [item for item in available_items if item.lower().startswith(item_input.lower())]
        if len(partial_matches) == 1:
            debug_log(f"Partial match '{item_input}' resolved to '{partial_matches[0]}'")
            return partial_matches[0]
        elif len(partial_matches) > 1:
            debug_log(f"Multiple partial matches for '{item_input}': {partial_matches}")
            # For health potions, prefer minor over major
            if "health_potion_minor" in partial_matches:
                return "health_potion_minor"
            return partial_matches[0]  # Return first match as fallback
        
        # Check if input contains key words that match item names
        for available_item in available_items:
            if item_input.lower() in available_item.lower():
                debug_log(f"Substring match '{item_input}' found in '{available_item}'")
                return available_item
        
        debug_log(f"No match found for '{item_input}'")
        return None

    def _get_class_restriction_text(self, item):
        """Get the class restriction text for display in error messages."""
        # Check class_restriction field first
        if "class_restriction" in item:
            class_restriction = item["class_restriction"]
            if isinstance(class_restriction, list):
                return " or ".join(class_restriction)
            return str(class_restriction)
        
        # Check allowed_classes field
        if "allowed_classes" in item:
            allowed_classes = item["allowed_classes"]
            if isinstance(allowed_classes, list):
                return " or ".join(allowed_classes)
            return str(allowed_classes)
            
        return "unknown"

    def save_game(self):
        """Save the current game state."""
        try:
            from src.save import save_manager
            
            # Get current world state
            world_state = self.world.get_state()
            
            # Save the game
            save_path = save_manager.save_game(self.player, world_state)
            
            self.ui.update_output(f"[bold green]✓ Game saved successfully![/bold green]")
            self.ui.update_output(f"[dim]Save location: {save_path}[/dim]")
            debug_log(f"Game saved to: {save_path}")
            
        except Exception as e:
            debug_log(f"Failed to save game: {e}")
            self.ui.update_output(f"[bold red]✗ Failed to save game: {e}[/bold red]")

    def quit_game(self):
        """Handle quit and exit commands with optional save."""
        # Check if player has made progress (not at starting health/room)
        has_progress = (
            self.player.health != self.player.max_health or 
            self.player.current_room != "home_grove" or 
            len(self.player.inventory) > 0 or
            self.player.equipped_weapon is not None
        )
        
        if has_progress:
            self.ui.update_output("[bold yellow]You have unsaved progress![/bold yellow]")
            self.ui.update_output("Would you like to save before quitting?")
            self.ui.update_output("[bold white]Options:[/bold white] [green]y[/green] (save & quit), [yellow]n[/yellow] (quit without saving), [red]c[/red] (cancel)")
            
            # Set quit confirmation mode
            self._in_quit_confirmation = True
        else:
            # No significant progress, just quit
            self._perform_quit()

    def _handle_quit_confirmation(self, choice):
        """Handle player's choice in quit confirmation."""
        choice = choice.lower().strip()
        
        if choice == 'y':
            # Save and quit
            self.ui.update_output("[cyan]Saving game...[/cyan]")
            self.save_game()
            self._perform_quit()
            
        elif choice == 'n':
            # Quit without saving
            self.ui.update_output("[yellow]Quitting without saving...[/yellow]")
            self._perform_quit()
            
        elif choice == 'c':
            # Cancel quit
            self.ui.update_output("[green]Quit cancelled. Continue your adventure![/green]")
            self._in_quit_confirmation = False
            
        else:
            # Invalid choice
            self.ui.update_output(f"[bold red]Invalid option: '{choice}'[/bold red]")
            self.ui.update_output("[bold white]Please choose:[/bold white] [green]y[/green] (save & quit), [yellow]n[/yellow] (quit without saving), [red]c[/red] (cancel)")

    def _perform_quit(self):
        """Actually quit the game."""
        self.ui.update_output("[yellow]Goodbye! Thanks for playing The Haunted Filesystem.[/yellow]")
        self.ui.update_output("[dim]The system spirits fade back into the digital void...[/dim]")
        exit(0) 