from utils.debug_tools import debug_log
from src.data_loader import load_class_data, load_weapon_data, get_abilities_for_class
import random

class Player:
    """Class representing the player in the game."""

    def __init__(self, name="", player_class="guardian", current_room="home_grove"):
        """Initialize a new player."""
        self.name = name
        self.player_class = player_class.lower()
        self.current_room = current_room

        # Core stats
        self.max_health = 100
        self.health = 100
        self.total_damage = 5
        self.inventory = {}
        self.equipped_weapon = None
        self.status_effects = {}
        # self.cooldowns = {} # Removed: Cooldowns are now managed by CombatSystem
        self.spells = []  # For special abilities later
        self.class_description = ""

        self.permanent_health_boost = 0
        self.permanent_damage_boost = 0

        # Load class info dynamically
        self.load_class_attributes()

        # Player ID for cooldowns
        self.player_id = id(self)

    def load_class_attributes(self):
        """Load stats, starter weapon, abilities from external class data."""
        classes_data = load_class_data()
        class_info = classes_data.get(self.player_class)

        if not class_info:
            debug_log(f"Invalid class '{self.player_class}' provided, defaulting to guardian.")
            class_info = classes_data.get("guardian")

        self.max_health = class_info.get("base_health", 100)
        self.health = self.max_health
        self.total_damage = class_info.get("base_damage", 5)
        self.class_description = class_info.get("description", "An explorer in the system.")

        debug_log(f"Player class set to {self.player_class} with {self.health} HP and {self.total_damage} base damage.")

        # Load starter weapon
        starter_weapon_id = class_info.get("starter_weapon")
        if starter_weapon_id:
            weapon_info = load_weapon_data(starter_weapon_id)
            if weapon_info:
                self.add_to_inventory(starter_weapon_id, weapon_info)
                self.equip_weapon(starter_weapon_id)

        # Load starter abilities
        self.starter_abilities = class_info.get("starter_abilities", [])

    def add_to_inventory(self, item_id, item_data):
        """Add an item to the player's inventory."""
        self.inventory[item_id] = item_data
        debug_log(f"Added {item_id} to inventory.")
        return True
        
    def remove_from_inventory(self, item_id):
        """Remove an item from the player's inventory."""
        if item_id in self.inventory:
            # If the equipped weapon is being removed, unequip it
            if self.equipped_weapon == item_id:
                self.equipped_weapon = None
            
            debug_log(f"Removing item {item_id} from inventory")
            del self.inventory[item_id]
            return True
        debug_log(f"Failed to remove {item_id} from inventory: item not found")
        return False

    def equip_weapon(self, item_id):
        """Equip a weapon from the inventory."""
        if item_id in self.inventory:
            # Unequip previous weapon bonus if any
            if self.equipped_weapon and self.equipped_weapon in self.inventory:
                old_bonus = self.inventory[self.equipped_weapon].get("damage", 0)
                self.total_damage -= old_bonus
                
            # Equip new weapon
            self.equipped_weapon = item_id
            weapon_bonus = self.inventory[item_id].get("damage", 0)
            self.total_damage += weapon_bonus
            debug_log(f"Equipped weapon {item_id}, total_damage now {self.total_damage}.")
            return True
        return False
        
    def get_inventory_items(self):
        """Get a list of all items in the player's inventory."""
        return list(self.inventory.keys())

    def is_dead(self):
        """Check if the player's health is at or below zero."""
        return self.health <= 0
    
    def has_item(self, item_id):
        """Check if the player has a specific item."""
        return item_id in self.inventory
    
    def get_item_from_inventory(self, item_id):
        """Get a specific item from the inventory."""
        return self.inventory.get(item_id)
    
    def can_use_item(self, item):
        """Check if the player can use this item based on class restrictions."""
        # Check class_restriction
        if "class_restriction" in item:
            allowed_classes = item["class_restriction"]
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            return self.player_class.lower() in [c.lower() for c in allowed_classes]
        
        # Check allowed_classes
        if "allowed_classes" in item:
            allowed_classes = item["allowed_classes"]
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            return self.player_class.lower() in [c.lower() for c in allowed_classes]
            
        # No restrictions means anyone can use it
        return True

    def apply_status_effect(self, effect_id, effect_data):
        """Apply a status effect to the player."""
        self.status_effects[effect_id] = {
            "duration": effect_data.get("duration", 3),
            "effect": effect_data
        }
        debug_log(f"Applied status effect {effect_id} for {self.status_effects[effect_id]['duration']} turns.")
        
    def add_status_effect(self, effect_id, effect_data, duration=3):
        """Add a status effect to the player."""
        self.status_effects[effect_id] = {
            "duration": duration,
            "effect": effect_data,
            "name": effect_data.get("name", "Unknown Effect"),
            "description": effect_data.get("description", "")
        }
        debug_log(f"Added status effect {effect_id} for {duration} turns")
        return True

    def update_status_effects(self):
        """Update and expire active status effects. Returns list of expiration messages."""
        expired = []
        messages = []
        
        for effect_id, data in list(self.status_effects.items()):
            data["duration"] -= 1
            if data["duration"] <= 0:
                expired.append(effect_id)
                effect_name = data.get("name", effect_id)
                messages.append(f"The {effect_name} effect has worn off.")

        for effect_id in expired:
            self.remove_status_effect(effect_id)
            
        return messages

    def remove_status_effect(self, effect_id):
        """Remove a status effect."""
        if effect_id in self.status_effects:
            debug_log(f"Status effect {effect_id} has expired.")
            del self.status_effects[effect_id]

    def clear_status_effects(self):
        """Clear all active status effects."""
        self.status_effects.clear()
        debug_log("All status effects cleared.")

    def get_active_status_effects(self):
        """Return a list of currently active status effects."""
        return [data for _, data in self.status_effects.items()]

    def take_damage(self, amount):
        """Reduce player health by amount."""
        self.health -= amount
        if self.health < 0:
            self.health = 0
        debug_log(f"Player took {amount} damage, health now {self.health}/{self.max_health}.")

    def heal(self, amount):
        """Heal the player by a certain amount."""
        old_health = self.health
        self.health += amount
        if self.health > self.max_health:
            self.health = self.max_health
        actual_heal = self.health - old_health
        debug_log(f"Player healed {actual_heal}, health now {self.health}/{self.max_health}.")
        return self.health
        
    def is_alive(self):
        """Check if the player is alive."""
        return self.health > 0
        
    def calculate_damage(self):
        """Calculate the player's total damage including weapon and status effects."""
        # Start with base damage
        total = self.total_damage
        
        # Add status effect bonuses
        for effect_id, data in self.status_effects.items():
            effect = data.get("effect", {})
            damage_bonus = effect.get("damage_bonus", 0)
            total += damage_bonus
            
        return total
        
    def get_combat_action(self, combat_system, ui):
        """
        Display available combat actions (attacks and items) and get the player's choice.
        """
        import readchar

        # Get available attacks from the combat system
        available_attacks = combat_system.get_available_attacks(self, self.spells)
        
        # Get usable items from inventory
        usable_items = []
        for item_id, item_data in self.inventory.items():
            if item_data.get("usable") and "combat_usable" in item_data.get("tags", []):
                usable_items.append((item_id, item_data))

        # Display options to the player via the UI
        ui.update_output("\n[bold]Choose your action:[/bold]")
        
        action_keys = {}
        key_idx = 1
        
        # Display attacks
        base_damage = self.calculate_damage()
        ui.update_output(f"[bold]Base Attack Damage:[/bold] {base_damage}")
        for attack_id, attack_data in available_attacks.items():
            attack_name = attack_data.get("name", attack_id)
            bonus_damage = attack_data.get("bonus_damage", 0)
            cooldown = attack_data.get("cooldown", 0)
            on_cooldown = attack_data.get("on_cooldown", False)
            
            description = attack_data.get("description", "")
            healing = attack_data.get("healing", 0)
            
            total_damage = base_damage + bonus_damage
            
            effect_desc = []
            if bonus_damage > 0:
                effect_desc.append(f"{total_damage} dmg")
            else:
                effect_desc.append(f"{base_damage} dmg")
            if healing > 0:
                effect_desc.append(f"Heal {healing} HP")
            if cooldown > 0:
                effect_desc.append(f"CD: {cooldown}")

            effects = ", ".join(effect_desc)
            
            if on_cooldown:
                ui.update_output(f"{key_idx}: [gray]{attack_name} ({effects}) - On Cooldown ({attack_data.get('cooldown_remaining', 0)} turns)[/gray]")
            else:
                ui.update_output(f"{key_idx}: [cyan]{attack_name}[/cyan] - {description} ({effects})")
                action_keys[str(key_idx)] = attack_id
            key_idx += 1
            
        # Display items
        if usable_items:
            ui.update_output("\n[bold]Items:[/bold]")
            for item_id, item_data in usable_items:
                item_name = item_data.get("name", item_id)
                ui.update_output(f"{key_idx}: [yellow]{item_name}[/yellow] - {item_data.get('description', '')}")
                action_keys[str(key_idx)] = item_id
                key_idx += 1
        
        # Add a flee option
        flee_key = 'f'
        ui.update_output(f"{flee_key}: [bold magenta]Flee Combat[/bold magenta]")
        action_keys[flee_key] = "flee"

        # Get player input
        choice = None
        while choice not in action_keys:
            ui.update_input_panel("Your choice: ", cursor_visible=True)
            choice = readchar.readkey()
            ui.update_input_panel(f"Your choice: {choice}", cursor_visible=False)
            if choice not in action_keys:
                ui.update_output("[red]Invalid choice.[/red]")
        
        return action_keys[choice]
        
    # def update_cooldowns(self): # Fully removed as it's handled by CombatSystem
    #     """Reduce all ability cooldowns by 1."""
    #     for attack_id in list(self.cooldowns.keys()):
    #         self.cooldowns[attack_id] -= 1
    #         if self.cooldowns[attack_id] <= 0:
    #             debug_log(f"Cooldown for '{attack_id}' has expired")
    #             del self.cooldowns[attack_id]
                
    def increase_max_health(self, amount):
        """Permanently increase maximum health."""
        old_max = self.max_health
        self.permanent_health_boost += amount
        self.max_health += amount
        # Also heal the player by the same amount
        self.health += amount
        debug_log(f"Player max health increased by {amount} ({old_max} -> {self.max_health})")
        return self.max_health
        
    def increase_damage(self, amount):
        """Permanently increase total damage."""
        self.permanent_damage_boost += amount
        self.total_damage += amount
        return self.total_damage
        
    def learn_spell(self, spell_data):
        """Learn a new spell (for mage/celtic classes)."""
        if self.player_class not in ["mage", "celtic"]:
            return False
            
        self.spells.append(spell_data)
        return True
        
    def move_to(self, room_id):
        """Move the player to a different room."""
        debug_log(f"Moving player from {self.current_room} to {room_id}")
        self.current_room = room_id
        return True
        
    @classmethod
    def from_dict(cls, data):
        """Create a player instance from a dictionary."""
        player = cls(data.get("name", ""), data.get("player_class", "guardian"), data.get("current_room", "home_grove"))
        player.health = data["health"]
        player.max_health = data["max_health"]
        player.total_damage = data.get("total_damage", player.total_damage)
        player.permanent_health_boost = data.get("permanent_health_boost", 0)
        player.permanent_damage_boost = data.get("permanent_damage_boost", 0)
        player.spells = data.get("spells", [])
        player.inventory = data["inventory"]
        player.equipped_weapon = data["equipped_weapon"]
        return player
    
    def to_dict(self):
        """Convert player data to a dictionary for saving."""
        return {
            "name": self.name,
            "player_class": self.player_class,
            "health": self.health,
            "max_health": self.max_health,
            "total_damage": self.total_damage,
            "permanent_health_boost": self.permanent_health_boost,
            "permanent_damage_boost": self.permanent_damage_boost,
            "spells": self.spells,
            "inventory": self.inventory,
            "equipped_weapon": self.equipped_weapon,
            "current_room": self.current_room
        }
