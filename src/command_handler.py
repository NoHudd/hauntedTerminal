#!/usr/bin/env python3
from src import rng
import logging
from rich.text import Text
from src.combat import CombatSession
from src.commands import build_registry
from src.events import EventType
from src.game_flow import GameFlow
from src.game_world import TUTORIAL_ENEMY
from src.item_effects import ItemEffects
from src.item_resolver import ItemResolver
from src.loot import LootService
from src.tutorial_coach import TutorialCoach
from src.viewmodels.view_builder import ViewBuilder
from utils.debug_tools import debug_log

logger = logging.getLogger(__name__)

class CommandHandler:
    """Handles processing of player commands"""
    
    def __init__(self, player, world, output, bus, on_combat_start=None, on_combat_end=None,
                 on_new_game=None, on_restore_save=None):
        """Initialize with player, world, a GameOutput sink and the engine's EventBus.

        Phase 2b: the handler no longer holds a UI reference — it writes to
        ``self.output`` (a src.game_output.GameOutput). The engine drains it and
        forwards to the real UI.

        on_combat_start() / on_combat_end(outcome) let the engine update the
        game state as a fight begins and ends, in a fixed place in the sequence.
        on_new_game() / on_restore_save() are the engine's, for the game-over
        screen's "n" and "r" choices.
        """
        debug_log("Initializing CommandHandler")
        self.player = player
        self.world = world
        self.output = output
        self.bus = bus
        self.current_combat_session = None
        self._on_combat_start = on_combat_start
        self._on_combat_end = on_combat_end

        # Navigation aliases (path/name -> room id) are built from each room's
        # own `path`/`aliases` YAML fields, so there is one source of truth per
        # room instead of a hand-maintained dict here. See src/room_paths.py.
        from src import room_paths
        self.room_aliases = room_paths.refresh_from_rooms(self.world.rooms)

        # Every verb is a Phase 3 command-pattern object. See src/commands/.
        self.command_registry = build_registry()

        # Collaborators the commands use through this handler (ctx.<name>).
        self.resolver = ItemResolver(world, player)
        self.tutorial = TutorialCoach(player, world, bus)
        self.flow = GameFlow(
            player, world, output, bus,
            save=lambda: self.command_registry["save"].execute(self, []),
            start_new_game=on_new_game,
            restore_save=on_restore_save,
        )
        self.effects = ItemEffects(
            player, world, output, bus, self.room_aliases,
            self.flow, start_encounter=self.check_for_enemies,
        )
        self.loot = LootService(world, player, output, relist_room=self.relist_room)

        debug_log(f"Registered {len(self.command_registry)} commands")

    def _subscriptions(self):
        return [
            (EventType.COMBAT_ENDED, self.tutorial.on_combat_ended),
            (EventType.COMBAT_ACTION_RESULT, self.tutorial.on_combat_action_result),
        ]

    def setup_event_subscriptions(self):
        """Set up event subscriptions for the command handler."""
        for event_type, callback in self._subscriptions():
            self.bus.subscribe(event_type, callback)
        debug_log("CommandHandler event subscriptions set up")

    def cleanup_event_subscriptions(self):
        """Clean up ALL event subscriptions for the command handler.

        Must mirror every subscribe in _subscriptions(); a missed unsubscribe
        leaves a dead run's tutorial reacting to the next run's fights.

        Also aborts any still-active combat session. A CombatSession only
        unsubscribes its own COMBAT_ACTION_SELECTED listener when it reaches a
        real victory/defeat/flee outcome; if the player restarts, loads a save,
        or (in tests) tears down mid-fight, that listener would otherwise leak
        and double-process the next combat's actions.
        """
        for event_type, callback in self._subscriptions():
            self.bus.unsubscribe(event_type, callback)
        if self.current_combat_session is not None:
            self.current_combat_session.abort()
            self.current_combat_session = None
        debug_log("CommandHandler event subscriptions cleaned up")
    
    def announce_room(self):
        """Tell the UI which room the player is in (scene, exits, theme).

        A notification only: nothing in the game reacts to ROOM_ENTERED, so a
        UI refresh (e.g. `ls -a` revealing a directory) can't start a fight.
        """
        room_view = ViewBuilder.build_room_view(self.world, self.player.current_room)
        self.bus.emit_event(
            EventType.ROOM_ENTERED,
            {"room": room_view.to_dict(), "player_name": self.player.name},
            "CommandHandler",
        )

    def arrive(self):
        """The player has just entered their current room.

        Shows it to the UI, then applies the arrival rules: enemies they fled
        from here come back, and any hostile here starts a fight. Callers invoke
        this directly after moving the player (cd, flee, new game, load); it
        used to hang off the ROOM_ENTERED event, and a load path that forgot to
        subscribe silently turned encounters off.
        """
        self.announce_room()
        room_id = self.player.current_room
        if room_id:
            self.world.respawn_fled_enemies(room_id)
            self.check_for_enemies()
    
    def _npc_speaks_after_combat(self, room_id):
        """The room was just cleared: the first NPC here, if any, offers its
        closing line."""
        npcs_in_room = self.world.get_npcs_in_room(room_id)
        if not npcs_in_room:
            return
        npc_id = npcs_in_room[0]
        npc_data = self.world.get_npc(npc_id)
        if not npc_data or not npc_data.dialogues:
            return

        npc_name = npc_data.name
        self.output.write(
            f"\n[bold cyan]🗨  {npc_name} speaks:[/bold cyan]\n"
            f"[italic cyan]\"{npc_data.dialogues[-1]}\"[/italic cyan]\n"
            f"\n[dim]The {npc_name} offers guidance now that the area is safe.[/dim]"
        )
        debug_log(f"Post-combat dialogue from {npc_id} in {room_id}")

    def handle_command(self, command):
        """Process a command from the player"""
        cmd_parts = command.split()
        
        if not cmd_parts:
            debug_log("Empty command received")
            return
        
        # Handle game over mode specially
        if self.flow.in_game_over_mode:
            self.flow.handle_game_over_input(command)
            return

        # Check if player is dead and trigger game over if not already handled
        if self.player and not self.player.is_alive() and not self.flow.in_game_over_mode:
            debug_log("Player is dead but not in game over mode - triggering game over screen")
            self.flow.show_game_over_screen()
            return

        # Handle quit confirmation mode specially
        if self.flow.in_quit_confirmation:
            self.flow.handle_quit_confirmation(command.strip())
            return
        
        # Handle combat commands specially
        if self.current_combat_session and self.current_combat_session.awaiting_action:
            self._handle_combat_command(command.strip())
            return
        
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        debug_log(f"Processing command: '{cmd}' with args: {args}")

        # Every verb is a command-pattern object in the registry; see src/commands/.
        if cmd in self.command_registry:
            debug_log(f"Executing migrated command '{cmd}' with args {args}")
            self.command_registry[cmd].execute(self, args)
        else:
            debug_log(f"Unknown command: '{cmd}'")
            self.handle_unknown_command(command)
    
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
            self.output.write("[bold red]Error: Invalid room![/bold red]")
            return
        
        # Mark room as visited
        self.world.set_room_visited(room_id)
        
        # Get room information
        room_name = room.name or room_id
        title = Text(f"{room_name}", style="bold white on dark_blue")
        description = Text(room.description or "No description available.")

        # Get atmospheric enhancement
        atmospheric = self.get_atmospheric_description(room_id)

        # Create content with title and atmospheric description
        location_content = f"[bold]{title}[/bold]\n\n{description}"
        if atmospheric:
            location_content += f"\n\n{atmospheric}"
        
        self.output.write(location_content)

    def relist_room(self):
        """Re-render the current room's contents, as if the player typed `ls`.

        Called after actions that change what's on the ground (take/drop) or
        after reading a room file, so the player sees the updated room without
        having to retype `ls`.
        """
        ls_cmd = self.command_registry.get("ls")
        if ls_cmd is not None:
            ls_cmd.execute(self, [])

    def get_formatted_item_description(self, item):
        """Format item description to show what it does in parentheses"""
        if not item:
            return "No description available"

        # Get base description (try different fields with fallbacks)
        base_desc = (
            item.short_description or
            item.description.split(".")[0] or  # Take first sentence if multiple
            item.name or
            "Unknown item"
        )

        # Determine item effect based on type and properties
        effect = ""

        # Healing items - check combat_effects.player_heal first (new format)
        if "player_heal" in item.combat_effects:
            effect = f"+{item.combat_effects['player_heal']} HP"

        # Also check on_use.heal (old format)
        elif "heal" in item.on_use:
            effect = f"+{item.on_use['heal']} HP"

        # Damage-dealing consumables
        elif "player_damage" in item.combat_effects:
            effect = f"+{item.combat_effects['player_damage']} DMG"
        elif "damage" in item.on_use:
            effect = f"+{item.on_use['damage']} DMG"

        # Status effect items
        elif "status_effect" in item.on_use:
            effect_name = item.on_use["status_effect"].get("name", "Effect")
            effect = f"Status: {effect_name}"

        # Weapons - check damage field
        elif item.type == "weapon" or "weapon" in item.type:
            if item.damage > 0:
                effect = f"+{item.damage} DMG"

        # Upgrade items
        elif item.effects:
            effects = []
            if "permanent_health" in item.effects:
                effects.append(f"+{item.effects['permanent_health']} HP")
            if "permanent_damage" in item.effects:
                effects.append(f"+{item.effects['permanent_damage']} DMG")
            if effects:
                effect = "Perm: " + "/".join(effects)

        # Key items
        elif item.type == "key" or item.unlocks:
            effect = "Unlocks areas"

        # Add the effect in parentheses if we found one
        if effect:
            return f"{base_desc} ({effect})"
        else:
            return base_desc
    
    def check_enemies_blocking_exploration(self, room_id):
        """Check if enemies are present and blocking exploration. Returns (has_enemies, output_text)"""
        enemies = self.world.get_enemies_in_room(room_id) or []
        if not enemies:
            return False, None
        
        lines = [
            "[bold red]⚠  COMBAT REQUIRED  ⚠[/bold red]\n",
            "Hostile entities are present! You must defeat all enemies before exploring.\n",
            "[bold red]Corrupted Entities:[/bold red]",
        ]
        for enemy_id in enemies:
            enemy = self.world.get_enemy(enemy_id, self.player.player_class)
            if enemy:
                name = enemy.name
                health = enemy.health
                lines.append(f"  [red]{enemy_id}[/red] - {name} (HP: {health})")

        lines.append("\nUse [cyan]attack <enemy>[/cyan] to engage in combat.")
        return True, "\n".join(lines)

    def start_combat(self, enemies_queue):
        """
        Start combat with queue of enemies.

        Args:
            enemies_queue: List of (enemy_id, Enemy) tuples
        """
        debug_log(f"Starting combat session with {len(enemies_queue)} enemies")

        self.current_combat_session = CombatSession(
            self.player, enemies_queue, self.output, self.bus,
            on_start=self._on_combat_start, on_end=self.end_combat,
            on_kill=self.on_kill,
        )
        self.current_combat_session.start()

    def end_combat(self, outcome):
        """A fight is over; CombatSession calls this directly with the outcome.

        The steps run in this order, every time: the engine updates the game
        state (combat over, or game over on a death), then the player is sent
        to game over, relocated after fleeing, or checked for victory. This
        used to be four COMBAT_ENDED listeners whose order came from the order
        they happened to be subscribed in.
        """
        if self.current_combat_session is None:
            return  # No active session to clean up

        victory = outcome.get("victory", False)
        defeat = outcome.get("defeat", False)
        fled = outcome.get("fled", False)
        enemy_id = outcome.get("enemy_id")

        self.current_combat_session = None
        if self._on_combat_end is not None:
            self._on_combat_end(outcome)

        if defeat:
            # Handle player death with game over screen
            debug_log("Player defeated in combat - showing game over screen")
            self.flow.show_game_over_screen()
            return

        tutorial_active = not self.player.tutorial_state.get("completed", False)
        if fled and enemy_id == TUTORIAL_ENEMY and tutorial_active:
            # Fleeing would take the scripted enemy out of the room until the
            # player leaves and comes back, stranding the tutorial on "press 1".
            # It stays put instead, so `attack` restarts the fight.
            self.tutorial.show_hint("step4_fled")
            return

        if fled and enemy_id:
            # Mark enemy as fled
            fled_from_room = self.player.current_room
            self.world.mark_enemy_as_fled(enemy_id, fled_from_room)

            # Force player back to previous room when fleeing
            if self.player.previous_room:
                prev_room = self.player.previous_room
                debug_log(f"Player fled from {fled_from_room} back to {prev_room}")
                self.output.write(f"[bold magenta]You were forced back to {prev_room}![/bold magenta]")

                self.player.move_to(prev_room)
                self.display_location()
                self.arrive()
                return
            else:
                debug_log("Player fled but no previous room available")
                self.output.write("[yellow]You fled but couldn't find your way back...[/yellow]")

        # Victory: the defeated enemy is already removed from the room (via
        # ENEMY_DEFEATED), so the Core is clear if the Overlord just fell.
        if victory:
            self.flow.check_game_completion()

    def on_kill(self, enemy_id):
        """An enemy died; the combat session calls this directly.

        Awards its loot into the room, removes it, and once the room is clear
        lets an NPC there speak up. This used to run from ENEMY_DEFEATED, and
        the removal re-emitted that same event from inside its own handling.
        """
        current_room = self.player.current_room
        self.loot.award_once(enemy_id, current_room)

        debug_log(f"Removing defeated enemy {enemy_id} from room {current_room}")
        self.world.remove_enemy_from_room(enemy_id)
        if not self.world.get_enemies_in_room(current_room):
            self._npc_speaks_after_combat(current_room)

    def _handle_combat_command(self, command):
        """Handle commands during combat."""
        debug_log(f"Handling combat command: {command}")

        # Emit combat action selected event
        self.bus.emit_event(
            EventType.COMBAT_ACTION_SELECTED,
            {"choice": command},
            "CommandHandler"
        )

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
            self.output.write("[bold red]System error: Cannot load enemy data[/bold red]")
            return

        # Show detection message for first enemy
        first_enemy_id, first_enemy_data = enemies_queue[0]
        enemy_name = first_enemy_data.name
        enemy_description = first_enemy_data.description or 'A menacing presence'

        enemy_count_msg = f" ({len(enemies_queue)} hostiles detected!)" if len(enemies_queue) > 1 else ""

        detection_message = f"""
[bold red]⚠  HOSTILE ENTITY DETECTED  ⚠[/bold red]

[red]System Alert:[/red] A corrupted process has manifested in this sector!{enemy_count_msg}

[bold yellow]Entity:[/bold yellow] [bold red]{enemy_name}[/bold red]
[bold yellow]Status:[/bold yellow] {enemy_description}

[bold red]BATTLE INITIATED![/bold red]
[dim]Prepare your commands - this corruption must be purged![/dim]
"""
        self.output.write(detection_message)

        debug_log(f"Starting combat with {len(enemies_queue)} enemies in queue")
        self.start_combat(enemies_queue)

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
        selected_response = rng.choice(responses)
        self.output.error(f"[italic]{selected_response}[/italic]", log_message=f"Unknown command: {command}")

        # If tutorial active, re-show the current step instead of the generic hint.
        ts = getattr(self.player, "tutorial_state", {}) or {}
        if not ts.get("completed", False):
            current_step = self.tutorial.current_step()
            if current_step == "step4" and self.current_combat_session is None:
                current_step = "step4_fled"
            if current_step:
                self.tutorial.show_hint(current_step)
                return

        self.output.write("[yellow]Hint: Try using standard commands like 'ls', 'cd', 'cat', or type 'help'.[/yellow]")
