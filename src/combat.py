#!/usr/bin/env python3
import yaml
import random
from utils.debug_tools import debug_log
from src.events import event_bus, EventType

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
        """Get available attacks for a specific character class."""
        if player_class == "fighter":
            attacks = ["strike", "power_strike", "shield_bash"]
        elif player_class == "mage":
            attacks = ["arcane_bolt", "fireball", "frost_nova"]
        elif player_class == "celtic":
            attacks = ["nature_strike", "ancient_fury", "healing_strike"]
        elif player_class == "guardian":
            attacks = ["strike", "power_strike", "shield_bash"]  # Guardian uses fighter attacks
        else:
            attacks = ["strike"]  # Default attack for unknown class
            
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

        if random.randint(1, 100) > attack_accuracy:
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
        
        message = f"You use {attack_data['name']} for {damage} damage!"
        if bonus_damage > 0: # Show total damage and bonus if bonus damage exists
            message = f"You use {attack_data['name']} for {damage} damage ({player_base_damage} base + {bonus_damage} weapon bonus)!"
        else: # Otherwise, just show total damage
            message = f"You use {attack_data['name']} for {damage} damage!"

        if healing_amount > 0:
            message += f" You also heal for {healing_amount} health."
        
        if enemy_damage_reduction > 0:
            message += f" Enemy damage reduced by {int(enemy_damage_reduction * 100)}% next turn."
            
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
        if learned_spells and player_class in ["mage", "celtic"]: # Ensure only spellcasting classes get spells
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
    
    def __init__(self, player, enemy_id, enemy_data, ui):
        """Initialize a combat session."""
        self.player = player
        self.enemy_id = enemy_id
        self.enemy_data = enemy_data
        self.ui = ui
        self.enemy_health = enemy_data.get("health", 50)
        self.enemy_max_health = self.enemy_health
        self.enemy_damage = enemy_data.get("damage", 10)
        self.is_boss = enemy_data.get("is_boss", False)
        self.is_active = True
        self.awaiting_action = False
        
        debug_log(f"CombatSession created: Player vs {enemy_id} (Health: {self.enemy_health})")
        
        # Subscribe to combat events
        event_bus.subscribe(EventType.COMBAT_ACTION_SELECTED, self._on_combat_action)
    
    def start(self):
        """Start the combat session."""
        enemy_name = self.enemy_data.get("name", self.enemy_id)
        debug_log(f"Starting combat with {enemy_name}")
        
        # Build initial combat display
        combat_intro = f"[bold red]⚔️  Combat initiated with {enemy_name}![/bold red]"
        if "dialogue" in self.enemy_data:
            combat_intro += f"\n[bold red]{enemy_name}:[/bold red] {self.enemy_data['dialogue']}"
        
        self.ui.update_output(combat_intro)
        
        # Emit combat started event
        event_bus.emit_event(
            EventType.COMBAT_STARTED,
            {"session": self, "player": self.player, "enemy": self.enemy_data},
            "CombatSession"
        )
        
        self._show_combat_status()
        self._request_player_action()
    
    def _show_combat_status(self):
        """Display current combat status."""
        player_health_bar = self._create_health_bar(self.player.health, self.player.max_health, "green")
        enemy_health_bar = self._create_health_bar(self.enemy_health, self.enemy_max_health, "red")
        
        enemy_name = self.enemy_data.get("name", self.enemy_id)
        
        # Build the status display as a single block
        status_block = f"""
[bold]Your Health:[/bold] {self.player.health}/{self.player.max_health}
{player_health_bar}
[bold red]{enemy_name}'s Health:[/bold red] {self.enemy_health}
{enemy_health_bar}"""
        
        # Check if this is initial combat display or ongoing
        if not hasattr(self, '_combat_initialized'):
            # First time showing combat status - use update_output to start fresh
            self.ui.update_output(status_block)
            self._combat_initialized = True
        else:
            # Ongoing combat - append status updates
            self.ui.append_output("\n" + "─" * 50)  # Separator line
            self.ui.append_output(status_block)
    
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
        self.available_attacks = {attack_id: attack_data for attack_id, attack_data in available_attacks.items() if not attack_data.get("on_cooldown", False)}
        self.available_items = {item_id: item_data for item_id, item_data in usable_items}
        
        # Show available actions in a concise format
        self.ui.update_output(f"\n[bold red]⚔️ Your turn![/bold red] Type [cyan]'ls'[/cyan] to see all actions or use:")
        
        # Show quick reference
        quick_actions = []
        attack_names = list(self.available_attacks.keys())[:2]  # Show first 2 attacks
        for attack_id in attack_names:
            quick_actions.append(f"[cyan]./{attack_id}[/cyan]")
        
        if usable_items:
            item_name = usable_items[0][0]
            quick_actions.append(f"[yellow]use {item_name}[/yellow]")
        
        quick_actions.append("[magenta]flee[/magenta]")
        
        self.ui.update_output(" | ".join(quick_actions))
    
    def _show_detailed_actions(self):
        """Show detailed list of available actions."""
        if not self.is_active:
            return
            
        # Get available attacks
        available_attacks = combat_system.get_available_attacks(self.player, self.player.spells)
        base_damage = self.player.calculate_damage()
        
        self.ui.update_output("\n[bold]Available Executables:[/bold]")
        
        for attack_id, attack_data in available_attacks.items():
            attack_name = attack_data.get("name", attack_id)
            bonus_damage = attack_data.get("bonus_damage", 0)
            on_cooldown = attack_data.get("on_cooldown", False)
            
            script_name = f"./{attack_id}"
            total_damage = base_damage + bonus_damage
            
            if on_cooldown:
                cooldown_remaining = attack_data.get('cooldown_remaining', 0)
                self.ui.update_output(f"[gray]-rwx------ {script_name}  (cooldown: {cooldown_remaining} turns)[/gray]")
            else:
                damage_info = f"({total_damage} dmg)" if bonus_damage > 0 else f"({base_damage} dmg)"
                self.ui.update_output(f"[cyan]-rwxr-xr-x {script_name}[/cyan]  {damage_info}")
        
        # Show usable items
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
        
        if usable_items:
            self.ui.update_output("\n[bold]Usable Items:[/bold]")
            for item_id, item_data in usable_items:
                item_name = item_data.get("name", item_id)
                self.ui.update_output(f"[yellow]{item_name}[/yellow] - use with: [cyan]use {item_id}[/cyan]")
        
        # Show commands
        self.ui.update_output(f"\n[bold]Commands:[/bold] [cyan]./attack_name[/cyan], [yellow]use item[/yellow], [magenta]flee[/magenta]")
        
        # Continue waiting for action
        self.awaiting_action = True
    
    def _on_combat_action(self, event):
        """Handle combat action selection."""
        if not self.awaiting_action or not self.is_active:
            return
            
        command = event.data.get('choice', '').strip()
        
        if not command:
            self.ui.update_output("[yellow]No command entered. Try again.[/yellow]")
            self._request_player_action()
            return
        
        self.awaiting_action = False
        self._parse_combat_command(command)
    
    def _parse_combat_command(self, command):
        """Parse and execute combat commands."""
        parts = command.lower().split()
        
        if not parts:
            self.ui.update_output("[yellow]No command entered.[/yellow]")
            self._request_player_action()
            return
        
        cmd = parts[0]
        
        # Handle script execution (./ prefix)
        if cmd.startswith('./'):
            attack_name = cmd[2:]  # Remove './' prefix
            if attack_name in self.available_attacks:
                self._process_player_action("attack", attack_name)
            else:
                self.ui.update_output(f"[red]bash: {cmd}: command not found[/red]")
                self._request_player_action()
        
        # Handle use command
        elif cmd == "use" and len(parts) > 1:
            item_name = parts[1]
            if item_name in self.available_items:
                self._process_player_action("item", item_name)
            elif item_name in self.player.inventory:
                # Check if item is usable in combat
                item_data = self.player.inventory[item_name]
                # Check both old and new combat usability systems
                is_combat_usable = (
                    "combat_usable" in item_data.get("tags", []) or  # Old system
                    item_data.get("usable_in_combat", False)          # New system
                )
                if is_combat_usable:
                    self._process_player_action("item", item_name)
                else:
                    self.ui.update_output(f"[yellow]{item_name} cannot be used in combat.[/yellow]")
                    self._request_player_action()
            else:
                self.ui.update_output(f"[red]Item '{item_name}' not found in inventory.[/red]")
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
        
        else:
            self.ui.update_output(f"[red]bash: {command}: command not found[/red]")
            self.ui.update_output("[dim]Type 'ls' to see available commands[/dim]")
            self._request_player_action()
    
    def _process_player_action(self, action_type, action_value):
        """Process the selected player action."""
        if action_type == "flee":
            if self.is_boss:
                self.ui.update_output("[bold yellow]You cannot flee from a boss battle![/bold yellow]")
                self._request_player_action()
                return
            else:
                self.ui.update_output("[bold magenta]You fled from combat.[/bold magenta]")
                self._end_combat(fled=True)
                return
        
        elif action_type == "item":
            # Handle item usage in combat
            item_data = self.player.inventory.get(action_value)
            if not item_data:
                self.ui.update_output(f"[red]Item '{action_value}' not found in inventory.[/red]")
                self._request_player_action()
                return
            
            # Process item effects
            self.ui.append_output(f"[yellow]📦 Using {item_data.get('name', action_value)}...[/yellow]")
            
            # Handle healing items - support both old and new formats
            heal_amount = 0
            if "healing" in item_data:
                # Old format: direct healing field
                heal_amount = item_data["healing"]
            elif "on_use" in item_data and "heal" in item_data["on_use"]:
                # New format: on_use.heal field
                heal_amount = item_data["on_use"]["heal"]
            
            if heal_amount > 0:
                old_health = self.player.health
                self.player.heal(heal_amount)
                actual_heal = self.player.health - old_health
                self.ui.append_output(f"[green]✨ You healed {actual_heal} HP![/green]")
                
                # Show on_use message if available
                if "on_use" in item_data and "message" in item_data["on_use"]:
                    self.ui.append_output(f"[italic]{item_data['on_use']['message']}[/italic]")
            
            # Handle damage boost items
            if "damage_boost" in item_data:
                boost = item_data["damage_boost"]
                self.ui.update_output(f"[green]Your damage increased by {boost}![/green]")
                # Temporary damage boost could be implemented here
            
            # Handle consumable items (remove after use) - support both formats
            should_consume = (
                item_data.get("consumable", False) or           # Old format
                item_data.get("consumed_on_use", False)         # New format
            )
            if should_consume:
                self.player.remove_from_inventory(action_value)
                self.ui.update_output(f"[dim]Used up {item_data.get('name', action_value)}[/dim]")
            
            # Show item description/effect
            if "effect_message" in item_data:
                self.ui.update_output(f"[italic]{item_data['effect_message']}[/italic]")
            
            # Emit combat action result event for item usage
            event_bus.emit_event(
                EventType.COMBAT_ACTION_RESULT,
                {
                    "actor": "player",
                    "action": "item",
                    "item_name": action_value,
                    "message": f"Used {item_data.get('name', action_value)}",
                    "damage": 0,
                    "success": True
                },
                "CombatSession"
            )
        
        elif action_type == "attack":
            attack_result = combat_system.perform_attack(self.player, action_value)
            self.ui.append_output(f"[green]⚔️ {attack_result['message']}[/green]")
            
            # Emit combat action result event
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
        self.ui.append_output(f"[bold red]🗡️ {enemy_name} attacks you![/bold red]")
        
        damage = self.enemy_damage
        self.player.take_damage(damage)
        self.ui.append_output(f"[red]💔 You took {damage} damage![/red]")
        
        # Emit combat action result event for enemy action
        event_bus.emit_event(
            EventType.COMBAT_ACTION_RESULT,
            {
                "actor": "enemy",
                "action": "attack",
                "attack_name": "basic_attack",
                "message": f"{enemy_name} deals {damage} damage to you!",
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
        
        # Update player stats to refresh combat panel
        event_bus.emit_event(
            EventType.PLAYER_STATS_CHANGED,
            {"player": self.player},
            "CombatSession"
        )
    
    def _end_combat(self, victory=False, defeat=False, fled=False):
        """End the combat session."""
        self.is_active = False
        self.awaiting_action = False
        
        # Unsubscribe from events
        event_bus.unsubscribe(EventType.COMBAT_ACTION_SELECTED, self._on_combat_action)
        
        if victory:
            enemy_name = self.enemy_data.get("name", self.enemy_id)
            self.ui.update_output(f"\n[bold green]Victory! You defeated {enemy_name}![/bold green]")
        elif defeat:
            self.ui.update_output("\n[bold red]You have been defeated.[/bold red]")
        
        # Reset cooldowns
        combat_system.reset_cooldowns(self.player)
        
        # Emit combat ended event
        event_bus.emit_event(
            EventType.COMBAT_ENDED,
            {
                "session": self,
                "victory": victory,
                "defeat": defeat,
                "fled": fled,
                "enemy_id": self.enemy_id
            },
            "CombatSession"
        )

# Create a singleton instance that can be imported elsewhere
combat_system = CombatSystem() 