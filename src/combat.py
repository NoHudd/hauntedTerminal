#!/usr/bin/env python3
import os
import yaml
import random
from debug_tools import debug_log

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
            message = f"You use {attack_data['name']} for {damage} damage ({player_base_damage} base + {bonus_damage} bonus)!"
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

# Create a singleton instance that can be imported elsewhere
combat_system = CombatSystem() 