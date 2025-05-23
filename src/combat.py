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
        self.active_cooldowns = {}  # player_id -> {attack_id -> remaining_cooldown}
    
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
    
    def calculate_damage(self, player_total_damage, attack_id):
        """Calculate damage for an attack using simplified formula.
        
        Formula: player_total_damage + attack_bonus_damage from YAML
        """
        debug_log(f"Calculating damage for attack '{attack_id}' with base damage {player_total_damage}")
        attack_data = self.get_attack_data(attack_id)
        if not attack_data:
            debug_log(f"No attack data found for '{attack_id}', using base damage only")
            return player_total_damage  # Just use total damage if attack not found
        
        # Use bonus_damage or fallback to damage for backward compatibility
        bonus_damage = attack_data.get('bonus_damage', attack_data.get('damage', 0))
        total_damage = player_total_damage + bonus_damage
        debug_log(f"Attack '{attack_id}' calculation: {player_total_damage} (base) + {bonus_damage} (bonus) = {total_damage}")
        return total_damage
    
    def perform_attack(self, player_id, player_total_damage, attack_id):
        """Execute an attack and return the results.
        
        Args:
            player_id: Unique identifier for the player
            player_total_damage: Player's total damage value
            attack_id: ID of the attack to perform
            
        Returns:
            dict: Results of the attack including damage, message, etc.
        """
        debug_log(f"Player {player_id} initiating attack '{attack_id}' with base damage {player_total_damage}")
        
        # Initialize cooldowns if not already done
        if player_id not in self.active_cooldowns:
            debug_log(f"Cooldowns not initialized for player {player_id}, initializing now")
            self.initialize_cooldowns(player_id)
        
        # Get attack data
        attack_data = self.get_attack_data(attack_id)
        if not attack_data:
            debug_log(f"Attack '{attack_id}' not found, falling back to basic attack")
            # Fallback to basic attack if attack not found
            return {
                "damage": player_total_damage,
                "message": "You attack with your weapon.",
                "enemy_damage_reduction": 0,
                "healing": 0
            }
        
        # Check if attack is on cooldown
        if attack_id in self.active_cooldowns[player_id] and self.active_cooldowns[player_id][attack_id] > 0:
            debug_log(f"Attack '{attack_id}' is on cooldown ({self.active_cooldowns[player_id][attack_id]} turns remaining)")
            return {
                "damage": player_total_damage,
                "message": f"{attack_data['name']} is on cooldown! You use a regular attack instead.",
                "enemy_damage_reduction": 0,
                "healing": 0
            }
        
        # Calculate damage using simplified formula
        damage = self.calculate_damage(player_total_damage, attack_id)
        
        # Get bonus damage for the message
        bonus_damage = attack_data.get('bonus_damage', attack_data.get('damage', 0))
        
        # Set cooldown
        cooldown = attack_data.get('cooldown', 0)
        if cooldown > 0:
            self.active_cooldowns[player_id][attack_id] = cooldown
            debug_log(f"Setting cooldown for '{attack_id}': {cooldown} turns")
        
        # Get additional effects
        healing = attack_data.get('healing', 0)
        enemy_damage_reduction = attack_data.get('enemy_damage_reduction', 0)
        
        debug_log(f"Attack '{attack_id}' results: damage={damage}, healing={healing}, enemy_damage_reduction={enemy_damage_reduction}")
        
        # Build message
        message = f"You use {attack_data['name']} for {damage} damage!"
        
        if healing > 0:
            message += f" You also heal for {healing} health."
        
        if enemy_damage_reduction > 0:
            message += f" Enemy damage reduced by {int(enemy_damage_reduction * 100)}% next turn."
        
        return {
            "damage": damage,
            "message": message,
            "enemy_damage_reduction": enemy_damage_reduction,
            "healing": healing,
            "bonus_damage": bonus_damage  # Include bonus_damage in the result
        }
    
    def update_cooldowns(self, player_id):
        """Update cooldowns at the end of a combat turn."""
        if player_id not in self.active_cooldowns:
            debug_log(f"No cooldowns to update for player {player_id}")
            return
        
        updated_attacks = []
        for attack_id in list(self.active_cooldowns[player_id].keys()):
            if self.active_cooldowns[player_id][attack_id] > 0:
                old_cooldown = self.active_cooldowns[player_id][attack_id]
                self.active_cooldowns[player_id][attack_id] -= 1
                new_cooldown = self.active_cooldowns[player_id][attack_id]
                updated_attacks.append(f"{attack_id}: {old_cooldown}->{new_cooldown}")
        
        if updated_attacks:
            debug_log(f"Updated cooldowns for player {player_id}: {', '.join(updated_attacks)}")
    
    def reset_cooldowns(self, player_id):
        """Reset all cooldowns for a player (used when combat ends)."""
        debug_log(f"Resetting all cooldowns for player {player_id}")
        self.active_cooldowns[player_id] = {}
    
    def get_available_attacks(self, player_id, player_class, learned_spells=None):
        """Get available attacks for a player, including learned spells."""
        debug_log(f"Getting available attacks for player {player_id} (class: {player_class})")
        if player_id not in self.active_cooldowns:
            debug_log(f"Cooldowns not initialized for player {player_id}, initializing now")
            self.initialize_cooldowns(player_id)
        
        # Get base attacks for class
        base_attacks = self.get_attacks_for_class(player_class)
        
        # Add learned spells if provided and class can use spells
        spell_attacks = []
        if learned_spells and player_class in ["mage", "celtic"]:
            for spell in learned_spells:
                spell_id = spell.get('spell_name', '').lower().replace(' ', '_')
                if spell_id in self.attacks:
                    spell_attacks.append(spell_id)
            
            if spell_attacks:
                debug_log(f"Added {len(spell_attacks)} learned spell attacks: {spell_attacks}")
        
        # Combine all attacks
        all_attacks = base_attacks + spell_attacks
        debug_log(f"Combined attacks list: {all_attacks}")
        
        # Build available attacks with cooldown info
        available_attacks = {}
        for attack_id in all_attacks:
            attack_data = self.get_attack_data(attack_id)
            if not attack_data:
                debug_log(f"No data found for attack '{attack_id}', skipping")
                continue
                
            attack_copy = attack_data.copy()
            
            # Use bonus_damage or fallback to damage for backward compatibility
            if 'bonus_damage' not in attack_copy and 'damage' in attack_copy:
                attack_copy['bonus_damage'] = attack_copy['damage']
                
            if attack_id in self.active_cooldowns[player_id] and self.active_cooldowns[player_id][attack_id] > 0:
                attack_copy["on_cooldown"] = True
                attack_copy["cooldown_remaining"] = self.active_cooldowns[player_id][attack_id]
                debug_log(f"Attack '{attack_id}' is currently on cooldown: {attack_copy['cooldown_remaining']} turns remaining")
            else:
                attack_copy["on_cooldown"] = False
                
            available_attacks[attack_id] = attack_copy
            
        debug_log(f"Returning {len(available_attacks)} available attacks for player {player_id}")
        return available_attacks

# Create a singleton instance that can be imported elsewhere
combat_system = CombatSystem() 