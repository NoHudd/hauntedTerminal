#!/usr/bin/env python3
import yaml
import random
from src import rng
from utils.debug_tools import debug_log
from src.events import event_bus, EventType
from src.viewmodels.view_builder import ViewBuilder

class CombatSystem:
    """Handles all combat-related functionality with a unified approach."""
    
    def __init__(self):
        """Initialize the combat system and load attack data."""
        debug_log("Initializing CombatSystem")
        self.attacks = self.load_attacks()
        self.active_cooldowns = {}  # player_object_id -> {attack_id -> remaining_cooldown}
    
    def load_attacks(self):
        """Load attack definitions from YAML file."""
        try:
            with open('data/attacks.yml', 'r') as file:
                data = yaml.safe_load(file)
                attack_count = len(data.get('attacks', {}))
                debug_log(f"Loaded {attack_count} attacks from attacks.yml")
                return data.get('attacks', {})
        except Exception as e:
            debug_log(f"Error loading attacks: {e}")
            print(f"Error loading attacks: {e}")
            return {}
    
    def get_attack_data(self, attack_id):
        """Get data for a specific attack from the YAML data."""
        attack = self.attacks.get(attack_id, None)
        if attack is None:
            debug_log(f"Attack '{attack_id}' not found in attacks data")
        return attack
    
    def get_attacks_for_class(self, player_class):
        """Get available attacks for a specific character class from classes.yaml."""
        from src.data_loader import load_class_data
        class_data = load_class_data()
        cls = class_data.get(player_class)
        attacks = (cls.attacks if cls else None) or ["strike"]
        debug_log(f"Available attacks for {player_class} class: {attacks}")
        return attacks
    
    def initialize_cooldowns(self, player_id):
        """Initialize cooldowns for a player."""
        debug_log(f"Initializing cooldowns for player ID: {player_id}")
        self.active_cooldowns[player_id] = {}
    
    def calculate_damage(self, base_player_damage, attack_id):
        """Calculate damage for an attack using simplified formula.
        
        Formula: base_player_damage + attack_bonus_damage from YAML
        """
        debug_log(f"Calculating damage for attack '{attack_id}' with base player damage {base_player_damage}")
        attack_data = self.get_attack_data(attack_id)
        if not attack_data:
            debug_log(f"No attack data found for '{attack_id}', using base damage only")
            return base_player_damage  # Just use total damage if attack not found
        
        # Use bonus_damage or fallback to damage for backward compatibility
        bonus_damage = attack_data.get('bonus_damage', attack_data.get('damage', 0))
        total_damage = base_player_damage + bonus_damage
        debug_log(f"Attack '{attack_id}' calculation: {base_player_damage} (base) + {bonus_damage} (bonus) = {total_damage}")
        return total_damage

    def perform_attack(self, player, attack_id):
        """Execute an attack and return the results.
        
        Args:
            player: The Player object initiating the attack.
            attack_id: ID of the attack to perform.
            
        Returns:
            dict: Results of the attack including damage, message, healing_amount,
                  enemy_damage_reduction, and success status.
        """
        player_id = player.player_id # Using the player object's unique ID
        player_base_damage = player.calculate_damage()
        debug_log(f"Player {player_id} (Name: {player.name}) initiating attack '{attack_id}' with base damage {player_base_damage}")

        # Initialize cooldowns if not already done for this player
        if player_id not in self.active_cooldowns:
            debug_log(f"Cooldowns not initialized for player {player_id}, initializing now")
            self.initialize_cooldowns(player_id)
        
        attack_data = self.get_attack_data(attack_id)
        
        if not attack_data:
            debug_log(f"Attack '{attack_id}' not found, falling back to basic attack")
            return {
                "damage": player_base_damage,
                "message": "You attack with your weapon.",
                "healing_amount": 0,
                "enemy_damage_reduction": 0,
                "success": True, # Basic attacks always succeed if attack_id is invalid
                "bonus_damage": 0
            }

        # Check if attack is on cooldown
        if attack_id in self.active_cooldowns[player_id] and self.active_cooldowns[player_id][attack_id] > 0:
            remaining_cooldown = self.active_cooldowns[player_id][attack_id]
            debug_log(f"Attack '{attack_id}' is on cooldown ({remaining_cooldown} turns remaining)")
            # Perform a basic attack instead
            return {
                "damage": player_base_damage, # Player's normal damage without skill bonus
                "message": f"{attack_data['name']} is on cooldown ({remaining_cooldown} turns)! You use a regular attack.",
                "healing_amount": 0,
                "enemy_damage_reduction": 0,
                "success": False, # Indicate the chosen skill didn't fire
                "bonus_damage": 0
            }

        # Hit/Miss mechanic
        attack_accuracy = attack_data.get('accuracy')
        if attack_accuracy is None:
            attack_accuracy = 90 # Default to 90 if not specified
            debug_log(f"Warning: Attack '{attack_id}' has no 'accuracy' defined. Defaulting to {attack_accuracy}%.", "warning")
        else:
            debug_log(f"Attack '{attack_id}' has accuracy: {attack_accuracy}%")

        if rng.randint(1, 100) > attack_accuracy:
            debug_log(f"Attack '{attack_id}' (Name: {attack_data.get('name', attack_id)}) MISSED!")
            return {
                "success": False,
                "message": f"Your {attack_data.get('name', attack_id)} missed!",
                "damage": 0,
                "healing_amount": 0,
                "enemy_damage_reduction": 0,
                "bonus_damage": 0 
            }
        else:
            debug_log(f"Attack '{attack_id}' (Name: {attack_data.get('name', attack_id)}) HIT!")
            # Proceed with successful attack logic

            # Calculate final damage using player's damage and attack's bonus
            damage = self.calculate_damage(player_base_damage, attack_id)
            bonus_damage = attack_data.get('bonus_damage', attack_data.get('damage', 0)) # For message consistency

            # Set cooldown ONLY IF THE ATTACK HITS
            cooldown = attack_data.get('cooldown', 0)
            if cooldown > 0:
                self.active_cooldowns[player_id][attack_id] = cooldown
                debug_log(f"Setting cooldown for '{attack_id}': {cooldown} turns for player {player_id}")
            
            healing_amount = attack_data.get('healing', 0)
            enemy_damage_reduction = attack_data.get('enemy_damage_reduction', 0)
        
        debug_log(f"Attack '{attack_id}' results: damage={damage}, healing_amount={healing_amount}, enemy_damage_reduction={enemy_damage_reduction}")

        # Build message with player name for combat log
        player_name = getattr(player, 'name', 'Player')
        attack_name = attack_data['name']

        message = f"{player_name} used {attack_name} ({damage} dmg)"
        if bonus_damage > 0:
            message = f"{player_name} used {attack_name} ({damage} dmg: {player_base_damage} base + {bonus_damage} bonus)"

        if healing_amount > 0:
            message += f" [+{healing_amount} HP]"

        if enemy_damage_reduction > 0:
            message += f" [Enemy dmg -{int(enemy_damage_reduction * 100)}%]"
            
        return {
            "damage": damage,
            "message": message,
            "healing_amount": healing_amount,
            "enemy_damage_reduction": enemy_damage_reduction,
            "success": True,
            "bonus_damage": bonus_damage
        }

    def update_cooldowns(self, player):
        """Update cooldowns at the end of a combat turn for a specific player."""
        player_id = player.player_id
        if player_id not in self.active_cooldowns:
            debug_log(f"No cooldowns to update for player {player_id} (Name: {player.name})")
            return
        
        updated_attacks = []
        for attack_id in list(self.active_cooldowns[player_id].keys()):
            if self.active_cooldowns[player_id][attack_id] > 0:
                old_cooldown = self.active_cooldowns[player_id][attack_id]
                self.active_cooldowns[player_id][attack_id] -= 1
                new_cooldown = self.active_cooldowns[player_id][attack_id]
                updated_attacks.append(f"{attack_id}: {old_cooldown}->{new_cooldown}")
        
        if updated_attacks:
            debug_log(f"Updated cooldowns for player {player_id} (Name: {player.name}): {', '.join(updated_attacks)}")

    def reset_cooldowns(self, player):
        """Reset all cooldowns for a player (used when combat ends)."""
        player_id = player.player_id
        debug_log(f"Resetting all cooldowns for player {player_id} (Name: {player.name})")
        self.active_cooldowns[player_id] = {}

    def reduce_cooldowns_by_one(self, player_id):
        """Reduce all active cooldowns by 1 turn (for sequential combat)."""
        if player_id not in self.active_cooldowns:
            return

        reduced = []
        for attack_id in list(self.active_cooldowns[player_id].keys()):
            if self.active_cooldowns[player_id][attack_id] > 0:
                old_cd = self.active_cooldowns[player_id][attack_id]
                self.active_cooldowns[player_id][attack_id] -= 1
                new_cd = self.active_cooldowns[player_id][attack_id]
                reduced.append(f"{attack_id}: {old_cd}->{new_cd}")

        if reduced:
            debug_log(f"Reduced cooldowns for sequential combat: {', '.join(reduced)}")

    def get_available_attacks(self, player, learned_spells=None):
        """Get available attacks for a player, including learned spells."""
        player_id = player.player_id
        player_class = player.player_class
        debug_log(f"Getting available attacks for player {player_id} (Name: {player.name}, Class: {player_class})")
        
        if player_id not in self.active_cooldowns:
            debug_log(f"Cooldowns not initialized for player {player_id}, initializing now")
            self.initialize_cooldowns(player_id)
        
        # Get base attacks for class from CombatSystem
        base_attacks_ids = self.get_attacks_for_class(player_class) # This returns list of IDs
        # Add learned spells (which are also attack_ids)
        spell_attack_ids = []
        if learned_spells and player_class in ["weaver", "shaman", "mage", "celtic"]: # Ensure only spellcasting classes get spells
            for spell in learned_spells: # Assuming learned_spells is a list of spell dicts
                spell_id = spell.get('spell_name', '').lower().replace(' ', '_') # Convert to attack_id format
                if spell_id in self.attacks: # Check if this spell_id is a defined attack
                    spell_attack_ids.append(spell_id)
            if spell_attack_ids:
                 debug_log(f"Added {len(spell_attack_ids)} learned spell attacks: {spell_attack_ids}")

        all_attack_ids = list(set(base_attacks_ids + spell_attack_ids)) # Use set to avoid duplicates
        debug_log(f"Combined attack IDs for {player_class}: {all_attack_ids}")

        available_attacks_data = {}
        for attack_id in all_attack_ids:
            attack_definition = self.get_attack_data(attack_id) # Fetches from attacks.yml
            if not attack_definition:
                debug_log(f"No attack definition found for '{attack_id}' in attacks.yml, skipping.")
                continue
            
            attack_display_data = attack_definition.copy() # Use a copy for modification

            # Add the attack_id to the data for easier access
            attack_display_data['id'] = attack_id

            # Ensure 'bonus_damage' is present, falling back to 'damage' if necessary
            if 'bonus_damage' not in attack_display_data and 'damage' in attack_display_data:
                attack_display_data['bonus_damage'] = attack_display_data['damage']
            elif 'bonus_damage' not in attack_display_data:
                 attack_display_data['bonus_damage'] = 0 # Default if neither exists

            # Check and apply cooldown status
            if attack_id in self.active_cooldowns[player_id] and self.active_cooldowns[player_id][attack_id] > 0:
                attack_display_data["on_cooldown"] = True
                attack_display_data["cooldown_remaining"] = self.active_cooldowns[player_id][attack_id]
                debug_log(f"Attack '{attack_id}' is on cooldown for player {player_id}: {attack_display_data['cooldown_remaining']} turns.")
            else:
                attack_display_data["on_cooldown"] = False
            
            available_attacks_data[attack_id] = attack_display_data
            
        debug_log(f"Returning {len(available_attacks_data)} available attacks for player {player_id} (Name: {player.name})")
        return available_attacks_data

class CombatSession:
    """Manages an active combat session using event-driven approach."""

    def __init__(self, player, enemies_queue, output):
        """
        Initialize combat session with enemy queue.

        Args:
            player: Player object
            enemies_queue: List of (enemy_id, enemy_data) tuples
            output: GameOutput sink (Phase 2b — no direct UI reference)
        """
        self.player = player
        self.enemies_queue = enemies_queue  # List of (enemy_id, enemy_data)
        self.current_enemy_index = 0
        self.output = output
        self.is_active = True
        self.awaiting_action = False

        # Initialize with first enemy
        if enemies_queue:
            self.enemy_id, self.enemy_data = enemies_queue[0]
            self.enemy_health = self.enemy_data.get("health", 50)
            self.enemy_max_health = self.enemy_health
            self.enemy_damage = self.enemy_data.get("damage", 10)
            self.is_boss = self.enemy_data.get("is_boss", False)

        debug_log(f"CombatSession created with {len(enemies_queue)} enemies in queue")

        # Subscribe to combat events
        event_bus.subscribe(EventType.COMBAT_ACTION_SELECTED, self._on_combat_action)
    
    def start(self):
        """Start the combat session."""
        enemy_name = self.enemy_data.get("name", self.enemy_id)
        debug_log(f"Starting combat with {enemy_name}")

        # Build combat view and emit combat started event
        combat_view = ViewBuilder.build_combat_view(
            self.player,
            self.enemy_data,
            self.enemy_health,
            combat_system
        )

        event_bus.emit_event(
            EventType.COMBAT_STARTED,
            combat_view.to_dict(),
            "CombatSession"
        )

        # Emit combat intro message as a combat log entry
        combat_intro = f"⚔  Combat initiated with {enemy_name}!"
        if "dialogue" in self.enemy_data:
            combat_intro += f" | {enemy_name}: {self.enemy_data['dialogue']}"

        event_bus.emit_event(
            EventType.COMBAT_ACTION_RESULT,
            {
                "actor": "system",
                "action": "combat_start",
                "message": combat_intro,
                "damage": 0,
                "success": True
            },
            "CombatSession"
        )

        self._show_combat_status()
        self._request_player_action()

    def _engage_next_enemy(self):
        """
        Transition to next enemy in queue.
        Returns True if there's a next enemy, False if queue exhausted.
        """
        self.current_enemy_index += 1

        if self.current_enemy_index >= len(self.enemies_queue):
            debug_log("No more enemies in queue - combat chain complete")
            return False

        # Get next enemy
        self.enemy_id, self.enemy_data = self.enemies_queue[self.current_enemy_index]
        self.enemy_health = self.enemy_data.get("health", 50)
        self.enemy_max_health = self.enemy_health
        self.enemy_damage = self.enemy_data.get("damage", 10)
        self.is_boss = self.enemy_data.get("is_boss", False)

        enemy_name = self.enemy_data.get("name", self.enemy_id)
        debug_log(f"Engaging next enemy: {enemy_name} ({self.current_enemy_index + 1}/{len(self.enemies_queue)})")

        # Reduce cooldowns by 1 for sequential combat
        combat_system.reduce_cooldowns_by_one(self.player.player_id)
        self.output.write(f"[bold yellow]⚡ Cooldowns reduced by 1 turn![/bold yellow]")

        # Show prominent transition message
        transition_msg = f"""
[bold red]═══════════════════════════════════════[/bold red]
[bold yellow]⚠  NEXT ENEMY ENGAGING  ⚠[/bold yellow]

[bold red]{enemy_name}[/bold red] attacks before you can recover!
[bold red]═══════════════════════════════════════[/bold red]
"""
        self.output.write(transition_msg)

        # Show enemy dialogue if available
        if "dialogue" in self.enemy_data:
            self.output.write(f"[bold red]{enemy_name}:[/bold red] {self.enemy_data['dialogue']}")

        # Reset combat UI flag for new enemy
        self._combat_initialized = False

        # Show status and request action
        self._show_combat_status()
        self._request_player_action()

        return True

    def _show_combat_status(self):
        """Display current combat status."""
        # Health status is shown in the Battle Status panel (right side)
        # Combat log with actions is shown in main output panel
        # No need to output anything here - UI handles all display via events
        pass
    
    def _create_health_bar(self, current, maximum, color):
        """Create ASCII health bar."""
        if maximum <= 0:
            return "[gray]▒▒▒▒▒▒▒▒▒▒[/gray]"
        
        bar_length = 20
        filled = int((current / maximum) * bar_length)
        empty = bar_length - filled
        bar = "█" * filled + "▒" * empty
        return f"[{color}]{bar}[/{color}]"
    
    def _request_player_action(self):
        """Request action from player via UI."""
        if not self.is_active:
            return
            
        self.awaiting_action = True
        
        # Get available attacks and usable items for validation
        available_attacks = combat_system.get_available_attacks(self.player, self.player.spells)
        
        usable_items = []
        for item_id, item_data in self.player.inventory.items():
            # Check both old and new combat usability systems
            is_combat_usable = (
                item_data.get("usable") and (
                    "combat_usable" in item_data.get("tags", []) or  # Old system
                    item_data.get("usable_in_combat", False)          # New system
                )
            )
            if is_combat_usable:
                usable_items.append((item_id, item_data))
        
        # Store available actions for validation
        self.all_attacks = available_attacks  # All attacks including those on cooldown
        self.available_attacks = {attack_id: attack_data for attack_id, attack_data in available_attacks.items() if not attack_data.get("on_cooldown", False)}
        self.available_items = {item_id: item_data for item_id, item_data in usable_items}

        # UI will show combat log and available actions via _update_combat_main_output()
        # No need to call update_output here - let the event system handle display
    
    def _show_detailed_actions(self):
        """Show detailed list of available actions."""
        if not self.is_active:
            return

        # The TAB key shows detailed attack info in the Stats panel
        # The combat log in main output shows action history
        # No need to output anything here - UI shows attacks in Stats panel
        # Just continue waiting for action
        self.awaiting_action = True
    
    def _on_combat_action(self, event):
        """Handle combat action selection."""
        if not self.awaiting_action or not self.is_active:
            return
            
        command = event.data.get('choice', '').strip()
        
        if not command:
            self.output.write("[yellow]No command entered. Try again.[/yellow]")
            self._request_player_action()
            return
        
        self.awaiting_action = False
        self._parse_combat_command(command)
    
    def _parse_combat_command(self, command):
        """Parse and execute combat commands."""
        parts = command.lower().split()
        
        if not parts:
            self.output.write("[yellow]No command entered.[/yellow]")
            self._request_player_action()
            return
        
        cmd = parts[0]
        
        # Handle script execution (./ prefix)
        if cmd.startswith('./'):
            attack_name = cmd[2:]  # Remove './' prefix
            if attack_name in self.available_attacks:
                self._process_player_action("attack", attack_name)
            elif attack_name in self.all_attacks:
                # Attack exists but is on cooldown
                attack_data = self.all_attacks[attack_name]
                if attack_data.get("on_cooldown", False):
                    display_name = attack_data.get("name", attack_name)
                    cd_remaining = attack_data.get("cooldown_remaining", 0)
                    self.output.write(
                        f"[bold yellow]⏱ {display_name} is on cooldown for {cd_remaining} turn{'s' if cd_remaining != 1 else ''}![/bold yellow]"
                    )
                    self._request_player_action()
                else:
                    # Attack exists but not in available - process anyway
                    self._process_player_action("attack", attack_name)
            else:
                self.output.write(f"[red]bash: {cmd}: command not found[/red]")
                self._request_player_action()
        
        # Handle use command
        elif cmd == "use" and len(parts) > 1:
            item_input = parts[1]
            resolved = self.player.resolve_inventory_item(item_input)
            if resolved and resolved in self.player.inventory:
                item_data = self.player.inventory[resolved]
                is_combat_usable = (
                    "combat_usable" in item_data.get("tags", []) or
                    item_data.get("usable_in_combat", False)
                )
                if is_combat_usable:
                    self._process_player_action("item", resolved)
                else:
                    item_label = item_data.get("name", resolved)
                    self.output.write(f"[yellow]{item_label} cannot be used in combat.[/yellow]")
                    self._request_player_action()
            else:
                self.output.write(f"[red]Item '{item_input}' not found in inventory.[/red]")
                self._request_player_action()
        
        # Handle flee command
        elif cmd == "flee":
            self._process_player_action("flee", None)
        
        # Handle ls command (show available actions)
        elif cmd == "ls":
            self._show_detailed_actions()
        
        # Handle direct attack names (without ./ prefix)
        elif cmd in self.available_attacks:
            self._process_player_action("attack", cmd)

        # Check if attack exists but is on cooldown
        elif cmd in self.all_attacks:
            attack_data = self.all_attacks[cmd]
            if attack_data.get("on_cooldown", False):
                attack_name = attack_data.get("name", cmd)
                cd_remaining = attack_data.get("cooldown_remaining", 0)
                self.output.write(
                    f"[bold yellow]⏱ {attack_name} is on cooldown for {cd_remaining} turn{'s' if cd_remaining != 1 else ''}![/bold yellow]"
                )
                self._request_player_action()
            else:
                # Attack exists but somehow not in available_attacks - process it anyway
                self._process_player_action("attack", cmd)

        else:
            self.output.write(f"[red]bash: {command}: command not found[/red]")
            # Don't show hint - battle log and UI already show available actions
            self._request_player_action()
    
    def _process_player_action(self, action_type, action_value):
        """Process the selected player action."""
        if action_type == "flee":
            if self.is_boss:
                self.output.write("[bold yellow]You cannot flee from a boss battle![/bold yellow]")
                self._request_player_action()
                return
            else:
                self.output.write("[bold magenta]You fled from combat.[/bold magenta]")
                self._end_combat(fled=True)
                return
        
        elif action_type == "item":
            # Handle item usage in combat
            item_data = self.player.inventory.get(action_value)
            if not item_data:
                self.output.write(f"[red]Item '{action_value}' not found in inventory.[/red]")
                self._request_player_action()
                return

            # Handle healing items - support legacy and new combat_effects formats
            heal_amount = 0
            combat_effects = item_data.get("combat_effects", {})
            if "player_heal" in combat_effects:
                heal_amount = combat_effects["player_heal"]
            elif "healing" in item_data:
                heal_amount = item_data["healing"]
            elif isinstance(item_data.get("on_use"), dict) and "heal" in item_data["on_use"]:
                heal_amount = item_data["on_use"]["heal"]

            actual_heal = 0
            if heal_amount > 0:
                actual_heal = self.player.heal(heal_amount)

            # Heal-over-time consumables (e.g. stable_cache)
            if "player_heal_over_time" in combat_effects:
                hot_amount = combat_effects["player_heal_over_time"]
                duration = combat_effects.get("duration_turns", 3)
                per_turn = max(1, hot_amount // duration)
                self.player.add_status_effect(
                    f"{action_value}_hot",
                    {"type": "heal_over_time", "heal_per_turn": per_turn,
                     "name": item_data.get("name", action_value)},
                    duration
                )

            # Mana restore consumables
            if "player_mana_restore" in combat_effects and hasattr(self.player, "restore_mana"):
                self.player.restore_mana(combat_effects["player_mana_restore"])

            # Handle damage boost items
            if "damage_boost" in item_data:
                boost = item_data["damage_boost"]
                # Temporary damage boost could be implemented here

            # Handle consumable items (remove after use) - support both formats
            should_consume = (
                item_data.get("consumable", False) or           # Old format
                item_data.get("consumed_on_use", False)         # New format
            )
            if should_consume:
                self.player.remove_from_inventory(action_value)
            
            # Build detailed message for item usage. Make a heal pop so the player
            # clearly sees it landed even when the enemy also hits this turn.
            item_name = item_data.get('name', action_value)
            if actual_heal > 0:
                item_message = (
                    f"[bold green]💚 {self.player.name} used {item_name} — "
                    f"+{actual_heal} HP![/bold green]"
                )
            else:
                item_message = f"{self.player.name} used {item_name}"

            # Emit combat action result event for item usage
            event_bus.emit_event(
                EventType.COMBAT_ACTION_RESULT,
                {
                    "actor": "player",
                    "action": "item",
                    "item_name": action_value,
                    "message": item_message,
                    "damage": 0,
                    "healing": actual_heal if heal_amount > 0 else 0,
                    "success": True
                },
                "CombatSession"
            )

        elif action_type == "attack":
            attack_result = combat_system.perform_attack(self.player, action_value)

            # Emit combat action result event (UI will display via combat log)
            event_bus.emit_event(
                EventType.COMBAT_ACTION_RESULT,
                {
                    "actor": "player",
                    "action": "attack",
                    "attack_name": action_value,
                    "message": attack_result['message'],
                    "damage": attack_result.get("damage", 0),
                    "success": attack_result.get("success", False)
                },
                "CombatSession"
            )

            if attack_result["success"]:
                self.enemy_health -= attack_result["damage"]
                if attack_result["healing_amount"] > 0:
                    self.player.heal(attack_result["healing_amount"])
        
        # Check if enemy is defeated
        if self.enemy_health <= 0:
            enemy_name = self.enemy_data.get("name", self.enemy_id)
            self.output.write(f"\n[bold green]Victory! You defeated {enemy_name}![/bold green]")

            # Emit enemy defeated event (for loot, achievements, etc)
            event_bus.emit_event(
                EventType.ENEMY_DEFEATED,
                {
                    "enemy_id": self.enemy_id,
                    "player_name": self.player.name
                },
                "CombatSession"
            )

            # Award harvesting cycles (XP) from the enemy's authored experience value.
            base_cycles = self.enemy_data.get("experience", 50)
            is_boss = self.enemy_data.get("boss_room", False) or self.enemy_data.get("boss_enemy", False)
            if is_boss:
                base_cycles *= 3
            # Scale XP by difficulty mode (easier = faster leveling).
            from src import difficulty
            base_cycles = difficulty.scale_xp(base_cycles)

            old_level = self.player.level
            self.player.harvest_cycles(base_cycles)
            new_level = self.player.level

            # Display cycles gained
            self.output.write(f"[cyan]+{base_cycles} Harvesting Cycles[/cyan]")

            # Check if player leveled up
            if new_level > old_level:
                self.output.write(f"[bold yellow]⬆ LEVEL UP! You are now level {new_level}![/bold yellow]")
                self.output.write(f"[green]+10 Max HP, +2 DMG[/green]")

            # Check if more enemies in queue
            if self._engage_next_enemy():
                # Next enemy engaged, continue combat
                return
            else:
                # All enemies defeated - end combat
                self.output.write(f"\n[bold green]✓ Area secured - all hostile entities eliminated![/bold green]")
                self._end_combat(victory=True)
                return
        
        # Enemy's turn
        self._enemy_turn()
        
        # Check if player is defeated
        if not self.player.is_alive():
            self._end_combat(defeat=True)
            return
        
        # Continue combat
        combat_system.update_cooldowns(self.player)
        self.player.update_status_effects()
        
        # Update UI with new health values
        self._update_ui_panels()
        
        self._show_combat_status()
        self._request_player_action()
    
    def _enemy_turn(self):
        """Process enemy's turn."""
        enemy_name = self.enemy_data.get("name", self.enemy_id)

        damage = self.enemy_damage
        self.player.take_damage(damage)

        # Emit combat action result event for enemy action (UI will display via combat log)
        event_bus.emit_event(
            EventType.COMBAT_ACTION_RESULT,
            {
                "actor": "enemy",
                "action": "attack",
                "attack_name": "basic_attack",
                "message": f"{enemy_name} attacked ({damage} dmg)",
                "damage": damage,
                "success": True
            },
            "CombatSession"
        )

        # Update UI with new player health
        self._update_ui_panels()
    
    def _update_ui_panels(self):
        """Update UI panels during combat."""
        # Emit events to update UI panels
        from src.events import event_bus, EventType

        # Build updated combat view with current health values
        combat_view = ViewBuilder.build_combat_view(
            self.player,
            self.enemy_data,
            self.enemy_health,
            combat_system
        )

        # Emit frame update so UI shows current health and cooldowns
        event_bus.emit_event(
            EventType.COMBAT_FRAME_UPDATED,
            combat_view.to_dict(),
            "CombatSession"
        )

        # Also update player stats
        stats_view = ViewBuilder.build_stats_view(self.player)
        event_bus.emit_event(
            EventType.PLAYER_STATS_CHANGED,
            stats_view.to_dict(),
            "CombatSession"
        )
    
    def _end_combat(self, victory=False, defeat=False, fled=False):
        """End the combat session."""
        self.is_active = False
        self.awaiting_action = False

        # Unsubscribe from events
        event_bus.unsubscribe(EventType.COMBAT_ACTION_SELECTED, self._on_combat_action)

        if defeat:
            self.output.write("\n[bold red]You have been defeated.[/bold red]")

        # Reset cooldowns after combat ends (normal or fled)
        combat_system.reset_cooldowns(self.player)

        # Emit combat ended event with primitive data only
        event_bus.emit_event(
            EventType.COMBAT_ENDED,
            {
                "victory": victory,
                "defeat": defeat,
                "fled": fled,
                "enemy_id": self.enemy_id,
                "enemies_defeated": self.current_enemy_index + (1 if victory else 0)
            },
            "CombatSession"
        )

# Create a singleton instance that can be imported elsewhere
combat_system = CombatSystem() 
