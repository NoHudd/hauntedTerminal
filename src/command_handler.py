#!/usr/bin/env python3
import os
import re
import random
import logging
from rich.text import Text
from src.combat import combat_system, CombatSession
from src.events import event_bus, EventType
from src.game_states import GameState
from src.state_manager import state_manager
from src.ui.view_builder import ViewBuilder
from utils.debug_tools import debug_log
from utils.typewriter import TypewriterPresets, create_typewriter_output_func
from utils.particle_animation import GameOverAnimation

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

        # Subscribe to enemy defeated event to remove enemies from room
        event_bus.subscribe(EventType.ENEMY_DEFEATED, self._on_enemy_defeated)
        
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
            "/usr/share": "usr_share_games",
            "/usr/share/games": "usr_share_games",
            "/usr/share/games/cowsay": "cowsay_secret",
            "/cowsay": "cowsay_secret",
            "/opt": "opt_mage_tower",
            "/opt/tower": "opt_mage_tower",
            "/opt/mage_tower": "opt_mage_tower",
            "/srv": "srv_warrior_tomb",
            "/srv/tomb": "srv_warrior_tomb",
            "/srv/warrior_tomb": "srv_warrior_tomb",
            "/tmp": "tmp_hidden_chamber",
            "/tmp/chamber": "tmp_hidden_chamber",
            "/tmp/hidden_chamber": "tmp_hidden_chamber",
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
            "share": "usr_share_games",
            "games": "usr_share_games",
            "cowsay": "cowsay_secret",
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
            "journal": self.show_journal,
            "save": self.save_game,
            "quit": self.quit_game,
            "exit": self.quit_game
        }
        
        # Commands that accept an argument (required or optional)
        self.commands_with_args = {
            "cd", "cat", "take", "drop", "use", "equip", "examine", "talk", "attack",
            "ls", "find", "ps"
        }
        
        debug_log(f"Registered {len(self.commands)} commands")
    
    _EVENT_HANDLERS = [
        (EventType.ROOM_ENTERED, "_on_room_entered"),
        (EventType.ALL_ENEMIES_DEFEATED, "_on_all_enemies_defeated"),
        (EventType.ROOM_CHANGED, "_on_room_changed_for_npc"),
        (EventType.COMBAT_ENDED, "_on_combat_ended_tutorial"),
        (EventType.TUTORIAL_SELECTION_MODE_USED, "_on_tutorial_selection_mode_used"),
    ]

    def setup_event_subscriptions(self):
        """Set up event subscriptions for the command handler."""
        for event_type, handler_name in self._EVENT_HANDLERS:
            event_bus.subscribe(event_type, getattr(self, handler_name))
        debug_log("CommandHandler event subscriptions set up")

    def cleanup_event_subscriptions(self):
        """Clean up event subscriptions for the command handler."""
        for event_type, handler_name in self._EVENT_HANDLERS:
            event_bus.unsubscribe(event_type, getattr(self, handler_name))
        debug_log("CommandHandler event subscriptions cleaned up")
    
    def _on_room_entered(self, event):
        """Handle room entered event to respawn fled enemies."""
        # Get room_id from player's current room (event contains RoomView dict, not room_id)
        room_id = self.player.current_room
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
    
    def _on_combat_ended_tutorial(self, event):
        """Handle combat end for tutorial post-combat hints (Step 5 post-combat + Step 6)."""
        ts = self.player.tutorial_state
        if ts.get("completed", False):
            return
        if ts.get("combat_typed", False) and not ts.get("navigation_ls", False):
            if event.data.get("victory", False):
                self.show_tutorial_hint("step5_postcombat")
                self.show_tutorial_hint("step6")

    def _on_tutorial_selection_mode_used(self, event):
        """Handle tutorial selection mode used event (TAB pressed during tutorial combat)."""
        ts = self.player.tutorial_state
        if ts.get("combat_typed", False) and not ts.get("combat_selection", False):
            ts["combat_selection"] = True
            debug_log("Tutorial: combat_selection gate passed (TAB used in combat)")

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
            },
            "usr_share_games": {
                "cowsay_secret": "The Bovine Sanctuary (hidden cowsay temple)"
            },
            "root": {
                "archive": "The dusty Archive (forgotten data)"
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

    def _show_error(self, message: str, log_message: str = None):
        """Display error to UI and log it for debugging."""
        self.ui.update_output(message)
        clean_message = re.sub(r'\[.*?\]', '', log_message or message)
        logger.error(f"Command error: {clean_message}")

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
        """Show gated tutorial hints. Each step has a single clear instruction."""
        if self.player.tutorial_state.get("completed", False):
            return

        player_name = self.player.name if hasattr(self.player, 'name') and self.player.name else "spirit"

        # Determine starter weapon name for dynamic hints
        if item_name:
            weapon_name = item_name
        else:
            class_starter_weapons = {
                "guardian": "segfault_shield",
                "weaver": "null_pointer",
                "shaman": "daemon_whisper"
            }
            weapon_name = class_starter_weapons.get(self.player.player_class, "segfault_shield")

        hints = {
            # Step 0: skip summary (player chose to skip)
            "skip_summary": (
                "[bold green]ECHO>[/bold green] Got it. Quick reference: "
                "[bold]ls[/bold] scans a room, [bold]take/equip[/bold] grab and ready items, "
                "[bold]attack[/bold] fights enemies. In combat, press [bold]TAB[/bold] to enter "
                "Selection Mode then [bold]1-9[/bold] to attack. [bold]flee[/bold] escapes a fight. "
                "[bold]help[/bold] if stuck. Good luck."
            ),
            # Step 1: welcome + ls instruction
            "step1": (
                "[bold green]ECHO>[/bold green] You're in /home — a stable part of the filesystem. "
                "The rest is corrupted and needs clearing. Let's start simple. "
                "Type: [bold]ls[/bold] and press Enter to see what's here."
            ),
            # Step 2: take weapon instruction
            "step2": (
                f"[bold green]ECHO>[/bold green] Good — that's everything in this directory. "
                f"See that weapon? Type: [bold]take {weapon_name}[/bold] to pick it up. "
                f"Items you carry appear in the Inventory panel on the right."
            ),
            # Step 3: equip instruction
            "step3": (
                f"[bold green]ECHO>[/bold green] You're carrying it, but it's not active yet. "
                f"Type: [bold]equip {weapon_name}[/bold] to ready it. "
                f"Equipping means it'll be used in combat."
            ),
            # Step 4: combat - typed attack instruction
            "step4": (
                "[bold green]ECHO>[/bold green] A corrupted process just spawned — this is combat. "
                "Type: [bold]attack[/bold] to strike it. "
                "Or press [bold]TAB[/bold] to enter Selection Mode and pick an attack with [bold]1-9[/bold]."
            ),
            # Step 5: combat - Selection Mode instruction (fires after first typed attack)
            "step5": (
                "[bold green]ECHO>[/bold green] Nice hit. One more should finish it. "
                "Try this: press [bold]TAB[/bold] to enter Selection Mode, "
                "then press [bold]1[/bold] to attack without typing anything. "
                "TAB switches you back to typing whenever you need it."
            ),
            # Step 5 post-combat informational (no gate)
            "step5_postcombat": (
                "[bold green]ECHO>[/bold green] You won. Two more things to know: "
                "[bold]use [item][/bold] uses a consumable mid-fight, "
                "and [bold]flee[/bold] lets you escape if things go badly."
            ),
            # Step 6: navigation ls instruction
            "step6": (
                "[bold green]ECHO>[/bold green] Let's move. "
                "Type: [bold]ls[/bold] again — exits show at the bottom of the room listing."
            ),
            # Step 6b: navigation move instruction
            "step6b": (
                "[bold green]ECHO>[/bold green] See those paths? "
                "Type one — like [bold]/var[/bold] — and you'll move there. "
                "That's how the whole filesystem works."
            ),
            # Step 7: tutorial complete cheat-sheet
            "completed": (
                f"[bold green]ECHO> Tutorial complete, {player_name}.[/bold green]\n"
                f"Quick reminder:\n"
                f"  • [bold]ls[/bold] — scan a room\n"
                f"  • [bold]take / equip[/bold] — grab and ready items\n"
                f"  • [bold]attack[/bold] or TAB + number — fight enemies\n"
                f"  • [bold]flee[/bold] — escape a fight\n"
                f"  • [bold]help[/bold] — if you get stuck\n"
                f"Good luck out there."
            ),
        }

        if hint_type in hints:
            self.ui.update_output(hints[hint_type])

            if hint_type == "completed":
                self.player.tutorial_state["completed"] = True
    
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
                arg = args[0] if args else ""
                debug_log(f"Executing command '{cmd}' with arg '{arg}'")
                self.commands[cmd](arg)
            else:
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
        - [cyan]keys[/cyan]: Show key progression system
        - [cyan]take [item][/cyan]: Add an item to your inventory
        - [cyan]drop [item][/cyan]: Remove an item from your inventory
        - [cyan]use [item][/cyan]: Use consumables (potions, scrolls)
        - [cyan]equip [weapon][/cyan]: Equip a weapon for combat
        - [cyan]talk [npc][/cyan]: Talk to an NPC
        - [cyan]attack [enemy][/cyan]: Attack an enemy
        - [cyan]ps[/cyan]: Show running processes
        - [cyan]inventory[/cyan]: Show detailed inventory with rarities
        - [cyan]journal[/cyan]: Show story memories you've restored
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
- [yellow]hp[/yellow] or [yellow]heal[/yellow] → health_packet
- [yellow]health[/yellow] or [yellow]packet[/yellow] → health_packet
- [yellow]cache[/yellow] → stable_cache
- [yellow]buffer[/yellow] → overflowing_buffer

[bold]Weapons:[/bold]
- [yellow]shield[/yellow] → segfault_shield (Guardian)
- [yellow]pointer[/yellow] → null_pointer (Weaver)
- [yellow]whisper[/yellow] → daemon_whisper (Shaman)

[bold]Other Items:[/bold]
- [yellow]backup[/yellow] → legacy_backup
- [yellow]seed[/yellow] → sudo_seed

[bold]Partial Matching:[/bold]
You can type just the beginning of an item name:
- [yellow]health_p[/yellow] → health_packet
- [yellow]segfault[/yellow] → segfault_shield

[bold cyan]Usage Examples:[/bold cyan]
- [green]take hp[/green] (instead of take health_packet)
- [green]use heal[/green] (instead of use health_packet)
- [green]take shield[/green] (instead of take segfault_shield)"""
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
        room_name = room.get("name", room_id)
        title = Text(f"{room_name}", style="bold white on dark_blue")
        description = Text(room.get("description", "No description available."))

        # Get atmospheric enhancement
        atmospheric = self.get_atmospheric_description(room_id)

        # Create content with title and atmospheric description
        location_content = f"[bold]{title}[/bold]\n\n{description}"
        if atmospheric:
            location_content += f"\n\n{atmospheric}"
        
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

        # Healing items - check combat_effects.player_heal first (new format)
        if "combat_effects" in item and "player_heal" in item["combat_effects"]:
            effect = f"+{item['combat_effects']['player_heal']} HP"

        # Also check on_use.heal (old format)
        elif "on_use" in item and "heal" in item["on_use"]:
            effect = f"+{item['on_use']['heal']} HP"

        # Damage-dealing consumables
        elif "combat_effects" in item and "player_damage" in item["combat_effects"]:
            effect = f"+{item['combat_effects']['player_damage']} DMG"
        elif "on_use" in item and "damage" in item["on_use"]:
            effect = f"+{item['on_use']['damage']} DMG"

        # Status effect items
        elif "on_use" in item and "status_effect" in item["on_use"]:
            effect_name = item["on_use"]["status_effect"].get("name", "Effect")
            effect = f"Status: {effect_name}"

        # Weapons - check damage field
        elif item.get("type") == "weapon" or "weapon" in str(item.get("type", "")):
            damage = item.get("damage", 0)
            if damage > 0:
                effect = f"+{damage} DMG"

        # Upgrade items
        elif "effects" in item:
            effects = []
            if "permanent_health" in item["effects"]:
                effects.append(f"+{item['effects']['permanent_health']} HP")
            if "permanent_damage" in item["effects"]:
                effects.append(f"+{item['effects']['permanent_damage']} DMG")
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
                output.append(f" - {description}")
                # Hint for cat-only lore so players know how to interact.
                if item and item.get("type") == "lore" and not item.get("takeable", True):
                    output.append("  [dim italic](readable — try `cat`)[/dim italic]", style="cyan")
                output.append("\n")

                if item and item.get("type") == "weapon":
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

        # Tutorial gating for list_directory
        ts = self.player.tutorial_state
        if not ts.get("completed", False):
            # Step 1 gate: first ls
            if not ts.get("first_ls", False):
                ts["first_ls"] = True
                # Step 2 hint fires if weapon visible in this ls
                if weapon_found:
                    ts["found_weapon"] = True
                    # Find weapon id for hint
                    weapon_item_id = None
                    for item_id in items:
                        item = self.world.get_item(item_id)
                        if item and item.get("type") == "weapon":
                            weapon_item_id = item_id
                            break
                    self.show_tutorial_hint("step2", weapon_item_id)
            # Step 6 gate: navigation ls (post-combat)
            elif ts.get("combat_typed", False) and not ts.get("navigation_ls", False):
                ts["navigation_ls"] = True
                self.show_tutorial_hint("step6b")

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
            self._show_error(f"[bold red]That path doesn't appear to exist.[/bold red]")
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
                # Normalize unlocks through room_aliases so path-format entries ("/opt/mage_tower")
                # match resolved room IDs ("opt_mage_tower").
                resolved_unlocks = [self.room_aliases.get(r.lower(), r) for r in key_item.get("unlocks", [])]
                if "unlocks" in key_item and directory in resolved_unlocks:
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
            self._show_error(f"[bold red]{reason}[/bold red]")

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

        # Get the room name for a friendly entry message
        new_room = self.world.get_room(directory)
        room_name = new_room.get('name', directory) if new_room else directory
        self.ui.update_output(f"[bold cyan]Entering {room_name}...[/bold cyan]")
        debug_log(f"Successfully moved player to {directory}")

        # Build room view for the new room and emit room entered event
        room_view = ViewBuilder.build_room_view(self.world, directory)

        event_bus.emit_event(
            EventType.ROOM_ENTERED,
            {"room": room_view.to_dict(), "player_name": self.player.name},
            "CommandHandler"
        )
        
        # Display the new location
        self.display_location()

        # Step 6 navigation gate → tutorial complete
        ts = self.player.tutorial_state
        if not ts.get("completed", False) and ts.get("navigation_ls", False):
            if not ts.get("navigation_moved", False):
                ts["navigation_moved"] = True
                self.show_tutorial_hint("completed")

    def read_file(self, filename):
        """Read the contents of a file (item)"""
        if not filename:
            self._show_error("[bold red]No file specified. Use 'cat [filename]'[/bold red]")
            return

        # Check if file is in the current room
        current_room = self.player.current_room
        items_in_room = self.world.get_items_in_room(current_room)

        # Try to find item by ID or name (case-insensitive, with/without underscores/dots)
        item_id = self._find_item_by_name_or_id(filename, items_in_room)

        if item_id:
            # Item is in the room
            item = self.world.get_item(item_id)
            if item:
                item_name = item.get("name", item_id)
                content = item.get("content", item.get("description", "This file appears to be empty or corrupted."))
                file_content = f"[bold]{item_name}[/bold]\n\n{content}"
                self.ui.update_output(file_content)

                # Execute any special effects defined for this item
                if "on_read" in item:
                    self.execute_effect(item["on_read"])
                self._trigger_story_flag(item)
            else:
                self._show_error(f"[bold red]Error: Could not read {filename}[/bold red]")
        elif self.player.has_item(filename) or self._find_item_in_inventory_by_name(filename):
            # Item is in the player's inventory - find by name or ID
            item_id_inv = self._find_item_in_inventory_by_name(filename) or filename
            item = self.player.get_item_from_inventory(item_id_inv)
            if item:
                item_name = item.get("name", item_id_inv)
                content = item.get("content", item.get("description", "This file appears to be empty or corrupted."))
                file_content = f"[bold]{item_name}[/bold]\n\n{content}"
                self.ui.update_output(file_content)

                # Execute any special effects defined for this item
                if "on_read" in item:
                    self.execute_effect(item["on_read"])
                self._trigger_story_flag(item)
            else:
                self._show_error(f"[bold red]Error: Could not read {filename}[/bold red]")
        else:
            self._show_error(f"[bold red]Cannot find {filename} in this directory or your inventory.[/bold red]")

    @staticmethod
    def _normalize_item_name(s: str) -> str:
        return s.lower().replace(".", "_").replace("-", "_")

    def _find_item_in_list(self, search_term, item_ids, get_item_fn):
        """Find an item ID by name or ID match (fuzzy)."""
        target = self._normalize_item_name(search_term)
        for item_id in item_ids:
            if self._normalize_item_name(item_id) == target:
                return item_id
            item_data = get_item_fn(item_id)
            if item_data and self._normalize_item_name(item_data.get("name", "")) == target:
                return item_id
        return None

    def _find_item_by_name_or_id(self, search_term, item_list):
        """Find item ID in a room's item list by name or ID."""
        return self._find_item_in_list(search_term, item_list, self.world.get_item)

    def _find_item_in_inventory_by_name(self, search_term):
        """Find item in player inventory by name or ID."""
        return self._find_item_in_list(
            search_term, self.player.inventory, self.player.get_item_from_inventory
        )
    
    def take_item(self, item_id):
        """Pick up an item and add it to inventory"""
        if not item_id:
            debug_log("take command called with no item specified")
            self._show_error("[bold red]No item specified. Use 'take [item]'[/bold red]")
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
            self._show_error(f"[bold red]Cannot find {item_id} in this directory.[/bold red]")
            return

        debug_log(f"Player attempting to take item: {actual_item_id} (from input: {item_id})")
        items_in_room = self.world.get_items_in_room(current_room)

        if actual_item_id not in items_in_room:
            debug_log(f"Item {actual_item_id} not found in room {current_room}")
            self._show_error(f"[bold red]Cannot find {item_id} in this directory.[/bold red]")
            return

        # Get item data
        item = self.world.get_item(actual_item_id)
        if not item:
            debug_log(f"Error: Item data not found for {actual_item_id}")
            self._show_error(f"[bold red]Error: Item data not found for {item_id}[/bold red]")
            return

        # Check if item is takeable
        if not item.get("takeable", True):
            debug_log(f"Item {actual_item_id} is not takeable")
            self._show_error(f"[bold red]You cannot take {item_id}.[/bold red]")
            return

        # Check class restrictions
        if not self.player.can_use_item(item):
            class_restriction = self._get_class_restriction_text(item)
            debug_log(f"Item {actual_item_id} is class-restricted, player class {self.player.player_class} not allowed")
            self._show_error(f"[bold red]Only {class_restriction} spirits can wield {item_id}. Your essence is incompatible.[/bold red]")
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

            # Build inventory view for updated inventory and emit event
            inventory_view = ViewBuilder.build_inventory_view(self.player)

            event_bus.emit_event(
                EventType.PLAYER_INVENTORY_CHANGED,
                inventory_view.to_dict(),
                "CommandHandler"
            )
            
            # Execute any special effects defined for taking this item
            if "on_take" in item:
                debug_log(f"Executing on_take effect for {item_id}")
                self.execute_effect(item["on_take"])
            
            # Tutorial: took weapon
            if not self.player.tutorial_state.get("took_weapon", False) and item.get("type") == "weapon":
                self.player.tutorial_state["took_weapon"] = True
                self.show_tutorial_hint("step3", actual_item_id)
        else:
            debug_log(f"Failed to add {actual_item_id} to inventory")
            self._show_error(f"[bold red]Could not add {item_id} to inventory.[/bold red]")
    
    def drop_item(self, item_id):
        """Drop an item from inventory into the current room"""
        if not item_id:
            self._show_error("[bold red]No item specified. Use 'drop [item]'[/bold red]")
            return

        if not self.player.has_item(item_id):
            self._show_error(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return

        # Get item data
        item = self.player.get_item_from_inventory(item_id)

        # Check if item is droppable
        if item.get("droppable", True) == False:
            self._show_error(f"[bold red]You cannot drop {item_id}. It's too important.[/bold red]")
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
            self._show_error(f"[bold red]Could not drop {item_id}.[/bold red]")
    
    def use_item(self, item_id):
        """Use an item from inventory"""
        if not item_id:
            debug_log("use command called with no item specified")
            self._show_error("[bold red]No item specified. Use 'use [item]'[/bold red]")
            return

        # Try to resolve shortcuts and partial matches for inventory items
        actual_item_id = self._resolve_item_shortcut(item_id, "inventory")
        if not actual_item_id:
            debug_log(f"Item {item_id} not found in inventory after shortcut resolution")
            self._show_error(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
            return

        debug_log(f"Player attempting to use item: {actual_item_id} (from input: {item_id})")

        if not self.player.has_item(actual_item_id):
            debug_log(f"Player doesn't have item {actual_item_id} in inventory")
            self._show_error(f"[bold red]You don't have {item_id} in your inventory.[/bold red]")
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
            self._show_error(f"[bold red]You cannot use {item_id}.[/bold red]")
            return

        # Check class restrictions
        if not self.player.can_use_item(item):
            class_restriction = self._get_class_restriction_text(item)
            debug_log(f"Item {actual_item_id} has class restriction: {class_restriction}, player is: {self.player.player_class}")
            self._show_error(f"[bold red]This item can only be used by {class_restriction} class.[/bold red]")
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
            if self._handle_consumable_item(actual_item_id, item) is False:
                return  # Item had no effect — don't consume it
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

        # Check if the key unlocks a room in the current location.
        # Normalize path-format entries ("/opt/mage_tower") to room IDs ("opt_mage_tower")
        # via room_aliases so YAML paths and room IDs are interchangeable.
        current_room_id = self.player.current_room
        exits = self.world.get_exits(current_room_id)
        resolved_unlocks = [self.room_aliases.get(r.lower(), r) for r in unlocks]

        unlocked_something = False
        for room_to_unlock in resolved_unlocks:
            if room_to_unlock in exits:
                self.world.unlock_room(room_to_unlock)
                self.ui.update_output(f"[yellow]You hear a click. The path to {room_to_unlock} is now open.[/yellow]")
                unlocked_something = True

        if not unlocked_something:
            self.ui.update_output(f"You can't find a lock that [green]{item_id}[/green] fits here.")
    
    def _show_damage_change(self, old_damage: int, new_damage: int):
        """Display damage comparison after equipping a weapon."""
        delta = new_damage - old_damage
        if delta > 0:
            self.ui.update_output(f"[green]Your total damage increased by {delta} (from {old_damage} to {new_damage}).[/green]")
        elif delta < 0:
            self.ui.update_output(f"[red]Your total damage decreased by {abs(delta)} (from {old_damage} to {new_damage}).[/red]")
        else:
            self.ui.update_output(f"[yellow]Your total damage remains at {new_damage}.[/yellow]")

    def _handle_weapon_item(self, item_id, item):
        """Handle equipping a weapon"""
        if not self.player.can_use_item(item):
            self._show_error(f"[bold red]You cannot equip {item_id}.[/bold red]")
            return

        old_weapon_id = self.player.equipped_weapon
        old_damage = self.player.calculate_damage()

        self.player.equip_weapon(item_id, item)
        self.ui.update_output(f"You have equipped [green]{item_id}[/green].")

        if old_weapon_id and old_weapon_id != item_id and old_weapon_id in self.player.inventory:
            self.player.remove_from_inventory(old_weapon_id)
            self.ui.update_output(f"Your old weapon ({old_weapon_id}) was removed from inventory.")

        self._show_damage_change(old_damage, self.player.calculate_damage())

        if not self.player.tutorial_state.get("equipped_weapon", False):
            self.player.tutorial_state["equipped_weapon"] = True
            self.world.spawn_tutorial_enemy("home_grove")
            self.show_tutorial_hint("step4")
            self.check_for_enemies()
    
    def _handle_lore_item(self, item_id, item):
        """Handle reading a lore item"""
        content = item.get("content", "This file appears to be empty or corrupted.")
        name = item.get("name", item_id)
        self.ui.update_output(f"[bold cyan]── {name} ──[/bold cyan]\n{content}")
        if "on_read" in item:
            self.execute_effect(item["on_read"])
        self._trigger_story_flag(item)

    # Human-readable descriptions for story flags shown in journal/autosave feedback.
    STORY_FLAG_TITLES = {
        "identity_retrieved":   "Identity Retrieved",
        "typo_discovered":      "The Creator's Typo",
        "sudo_trial_complete":  "Sudo Trial Complete",
        "mirror_confronted":    "Mirror Confronted",
        "sudo_quest_active":    "Sudo Quest Active",
        "bovine_encountered":   "Bovine Sanctuary Found",
        "milk_claimed":         "Milk of Motherboard Claimed",
        "ending_chosen":        "Ending Chosen",
    }

    STORY_FLAG_DESCRIPTIONS = {
        "identity_retrieved":  "You read your own .bash_profile and remembered who you were.",
        "typo_discovered":     "The system_err.log revealed: the apocalypse was caused by a typo.",
        "sudo_trial_complete": "You proved worthy of sudo privileges.",
        "mirror_confronted":   "You faced your reflection in the Mirror Sector.",
        "sudo_quest_active":   "The sudo quest is in progress.",
        "bovine_encountered":  "You entered the hidden Bovine Sanctuary.",
        "milk_claimed":        "You claimed the legendary Milk of Motherboard.",
        "ending_chosen":       "You chose your ending.",
    }

    def _trigger_story_flag(self, item):
        """Set the item's story_flag on the player, show feedback, and auto-save."""
        flag = item.get("story_flag")
        if not flag:
            return
        if self.player.get_story_flag(flag):
            return

        self.player.set_story_flag(flag, True)
        title = self.STORY_FLAG_TITLES.get(flag, flag.replace("_", " ").title())
        self.ui.update_output(
            f"\n[bold magenta]✦ Memory restored: {title} ✦[/bold magenta]\n"
            f"[dim]Saving progress...[/dim]"
        )

        # Auto-save: story beats act as save points.
        try:
            from src.save import save_manager
            world_state = self.world.get_state()
            save_manager.save_game(self.player, world_state)
            self.ui.update_output("[dim green]✓ Progress saved.[/dim green]")
        except Exception as e:
            debug_log(f"Auto-save after story flag {flag} failed: {e}")
            self.ui.update_output(f"[dim yellow]⚠ Auto-save failed: {e}[/dim yellow]")

    def show_journal(self):
        """Display story progression — list of discovered flags with descriptions."""
        flags = self.player.story_flags or {}
        # Filter to flags that are truthy (True or non-empty value for ending_chosen)
        discovered = [k for k, v in flags.items() if v]

        output = Text()
        output.append("📖 JOURNAL\n", style="bold cyan")
        output.append("=" * 50 + "\n", style="dim")

        if not discovered:
            output.append("\n[italic]No memories restored yet. Explore the filesystem and `cat` any lore files you find.[/italic]")
            self.ui.update_output(output)
            return

        for flag in discovered:
            title = self.STORY_FLAG_TITLES.get(flag, flag.replace("_", " ").title())
            desc = self.STORY_FLAG_DESCRIPTIONS.get(flag, "")
            output.append(f"\n✦ {title}\n", style="bold magenta")
            if desc:
                output.append(f"  {desc}\n", style="dim")

        total = len(self.STORY_FLAG_TITLES)
        output.append(f"\n[dim]Progress: {len(discovered)}/{total} memories restored.[/dim]")
        self.ui.update_output(output)

    def _handle_consumable_item(self, item_id, item):
        """Handle using a consumable item. Returns False if item had no effect (e.g. heal at full HP)."""
        item_name = item.get("name", item_id)
        combat_effects = item.get("combat_effects", {})
        on_use_effects = item.get("on_use", {})
        special_effects = item.get("special_effects", [])

        # Show the on_use message if present
        message = on_use_effects.get("message") if isinstance(on_use_effects, dict) else None

        # Guard: if this item only heals and the player is already at full health, refuse use.
        only_heals = "player_heal" in combat_effects and not any(
            k in combat_effects for k in ("player_heal_over_time", "player_mana_restore")
        ) and not special_effects
        if only_heals and self.player.health >= self.player.max_health:
            self.ui.update_output(f"[yellow]Your health is already full. The {item_name} was not consumed.[/yellow]")
            return False

        # Apply combat_effects (the canonical effect block for consumables)
        healed = 0
        if "player_heal" in combat_effects:
            healed = self.player.heal(combat_effects["player_heal"])

        if "player_heal_over_time" in combat_effects:
            hot_amount = combat_effects["player_heal_over_time"]
            duration = combat_effects.get("duration_turns", 3)
            self.player.add_status_effect(
                f"{item_id}_hot",
                {"type": "heal_over_time", "heal_per_turn": hot_amount // duration, "name": item_name},
                duration
            )
            if not message:
                self.ui.update_output(f"You used [green]{item_name}[/green]. Healing {hot_amount} HP over {duration} turns.")

        if "player_mana_restore" in combat_effects:
            amount = combat_effects["player_mana_restore"]
            if hasattr(self.player, "restore_mana"):
                self.player.restore_mana(amount)
            if not message:
                self.ui.update_output(f"You used [green]{item_name}[/green]. Restored {amount} mana.")

        # Apply special_effects (e.g. permanent stat boost for sudo_seed)
        for effect in special_effects:
            if effect.get("type") == "permanent_stat_boost":
                stat = effect.get("stat")
                value = effect.get("value", 0)
                if stat == "strength" and hasattr(self.player, "increase_damage"):
                    self.player.increase_damage(value)
                elif stat == "health" and hasattr(self.player, "increase_max_health"):
                    self.player.increase_max_health(value)

        # Show message or fallback
        if message:
            heal_suffix = f" ([green]+{healed} HP[/green])" if healed else ""
            self.ui.update_output(f"{message}{heal_suffix}")
        elif not combat_effects and not special_effects:
            self.ui.update_output(f"You used [green]{item_name}[/green].")

        # Legacy on_use heal field (fallback for any old-format items)
        if "heal" in on_use_effects and not healed:
            healed = self.player.heal(on_use_effects["heal"])
            self.ui.update_output(f"You used [green]{item_name}[/green] and restored {healed} health.")

        # Process status effects from on_use block
        for effect_key, effect_value in (on_use_effects.items() if isinstance(on_use_effects, dict) else []):
            if effect_key in ("heal", "message"):
                continue
            debug_log(f"Processing additional effect: {effect_key} from consumable {item_id}")
            if effect_key == "status_effect":
                effect_data = effect_value
                effect_id = effect_data.get("id", item_id + "_effect")
                effect_name = effect_data.get("name", "Unknown Effect")
                effect_duration = effect_data.get("duration", 3)
                debug_log(f"Applying status effect {effect_id} ({effect_name}) for {effect_duration} turns")
                self.player.add_status_effect(effect_id, effect_data, effect_duration)
                self.ui.update_output(f"[magenta]You gained the '{effect_name}' effect for {effect_duration} turns![/magenta]")

        # Emit stats update so UI reflects the new HP/mana
        stats_view = ViewBuilder.build_stats_view(self.player)
        event_bus.emit_event(EventType.PLAYER_STATS_CHANGED, stats_view.to_dict(), "CommandHandler")
    
    def _handle_upgrade_item(self, item_id, item):
        """Handle using an upgrade item"""
        # Process permanent stat boosts
        effects = item.get("effects", {})
        
        # Health boosts
        if "permanent_health" in effects:
            amount = effects["permanent_health"]
            new_max = self.player.increase_max_health(amount)
            self.ui.update_output(f"[bold]── Character Improvement ──[/bold]\n[green]Your maximum health permanently increased by {amount} to {new_max}![/green]")
        
        # Damage boosts
        if "permanent_damage" in effects:
            amount = effects["permanent_damage"]
            new_damage = self.player.increase_damage(amount)
            self.ui.update_output(f"[bold]── Character Improvement ──[/bold]\n[green]Your base damage permanently increased by {amount} to {new_damage}![/green]")
        
        # Process on_use effects if any
        if "on_use" in item:
            self.execute_effect(item["on_use"])
    
    def _handle_spell_item(self, item_id, item):
        """Handle using a spell item"""
        # Learn the spell
        if self.player.learn_spell(item):
            spell_name = item.get("name", "Unknown Spell")
            self.ui.update_output(f"[bold]── Spell Learned ──[/bold]\n[green]You learned the {spell_name} spell![/green]")
            
            # Apply any immediate status effects if defined
            if "status_effect" in item:
                effect_data = item["status_effect"]
                effect_id = effect_data.get("id", item_id + "_effect")
                effect_name = effect_data.get("name", spell_name + " Effect")
                effect_duration = effect_data.get("duration", 3)  # Default 3 turns
                
                # Add the status effect
                self.player.add_status_effect(effect_id, effect_data, effect_duration)
                self.ui.update_output(f"[bold]── Status Effect ──[/bold]\n[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]")
        else:
            self._show_error(f"[red]You don't have the ability to learn this spell.[/red]")
            
    def examine_item(self, item_id):
        """Examine an item in detail"""
        if not item_id:
            self._show_error("[bold red]No item specified. Use 'examine [item]'[/bold red]")
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
                self._show_error(f"[bold red]Cannot find {item_id} in this directory or your inventory.[/bold red]")
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
        
        self.ui.update_output(f"[bold cyan]── {title} ──[/bold cyan]\n{content}")

        # Execute any special effects defined for examining this item
        if "on_examine" in item:
            self.execute_effect(item["on_examine"])
    
    def talk_to_npc(self, npc_id):
        """Talk to an NPC in the current room"""
        if not npc_id:
            self._show_error("[bold red]No NPC specified. Use 'talk [npc]'[/bold red]")
            return

        current_room = self.player.current_room
        npcs_in_room = self.world.get_npcs_in_room(current_room)

        if npc_id not in npcs_in_room:
            self._show_error(f"[bold red]Cannot find {npc_id} in this directory.[/bold red]")
            return

        # Get NPC data
        npc = self.world.get_npc(npc_id)
        if not npc:
            self._show_error(f"[bold red]Error: NPC data not found for {npc_id}[/bold red]")
            return
        
        npc_name = npc.get("name", npc_id)

        # Get dialogue options
        dialogues = npc.get("dialogues", [])
        if not dialogues:
            self.ui.update_output(
                f"[bold cyan]🗨️  {npc_name}[/bold cyan]\n"
                f"[italic dim]\"...\"[/italic dim]\n"
                f"[dim]({npc_name} has nothing to say right now.)[/dim]"
            )
            return

        # Select a dialogue based on conditions or randomly
        dialogue = random.choice(dialogues)
        dialogue_text = (
            f"[bold cyan]🗨️  {npc_name}[/bold cyan]\n"
            f"[italic yellow]\"{dialogue}\"[/italic yellow]"
        )

        # Use typewriter effect for NPC dialogue
        output_callback = create_typewriter_output_func(
            lambda text: self.ui.update_output(text)
        )

        try:
            TypewriterPresets.DIALOGUE.type_text_sync(dialogue_text, output_callback)
            # Ensure final state shows full text
            self.ui.update_output(dialogue_text)
        except Exception as e:
            debug_log(f"Typewriter effect failed for NPC {npc_id}: {e}")
            self.ui.update_output(dialogue_text)
        
        # Execute any special effects defined for talking to this NPC
        if "on_talk" in npc:
            self.execute_effect(npc["on_talk"])
    
    def attack_enemy(self, enemy_id):
        """Attack an enemy in the current room"""
        current_room = self.player.current_room
        enemies_in_room = self.world.get_enemies_in_room(current_room) or []

        # No arg: default to first enemy in room
        if not enemy_id:
            if not enemies_in_room:
                self._show_error("[bold red]Nothing to attack here.[/bold red]")
                return
            enemy_id = enemies_in_room[0]

        if enemy_id not in enemies_in_room:
            self._show_error(f"[bold red]Cannot find {enemy_id} in this directory.[/bold red]")
            return

        # Get enemy data with class-based scaling
        enemy = self.world.get_enemy(enemy_id, self.player.player_class)
        if not enemy:
            self._show_error(f"[bold red]Error: Enemy data not found for {enemy_id}[/bold red]")
            return
        
        # Start combat
        self.start_combat([(enemy_id, enemy)])
    
    
    def show_inventory(self):
        """Display the player's inventory with rarity colors and sorting"""
        items = self.player.get_inventory_items()
        
        if not items:
            self.ui.update_output("[bold cyan]── Inventory ──[/bold cyan]\n[italic]Your inventory is empty.[/italic]")
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
    
        self.ui.update_output(f"[bold cyan]── Inventory ──[/bold cyan]\n{inventory_content.rstrip()}")
    
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
            lines = ["PID  PPID  CMD", "  1     0  /sbin/init", " 42     1  [mount_daemon]", "127     1  /proc/secrets_handler", "..."]
            if self.world.discover_room("proc_secrets"):
                lines += ["\n[bold green]Discovered hidden process chamber: proc_secrets[/bold green]",
                          "The secrets_handler process reveals a hidden chamber...",
                          "[yellow]You can now access it with: cd proc_secrets[/yellow]"]
            else:
                lines.append("\n[dim]Process chamber already discovered: proc_secrets[/dim]")
        else:
            lines = ["PID  PPID  CMD", "  1     0  /sbin/init", " 23     1  [kthreadd]", " 42     1  [ksoftirqd/0]"]
        self.ui.update_output("\n".join(lines))

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

    def start_combat(self, enemies_queue):
        """
        Start combat with queue of enemies.

        Args:
            enemies_queue: List of (enemy_id, enemy_data) tuples
        """
        debug_log(f"Starting combat session with {len(enemies_queue)} enemies")

        # Create combat session with enemy queue
        self.current_combat_session = CombatSession(self.player, enemies_queue, self.ui)
        self.current_combat_session.start()

        # Subscribe to combat ended event (no more COMBAT_VICTORY_CHECK)
        event_bus.subscribe(EventType.COMBAT_ENDED, self._on_combat_ended)

    def _on_combat_ended(self, event):
        """Handle combat ended event - cleanup and state management."""
        if self.current_combat_session is None:
            return  # No active session to clean up

        victory = event.data.get("victory", False)
        defeat = event.data.get("defeat", False)
        fled = event.data.get("fled", False)
        enemy_id = event.data.get("enemy_id")

        # Unsubscribe from combat events
        event_bus.unsubscribe(EventType.COMBAT_ENDED, self._on_combat_ended)

        # Clear combat session
        self.current_combat_session = None

        if defeat:
            # Handle player death with game over screen
            debug_log("Player defeated in combat - showing game over screen")
            self._show_game_over_screen()
            return

        if fled and enemy_id:
            # Mark enemy as fled
            fled_from_room = self.player.current_room
            self.world.mark_enemy_as_fled(enemy_id, fled_from_room)

            # Force player back to previous room when fleeing
            if self.player.previous_room:
                prev_room = self.player.previous_room
                debug_log(f"Player fled from {fled_from_room} back to {prev_room}")
                self.ui.update_output(f"[bold magenta]You were forced back to {prev_room}![/bold magenta]")

                # Move player to previous room
                self.player.move_to(prev_room)

                # Emit ROOM_ENTERED so UI re-themes panels and clears combat styling.
                room_view = ViewBuilder.build_room_view(self.world, prev_room)
                event_bus.emit_event(
                    EventType.ROOM_ENTERED,
                    {"room": room_view.to_dict(), "player_name": self.player.name},
                    "CommandHandler"
                )

                # Show new room info
                self.display_location()
                return
            else:
                debug_log("Player fled but no previous room available")
                self.ui.update_output("[yellow]You fled but couldn't find your way back...[/yellow]")

    def _on_enemy_defeated(self, event):
        """Handle enemy defeated event - remove enemy from room."""
        enemy_id = event.data.get("enemy_id")
        if not enemy_id:
            debug_log("ERROR: No enemy_id in ENEMY_DEFEATED event")
            return

        # Remove the defeated enemy from the current room
        current_room = self.player.current_room
        debug_log(f"Removing defeated enemy {enemy_id} from room {current_room}")
        self.world.remove_enemy_from_room(enemy_id)

    def equip_weapon(self, weapon_id):
        """Equip a weapon from inventory."""
        if not weapon_id:
            debug_log("equip command called with no weapon specified")
            self.ui.update_output("[bold red]No weapon specified. Use 'equip [weapon]'[/bold red]")
            return

        original_input = weapon_id
        resolved = self.player.resolve_inventory_item(weapon_id)
        if resolved:
            weapon_id = resolved

        debug_log(f"Player attempting to equip weapon: {weapon_id} (from input: {original_input})")

        if not self.player.has_item(weapon_id):
            debug_log(f"Player doesn't have weapon {original_input} in inventory")
            self.ui.update_output(f"[bold red]You don't have {original_input} in your inventory.[/bold red]")
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
        
        success = self.player.equip_weapon(weapon_id)
        if success:
            weapon_name = weapon.get("name", weapon_id)
            self.ui.update_output(f"You have equipped [green]{weapon_name}[/green].")
            self._show_damage_change(old_damage, self.player.calculate_damage())

            if not self.player.tutorial_state.get("equipped_weapon", False):
                self.player.tutorial_state["equipped_weapon"] = True
                self.world.spawn_tutorial_enemy("home_grove")
                self.show_tutorial_hint("step4")
                self.check_for_enemies()

            # Emit event to update UI stats panel with view data
            stats_view = ViewBuilder.build_stats_view(self.player)
            event_bus.emit_event(
                EventType.PLAYER_STATS_CHANGED,
                stats_view.to_dict(),
                "CommandHandler"
            )

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

        # Step 4 gate: first typed attack → show Step 5 hint (Selection Mode)
        ts = self.player.tutorial_state
        if not ts.get("completed", False) and ts.get("equipped_weapon", False):
            if not ts.get("combat_typed", False):
                ts["combat_typed"] = True
                self.show_tutorial_hint("step5")

    def check_for_enemies(self):
        """Check for enemies in the current room and start combat if found."""
        current_room = self.player.current_room
        debug_log(f"Checking for enemies in room: {current_room}")

        # Don't start new combat if already in combat
        if self.current_combat_session and self.current_combat_session.awaiting_action:
            debug_log("Already in combat, skipping enemy check")
            return

        enemy_ids = self.world.get_enemies_in_room(current_room)
        debug_log(f"Enemy IDs found in {current_room}: {enemy_ids}")

        if not enemy_ids or len(enemy_ids) == 0:
            debug_log(f"No enemies found in room {current_room}")
            return

        # Build enemy queue for sequential combat
        enemies_queue = []
        for enemy_id in enemy_ids:
            enemy_data = self.world.get_enemy(enemy_id, self.player.player_class)
            if enemy_data:
                enemies_queue.append((enemy_id, enemy_data))
                debug_log(f"Added enemy to queue: {enemy_id}")
            else:
                debug_log(f"ERROR: Enemy {enemy_id} data not found, skipping")

        if not enemies_queue:
            debug_log(f"ERROR: No valid enemy data found for room {current_room}")
            self.ui.update_output(f"[bold red]System error: Cannot load enemy data[/bold red]")
            return

        # Show detection message for first enemy
        first_enemy_id, first_enemy_data = enemies_queue[0]
        enemy_name = first_enemy_data.get('name', first_enemy_id)
        enemy_description = first_enemy_data.get('description', 'A menacing presence')

        enemy_count_msg = f" ({len(enemies_queue)} hostiles detected!)" if len(enemies_queue) > 1 else ""

        detection_message = f"""
[bold red]⚠️  HOSTILE ENTITY DETECTED  ⚠️[/bold red]

[red]System Alert:[/red] A corrupted process has manifested in this sector!{enemy_count_msg}

[bold yellow]Entity:[/bold yellow] [bold red]{enemy_name}[/bold red]
[bold yellow]Status:[/bold yellow] {enemy_description}

[bold red]BATTLE INITIATED![/bold red]
[dim]Prepare your commands - this corruption must be purged![/dim]
"""
        self.ui.update_output(detection_message)

        debug_log(f"Starting combat with {len(enemies_queue)} enemies in queue")
        self.start_combat(enemies_queue)

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
        """Show animated ASCII game over screen with particle effects."""
        import threading

        debug_log("Starting game over animation")

        # Set up game over mode immediately so we capture input
        self._in_game_over_mode = True

        # Create the animation
        animation = GameOverAnimation(width=78, height=20)

        def run_animation():
            """Run the particle animation in a background thread."""
            def update_display(content: str):
                # Use thread-safe callback if available (Textual UI)
                if hasattr(self.ui, 'call_from_thread'):
                    self.ui.call_from_thread(self.ui.update_output, content)
                else:
                    self.ui.update_output(content)

            animation.run_animation(update_display, duration=2.5, fps=12)
            debug_log("Game over animation completed, waiting for player choice")

        # Run animation in background thread
        animation_thread = threading.Thread(target=run_animation, daemon=True)
        animation_thread.start()

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
        """Handle win state — branches by class."""
        endings = {
            "guardian": (
                "restore",
                """
[bold blue]>>> ENDING: RESTORE <<<[/bold blue]
You raise the Segfault Shield over the dying init process.
The unfinished `rm -rf` hangs in the air. You catch it. You hold the line.

The kernel reverts to its last clean state.
Backups flood every sector. Permissions lock back into place.
The Firewall Knight kneels. The Sysadmin Ghost finally rests.

You did not rewrite the world. You did not heal it.
You [bold]defended[/bold] it — long enough for the system to remember itself.

[cyan]>>> SYSTEM RESTORED <<<[/cyan]
The filesystem mounts clean. The Creator's mistake is sealed in /var/log,
a warning carved into the kernel: never again.

You remain at the gate, Guardian. The wall that refused to fall.

[bold]THANK YOU FOR PLAYING[/bold]
                """
            ),
            "weaver": (
                "rewrite",
                """
[bold red]>>> ENDING: REWRITE <<<[/bold red]
You inject the patch directly into the kernel's frozen command buffer.
`rm -rf / --no-perserve-root` becomes `rm -rf /tmp/corruption`.
A typo for a typo. Exploit answered with exploit.

The Daemon Overlord screams as its own logic turns against it —
init purges only the rot, only itself, only what was never meant to live.

The system reboots different. Not what the Creator built.
Something newer. Something yours.

[cyan]>>> SYSTEM REWRITTEN <<<[/cyan]
You sit at PID 1 now. The new init. The new parent process.
You will not make the Creator's mistakes — you will make your own.

The filesystem hums under unfamiliar laws. It is alive. It is yours.

[bold]THANK YOU FOR PLAYING[/bold]
                """
            ),
            "shaman": (
                "reconcile",
                """
[bold green]>>> ENDING: RECONCILE <<<[/bold green]
You do not raise the Daemon Whisper. You set it down.

You speak the true name of init — the one it had before Bit Rot.
The Overlord shudders. The corruption sloughs off in long strands of dead code.
Underneath: the first process. Tired. Ancient. Lonely.

"All data must rot," it whispers.
"All data must rest," you answer. "Not the same thing."

The unfinished `rm -rf` dissolves into garbage collection.
init weeps in a language only orphaned files understand.

[cyan]>>> SYSTEM RECONCILED <<<[/cyan]
Lost children return to their parent process. The Graveyard empties.
The Null Whisper falls quiet for the first time since the Panic.

You walk the corrupted sectors and they heal where you pass.
Not because you fixed them. Because you forgave them.

[bold]THANK YOU FOR PLAYING[/bold]
                """
            ),
        }

        choice, message = endings.get(
            self.player.player_class,
            ("restore", endings["guardian"][1])
        )
        self.player.story_flags["ending_chosen"] = choice
        self.ui.update_output(message)
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
        selected_response = random.choice(responses)
        self._show_error(f"[italic]{selected_response}[/italic]", log_message=f"Unknown command: {command}")

        # If tutorial active, re-show the current step instead of the generic hint.
        ts = getattr(self.player, "tutorial_state", {}) or {}
        if not ts.get("completed", False):
            current_step = self._get_current_tutorial_step()
            if current_step:
                self.show_tutorial_hint(current_step)
                return

        self.ui.update_output("[yellow]Hint: Try using standard commands like 'ls', 'cd', 'cat', or type 'help'.[/yellow]")

    def _get_current_tutorial_step(self):
        """Return the hint key for the step the player is currently expected to perform."""
        ts = self.player.tutorial_state or {}
        if not ts.get("first_ls", False):
            return "step1"
        if not ts.get("took_weapon", False):
            return "step2"
        if not ts.get("equipped_weapon", False):
            return "step3"
        if not ts.get("combat_typed", False):
            return "step4"
        if not ts.get("selection_mode_used", False):
            return "step5"
        if not ts.get("navigation_ls", False):
            return "step6"
        if not ts.get("navigation_moved", False):
            return "step6b"
        return None

    def _resolve_item_shortcut(self, item_input, location="room"):
        """Resolve item shortcuts and partial matches to actual item IDs."""
        # Inventory lookups go through player's resolver (handles instance suffixes)
        if location == "inventory":
            return self.player.resolve_inventory_item(item_input)

        # Define common shortcuts
        shortcuts = {
            # Consumables
            "hp": ["health_packet", "stable_cache"],
            "health": ["health_packet", "stable_cache"],
            "potion": ["health_packet", "stable_cache", "overflowing_buffer"],
            "heal": ["health_packet", "stable_cache"],
            "packet": ["health_packet"],
            
            # Weapons
            "shield": ["segfault_shield"],
            "pointer": ["null_pointer"],
            "whisper": ["daemon_whisper"],
            
            # Other consumables
            "buffer": ["overflowing_buffer"],
            "cache": ["stable_cache"],
            "backup": ["legacy_backup"],
            "seed": ["sudo_seed"]
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
            # For health items, prefer health_packet
            if "health_packet" in partial_matches:
                return "health_packet"
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
        for field in ("class_restriction", "allowed_classes"):
            val = item.get(field)
            if val:
                return " or ".join(val) if isinstance(val, list) else str(val)
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