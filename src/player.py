from utils.debug_tools import debug_log
from src.data_loader import load_class_data, load_weapon_data, get_abilities_for_class, load_consumable_data
import random

# Armor mitigation: defense -> capped percent damage reduction.
ARMOR_MITIGATION_CAP = 33       # max % damage reduced, so a tank can't become unkillable
ARMOR_DEFENSE_TO_PCT = 1.5      # each point of armor `defense` = this many % mitigation
                                # (low factor + this cap lets guardian's def-20/22 pieces
                                #  out-mitigate weaver/shaman def-15 instead of all capping equal)


class Player:
    """Class representing the player in the game."""

    def __init__(self, name="", player_class="guardian", current_room="home_grove"):
        """Initialize a new player."""
        self.name = name
        self.player_class = player_class.lower()
        self.current_room = current_room
        self.previous_room = None  # Track previous room for flee functionality

        # Core stats
        self.max_health = 100
        self.health = 100
        self.total_damage = 5
        self.inventory = {}
        self.equipped_weapon = None
        self.equipped_armor = None
        self.armor_mitigation = 0.0  # fraction 0..(cap/100), from equipped armor's defense
        self.status_effects = {}
        # self.cooldowns = {} # Removed: Cooldowns are now managed by CombatSystem
        self.spells = []  # For special abilities later
        self.run_stats = {"kills": 0, "items_found": 0}  # lifetime-of-run counters
        self.met_npcs: set = set()  # npc ids the player has talked to (greetings fire once)
        self.class_description = ""

        self.permanent_health_boost = 0
        self.permanent_damage_boost = 0

        # Load class info dynamically
        self.load_class_attributes()

        # Player ID for cooldowns - use a more stable identifier
        import uuid
        self.player_id = str(uuid.uuid4())
        
        # Tutorial tracking
        self.tutorial_state = {
            "skip_offered": False,      # Whether skip prompt has been shown
            "first_ls": False,          # Step 1 gate
            "found_weapon": False,      # Step 2 (ls revealed weapon)
            "took_weapon": False,       # Step 2 gate
            "equipped_weapon": False,   # Step 3 gate (also triggers enemy spawn)
            "combat_typed": False,      # Step 4 gate (used typed attack)
            "combat_selection": False,  # Step 5 gate (used TAB + number)
            "navigation_ls": False,     # Step 6 gate (typed ls post-combat)
            "navigation_moved": False,  # Step 6 gate (moved to new room)
            "completed": False          # Step 7 — tutorial fully done
        }

        # Harvesting Cycles (XP System)
        self.harvesting_cycles = 0
        self.level = 1
        self.cycles_to_next_level = 100

        # Story progression flags
        self.story_flags = {
            "identity_retrieved": False,
            "typo_discovered": False,
            "sudo_trial_complete": False,
            "mirror_confronted": False,
            "ending_chosen": None,
            "sudo_quest_active": False,
            "bovine_encountered": False,
            "milk_claimed": False
        }

    def load_class_attributes(self):
        """Load stats, starter weapon, abilities from external class data."""
        classes_data = load_class_data()
        class_info = classes_data.get(self.player_class)

        if not class_info:
            debug_log(f"Invalid class '{self.player_class}' provided, defaulting to guardian.")
            class_info = classes_data.get("guardian")

        self.max_health = class_info.base_health
        self.health = self.max_health
        self.total_damage = class_info.base_damage
        self.class_description = class_info.description

        debug_log(f"Player class set to {self.player_class} with {self.health} HP and {self.total_damage} base damage.")

        # Load starter weapon - DISABLED to force players to learn 'take' command
        # starter_weapon_id = class_info.get("starter_weapon")
        # if starter_weapon_id:
        #     weapon_info = load_weapon_data(starter_weapon_id)
        #     if weapon_info:
        #         self.add_to_inventory(starter_weapon_id, weapon_info)
        #         self.equip_weapon(starter_weapon_id)

        # Load starter abilities
        self.starter_abilities = class_info.starter_abilities

        # Give starter consumables to help survive early game
        self._add_starter_items()

    def _add_starter_items(self):
        """Give the player starter consumables to help survive early game."""
        # Give 1 health packet to start
        health_packet = load_consumable_data("health_packet")
        if health_packet:
            self.inventory["health_packet_1"] = health_packet.copy()
            debug_log("Starter items added: 1x Health Packet")
        else:
            debug_log("WARNING: Could not load health_packet for starter items")

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
            if self.equipped_armor == item_id:
                self.equipped_armor = None
                self.armor_mitigation = 0.0

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

    def equip_armor(self, item_id):
        """Equip an armor piece from inventory; set capped damage mitigation from its defense."""
        if item_id not in self.inventory:
            return False
        self.equipped_armor = item_id
        defense = self.inventory[item_id].get("defense", 0) or 0
        self.armor_mitigation = min(ARMOR_MITIGATION_CAP, defense * ARMOR_DEFENSE_TO_PCT) / 100.0
        debug_log(f"Equipped armor {item_id}, mitigation now {self.armor_mitigation:.0%}.")
        return True
        
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

    def resolve_inventory_item(self, name):
        """Resolve a user-typed name/shortcut to an actual inventory key.

        Handles exact match, prefix match (e.g. 'health_packet' -> 'health_packet_1'),
        common shortcuts ('hp', 'heal', 'pointer', etc.), and substring fallback.
        Returns the inventory key or None.
        """
        if not name:
            return None

        keys = list(self.inventory.keys())
        lower = name.lower()

        # Exact match
        if name in self.inventory:
            return name

        # Prefix match (suffixed instance keys like health_packet_1)
        prefix_matches = [k for k in keys if k.lower().startswith(lower)]
        if len(prefix_matches) == 1:
            return prefix_matches[0]

        shortcuts = {
            "hp": ["health_packet", "stable_cache"],
            "health": ["health_packet", "stable_cache"],
            "heal": ["health_packet", "stable_cache"],
            "potion": ["health_packet", "stable_cache", "overflowing_buffer"],
            "packet": ["health_packet"],
            "buffer": ["overflowing_buffer"],
            "cache": ["stable_cache"],
            "backup": ["legacy_backup"],
            "seed": ["sudo_seed"],
            "shield": ["segfault_shield"],
            "pointer": ["null_pointer"],
            "whisper": ["daemon_whisper"],
        }
        if lower in shortcuts:
            for target in shortcuts[lower]:
                # Try exact then prefix
                if target in self.inventory:
                    return target
                target_matches = [k for k in keys if k.lower().startswith(target.lower())]
                if target_matches:
                    return target_matches[0]

        # Multi-prefix tiebreak: prefer health_packet
        if prefix_matches:
            preferred = [k for k in prefix_matches if "health_packet" in k]
            if preferred:
                return preferred[0]
            return prefix_matches[0]

        # Substring fallback
        substring_matches = [k for k in keys if lower in k.lower()]
        if substring_matches:
            return substring_matches[0]

        return None
    
    def can_use_item(self, item):
        """Check if the player can use this item based on class restrictions."""
        if "allowed_classes" in item:
            allowed_classes = item["allowed_classes"]
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            return self.player_class.lower() in [c.lower() for c in allowed_classes]
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
        """Reduce player health by amount, after equipped-armor mitigation."""
        if amount > 0 and self.armor_mitigation:
            amount = max(1, round(amount * (1 - self.armor_mitigation)))
        self.health -= amount
        if self.health < 0:
            self.health = 0
        debug_log(f"Player took {amount} damage, health now {self.health}/{self.max_health}.")

    def heal(self, amount):
        """Heal the player by a certain amount. Returns actual HP gained."""
        old_health = self.health
        self.health = min(self.health + amount, self.max_health)
        actual_heal = self.health - old_health
        debug_log(f"Player healed {actual_heal}, health now {self.health}/{self.max_health}.")
        return actual_heal
        
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
        # Also heal the player by the same amount, capped at new max
        self.health = min(self.health + amount, self.max_health)
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
        self.previous_room = self.current_room  # Track previous room
        self.current_room = room_id
        return True

    def harvest_cycles(self, amount):
        """Gain harvesting cycles (XP) from defeated enemies."""
        self.harvesting_cycles += amount
        debug_log(f"Player gained {amount} harvesting cycles. Total: {self.harvesting_cycles}/{self.cycles_to_next_level}")

        # Check for level up
        while self.harvesting_cycles >= self.cycles_to_next_level:
            self.level_up()

        return self.harvesting_cycles

    def level_up(self):
        """Level up the player, increasing stats and resetting cycle requirement."""
        self.harvesting_cycles -= self.cycles_to_next_level
        self.level += 1

        # Increase stats
        health_gain = 10
        damage_gain = 2

        self.increase_max_health(health_gain)
        self.increase_damage(damage_gain)

        # Exponentially increasing cycle requirements
        self.cycles_to_next_level = int(self.cycles_to_next_level * 1.5)

        debug_log(f"Player leveled up to level {self.level}! +{health_gain} HP, +{damage_gain} DMG. Next level at {self.cycles_to_next_level} cycles.")

        return {
            "new_level": self.level,
            "health_gain": health_gain,
            "damage_gain": damage_gain,
            "cycles_to_next": self.cycles_to_next_level
        }

    def get_persistent_items(self):
        """Return only items with persistence: 'persistent' tag."""
        persistent = {}
        for item_id, item_data in self.inventory.items():
            persistence = item_data.get("persistence", "persistent")  # Default to persistent for backwards compatibility
            if persistence == "persistent":
                persistent[item_id] = item_data
        return persistent

    def apply_death_penalty(self):
        """Remove ephemeral items on death."""
        ephemeral_items = []
        for item_id, item_data in list(self.inventory.items()):
            persistence = item_data.get("persistence", "persistent")
            if persistence == "ephemeral":
                ephemeral_items.append(item_id)

        # Remove all ephemeral items
        for item_id in ephemeral_items:
            self.remove_from_inventory(item_id)
            debug_log(f"Ephemeral item {item_id} lost on death")

        return ephemeral_items

    def set_story_flag(self, flag, value=True):
        """Set a story progression flag."""
        if flag in self.story_flags:
            self.story_flags[flag] = value
            debug_log(f"Story flag '{flag}' set to {value}")
            return True
        else:
            debug_log(f"Warning: Unknown story flag '{flag}'")
            self.story_flags[flag] = value  # Add it anyway
            return True

    def get_story_flag(self, flag):
        """Get the value of a story flag."""
        return self.story_flags.get(flag, False)

    @classmethod
    def from_dict(cls, data):
        """Create a player instance from a dictionary."""
        player = cls(data.get("name", ""), data.get("player_class", "guardian"), data.get("current_room", "home_grove"))
        # Use .get() with defaults so a legacy or partial save can't KeyError
        # here (previously data["health"]/["inventory"]/["equipped_weapon"] did).
        player.health = data.get("health", player.max_health)
        player.max_health = data.get("max_health", player.max_health)
        player.total_damage = data.get("total_damage", player.total_damage)
        player.permanent_health_boost = data.get("permanent_health_boost", 0)
        player.permanent_damage_boost = data.get("permanent_damage_boost", 0)
        player.previous_room = data.get("previous_room", None)  # Load previous room
        player.spells = data.get("spells", [])
        player.inventory = data.get("inventory", {})
        player.run_stats = data.get("runStats", {"kills": 0, "items_found": 0})
        player.met_npcs = set(data.get("metNpcs", []))
        player.equipped_weapon = data.get("equipped_weapon", None)
        # Restore player_id if it exists, otherwise keep the generated one
        if "player_id" in data:
            player.player_id = data["player_id"]
        # Restore tutorial state if it exists
        if "tutorial_state" in data:
            player.tutorial_state = data["tutorial_state"]
        # Restore harvesting cycles and level
        player.harvesting_cycles = data.get("harvesting_cycles", 0)
        player.level = data.get("level", 1)
        player.cycles_to_next_level = data.get("cycles_to_next_level", 100)
        # Restore story flags
        if "story_flags" in data:
            player.story_flags = data["story_flags"]
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
            "current_room": self.current_room,
            "previous_room": self.previous_room,  # Save previous room
            "player_id": self.player_id,
            "tutorial_state": self.tutorial_state,
            "harvesting_cycles": self.harvesting_cycles,
            "level": self.level,
            "cycles_to_next_level": self.cycles_to_next_level,
            "story_flags": self.story_flags,
            "runStats": self.run_stats,
            "metNpcs": sorted(self.met_npcs)
        }
