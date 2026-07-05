#!/usr/bin/env python3
import random
from src import rng
import yaml
import os
from utils.debug_tools import debug_log
from src.events import event_bus, EventType

class GameWorld:
    """Manages the game world, including rooms, items, enemies, and NPCs"""
    
    def __init__(self, rooms, items, enemies, npcs, initialize_state=True):
        """Initialize with data loaded from YAML files
        
        Args:
            rooms, items, enemies, npcs: Game data from YAML files
            initialize_state: Whether to initialize world state from room data (default True)
                             Set to False when loading from save to prevent overwriting loaded state
        """
        import uuid
        self.instance_id = str(uuid.uuid4())[:8]
        debug_log(f"Initializing GameWorld instance {self.instance_id} (initialize_state={initialize_state})")
        self.rooms = rooms
        self.items = items
        self.enemies = enemies
        self.npcs = npcs
        
        # Track which items are in which rooms
        self.item_locations = {}
        
        # Track which enemies are in which rooms
        self.enemy_locations = {}
        
        # Track which NPCs are in which rooms
        self.npc_locations = {}
        
        # Track enemies that were fled from (room_id -> [enemy_ids])
        self.fled_enemies = {}
        
        # Room states (e.g., locked doors)
        self.room_states = {}
        
        # Track how many of each item have been spawned (for max_spawn)
        self.item_spawn_counts = {}

        # Track items that have been permanently removed (won't respawn from room data)
        self.removed_items = set()

        # Load class data for world generation
        self.class_data = self._load_class_data()
        
        # Initialize the world state from room data (unless loading from save)
        if initialize_state:
            debug_log("Starting world state initialization")
            self._initialize_world_state()
            debug_log("World state initialization complete")
        else:
            debug_log("Skipping world state initialization (will be loaded from save)")
    
    def get_state(self):
        """Get the current world state for saving"""
        state = {
            "item_locations": self.item_locations,
            "enemy_locations": self.enemy_locations,
            "npc_locations": self.npc_locations,
            "fled_enemies": self.fled_enemies,
            "room_states": self.room_states,
            "item_spawn_counts": self.item_spawn_counts,
            "removed_items": list(self.removed_items)  # Convert set to list for JSON serialization
        }
        debug_log(f"[Instance {self.instance_id}] Saving world state with {len(self.item_locations)} items")
        return state
    
    def set_state(self, state):
        """Restore world state from loaded save data"""
        if not state:
            debug_log(f"[Instance {self.instance_id}] No world state to restore, using fresh initialization")
            return

        self.item_locations = state.get("item_locations", {})
        self.enemy_locations = state.get("enemy_locations", {})
        self.npc_locations = state.get("npc_locations", {})
        self.fled_enemies = state.get("fled_enemies", {})
        self.room_states = state.get("room_states", {})
        self.item_spawn_counts = state.get("item_spawn_counts", {})
        self.removed_items = set(state.get("removed_items", []))  # Convert list back to set
        
        debug_log(f"[Instance {self.instance_id}] Restored world state with {len(self.item_locations)} items, {len(self.enemy_locations)} enemies, {len(self.npc_locations)} NPCs")

    def spawn_tutorial_enemy(self, room_id: str = "home_grove") -> None:
        """Spawn the scripted tutorial enemy in the given room.

        The enemy is not persisted to save state — it re-spawns if the player
        reloads before completing the tutorial.
        """
        enemy_id = "glitched_process.tmp"
        if enemy_id not in self.enemies:
            debug_log(f"Tutorial enemy {enemy_id} not found in enemies data")
            return
        if room_id not in self.enemy_locations:
            self.enemy_locations[room_id] = []
        if enemy_id not in self.enemy_locations[room_id]:
            self.enemy_locations[room_id].append(enemy_id)
            debug_log(f"Tutorial enemy {enemy_id} spawned in {room_id}")

    def scale_enemy_stats(self, enemy_data, player_class):
        """Scale enemy stats based on player class power scaling"""
        if not enemy_data or not player_class:
            return enemy_data
        
        # Get class scaling type
        class_info = self.class_data.get(player_class, {})
        power_scaling = class_info.get("power_scaling", "balanced")
        
        # Create scaled copy to avoid modifying original data
        scaled_enemy = enemy_data.copy()
        base_health = enemy_data.get("health", 50)
        base_damage = enemy_data.get("damage", 10)
        
        # Apply scaling based on class type
        if power_scaling == "aggressive":  # Weaver - make enemies tougher
            health_multiplier = 1.15  # +15% health
            damage_multiplier = 1.05  # +5% damage
            debug_log(f"Scaling enemy for aggressive class: health x{health_multiplier}, damage x{damage_multiplier}")
            
        elif power_scaling == "defensive":  # Guardian - make enemies easier
            health_multiplier = 0.90  # -10% health  
            damage_multiplier = 0.85  # -15% damage
            debug_log(f"Scaling enemy for defensive class: health x{health_multiplier}, damage x{damage_multiplier}")
            
        else:  # balanced - Shaman gets standard stats
            health_multiplier = 1.0
            damage_multiplier = 1.0
            debug_log(f"No scaling applied for balanced class")
        
        # Apply scaling
        scaled_enemy["health"] = max(1, int(base_health * health_multiplier))
        scaled_enemy["damage"] = max(1, int(base_damage * damage_multiplier))
        
        # Scale attack patterns if they exist
        if "attack_patterns" in scaled_enemy:
            for attack in scaled_enemy["attack_patterns"]:
                if "damage" in attack:
                    attack["damage"] = max(1, int(attack["damage"] * damage_multiplier))
        
        debug_log(f"Enemy scaled: {base_health}HP -> {scaled_enemy['health']}HP, {base_damage}DMG -> {scaled_enemy['damage']}DMG")
        return scaled_enemy

    def _initialize_world_state(self):
        """Initialize item and enemy locations from room data"""
        for room_id, room_data in self.rooms.items():
            debug_log(f"Initializing state for room: {room_id}")
            # Initialize room state
            self.room_states[room_id] = {
                "visited": False,
                "locked": room_data.get("locked", False),
                "hidden": room_data.get("hidden", False),
                "key_required": room_data.get("key_required", None)
            }
            
            if self.room_states[room_id]["locked"]:
                debug_log(f"Room {room_id} is locked. Key required: {self.room_states[room_id]['key_required']}")
            if self.room_states[room_id]["hidden"]:
                debug_log(f"Room {room_id} is hidden")
            
            # Initialize enemies in this room
            enemy_count = 0
            for enemy_id in room_data.get("enemies", []) or []:
                # Try both with and without extension
                if enemy_id in self.enemies:
                    self.enemy_locations[enemy_id] = room_id
                    enemy_count += 1
                    debug_log(f"Placed enemy {enemy_id} in room {room_id} (direct match)")
                elif enemy_id + ".yml" in self.enemies:
                    # If enemy was loaded with extension
                    self.enemy_locations[enemy_id] = room_id
                    self.enemies[enemy_id] = self.enemies[enemy_id + ".yml"]
                    enemy_count += 1
                    debug_log(f"Placed enemy {enemy_id} in room {room_id} (fixed extension)")
                else:
                    # Try variations without extension
                    base_name = enemy_id.split('.')[0]
                    if base_name in self.enemies:
                        self.enemy_locations[enemy_id] = room_id
                        self.enemies[enemy_id] = self.enemies[base_name]
                        enemy_count += 1
                        debug_log(f"Placed enemy {enemy_id} in room {room_id} (using base name)")
                    else:
                        debug_log(f"WARNING: Enemy {enemy_id} specified in room {room_id} not found in enemies data")
                        debug_log(f"Available enemies: {list(self.enemies.keys())}")
            
            debug_log(f"Room {room_id} initialized with {enemy_count} enemies")
            
            # Initialize NPCs in this room
            npc_count = 0
            for npc_id in room_data.get("npcs", []) or []:
                if npc_id in self.npcs:
                    self.npc_locations[npc_id] = room_id
                    npc_count += 1
                    debug_log(f"Placed NPC {npc_id} in room {room_id}")
                else:
                    debug_log(f"WARNING: NPC {npc_id} specified in room {room_id} not found in npcs data")
            
            debug_log(f"Room {room_id} initialized with {npc_count} NPCs")
            
            # Initialize fixed items in this room (from room data)
            # This ensures quest/fixed items are always in the right place
            item_count = 0
            for item_id in room_data.get("items", []) or []:
                if item_id in self.items:
                    self.item_locations[item_id] = room_id
                    item_count += 1
                    debug_log(f"Placed item {item_id} in room {room_id} (fixed placement)")
                    # Initialize spawn count for fixed items
                    if item_id not in self.item_spawn_counts:
                        self.item_spawn_counts[item_id] = 1
                    else:
                        self.item_spawn_counts[item_id] += 1
                else:
                    debug_log(f"WARNING: Item {item_id} specified in room {room_id} not found in items data")
            
            debug_log(f"Room {room_id} initialized with {item_count} items")
    
    def _load_class_data(self):
        """Load class configuration data for world generation."""
        try:
            with open('data/classes.yaml', 'r') as file:
                data = yaml.safe_load(file)
                debug_log(f"Loaded class data for {len(data.get('classes', {}))} classes")
                return data.get('classes', {})
        except Exception as e:
            debug_log(f"Error loading class data: {e}")
            return {}
    
    def place_items(self, player_class=None):
        """
        Place items in the game world based on class, zones, and rarity.
        
        Args:
            player_class: Player class to determine item placement strategy
        """
        debug_log(f"Starting class-based item placement for player_class: {player_class}")
        
        # Always place the class-specific starter weapon first
        if player_class and player_class in self.class_data:
            self._place_starter_weapon(player_class)
        
        if not player_class or player_class not in self.class_data:
            debug_log(f"Invalid or missing player class, using default placement")
            return self._place_items_default()
            
        return self._place_items_class_based(player_class)
    
    def _place_starter_weapon(self, player_class):
        """Ensure the class-specific starter weapon is available in safe zones."""
        debug_log(f"Ensuring starter weapon availability for class: {player_class}")
        
        class_info = self.class_data[player_class]
        starter_weapon = class_info.get("starter_weapon")
        
        if not starter_weapon:
            debug_log(f"No starter weapon defined for class {player_class}")
            return
            
        # Check if the weapon item exists in the items collection
        weapon_found = False
        for item_id, item_data in self.items.items():
            if item_id == starter_weapon or (isinstance(item_data, dict) and item_data.get("name", "").lower().replace(" ", "_") == starter_weapon):
                weapon_found = True
                # Ensure it can spawn in safe zones like home_grove
                allowed_zones = item_data.get("allowed_zones", [])
                if "safe" not in allowed_zones:
                    allowed_zones.append("safe")
                    item_data["allowed_zones"] = allowed_zones
                debug_log(f"Starter weapon {starter_weapon} configured for dynamic placement")
                break
                
        if not weapon_found:
            debug_log(f"Starter weapon {starter_weapon} not found in items data")
    
    def _place_items_class_based(self, player_class):
        """Place items based on player class preferences and zone affinity."""
        debug_log(f"Executing class-based placement for {player_class}")

        class_info = self.class_data[player_class]
        preferred_zones = class_info.get("preferred_zones", [])
        loot_preferences = class_info.get("loot_preference", [])
        power_scaling = class_info.get("power_scaling", "balanced")

        # Place keys first so loot pass doesn't compete for room slots.
        self._place_keys()

        # Get class-specific rarity weights based on power scaling
        rarity_weights = self._get_class_rarity_weights(power_scaling)

        # Organize rooms by zones
        rooms_by_zone = self._organize_rooms_by_zone()

        # Place items zone by zone
        total_placed = 0
        for zone, zone_rooms in rooms_by_zone.items():
            zone_multiplier = 2.0 if zone in preferred_zones else 1.0
            items_placed = self._place_items_in_zone(
                zone, zone_rooms, player_class, rarity_weights,
                loot_preferences, zone_multiplier
            )
            total_placed += items_placed
            debug_log(f"Placed {items_placed} items in {zone} zone (multiplier: {zone_multiplier})")

        debug_log(f"Class-based placement complete: {total_placed} items placed")

        # Ensure home_grove has at least one health potion for better player experience
        self._ensure_home_grove_basics()

        return total_placed

    def _place_keys(self):
        """Scatter unplaced keys across non-locked rooms so progression items
        spread out instead of monopolizing the random-loot pool."""
        unplaced_keys = [
            item_id for item_id, item_data in self.items.items()
            if item_data.get("type", "").lower() == "key"
            and item_id not in self.item_locations
        ]
        if not unplaced_keys:
            return

        # Eligible rooms: unlocked, not home_grove (starter rooms keep their fixed items)
        eligible_rooms = [
            room_id for room_id in self.rooms.keys()
            if not self.room_states.get(room_id, {}).get("locked", False)
            and room_id != "home_grove"
        ]
        if not eligible_rooms:
            return

        rng.shuffle(unplaced_keys)
        rng.shuffle(eligible_rooms)

        # Spread keys across distinct rooms first, then double up if more keys than rooms.
        for i, key_id in enumerate(unplaced_keys):
            room_id = eligible_rooms[i % len(eligible_rooms)]
            self.item_locations[key_id] = room_id
            self.item_spawn_counts[key_id] = 1
            debug_log(f"Scattered key {key_id} into room {room_id}")
    
    def _ensure_home_grove_basics(self):
        """Ensure home_grove has essential consumables for good player experience."""
        # item_locations maps item_id -> room_id, so check it correctly
        home_grove_items = [item_id for item_id, loc in self.item_locations.items() if loc == "home_grove"]

        # Check if there's already a healing consumable in home_grove
        has_health_item = any(
            "healing" in self.items.get(item_id, {}).get("tags", [])
            for item_id in home_grove_items
        )

        # health_packet is always placed via room YAML, so this is just a safety net
        if not has_health_item and "health_packet" in self.items:
            if "health_packet" not in self.item_locations:
                self.item_locations["health_packet"] = "home_grove"
                self.item_spawn_counts["health_packet"] = 1
                debug_log("Added health_packet to home_grove as safety net")
    
    def _place_items_default(self):
        """Fallback to original placement algorithm."""
        debug_log("Using default item placement")
        # Define rarity weights
        rarity_weights = {
            "common": 60,
            "uncommon": 25,
            "rare": 10,
            "epic": 4,
            "legendary": 1
        }
        
        # Group items by their rarity
        items_by_rarity = {
            "common": [],
            "uncommon": [],
            "rare": [],
            "epic": [],
            "legendary": []
        }
        
        # Gather all items with placement information and organize by rarity
        for item_id, item_data in self.items.items():
            # Skip if item is already placed in a fixed location
            if item_id in self.item_locations:
                debug_log(f"Skipping item {item_id} - already placed")
                continue
            
            # Skip items that don't match the player's class if specified
            if player_class and not self._item_suitable_for_class(item_data, player_class):
                debug_log(f"Skipping item {item_id} - class restriction mismatch vs {player_class}")
                continue
            
            # Check if the item has already reached its max spawn count
            max_spawn = item_data.get("max_spawn", 1)
            current_spawn = self.item_spawn_counts.get(item_id, 0)
            
            if current_spawn >= max_spawn:
                debug_log(f"Skipping item {item_id} - already at max spawn count: {max_spawn}")
                continue  # Skip if we've already spawned the maximum number
            
            # Get the item's rarity (default to "common" if not specified)
            rarity = item_data.get("rarity", "common")

            # Normalize rarity to standardized string format
            rarity = self._normalize_rarity(rarity)
            debug_log(f"Normalized rarity for item {item_id}: {rarity}")

            # Add item to the appropriate rarity group
            if rarity in items_by_rarity:
                items_by_rarity[rarity].append((item_id, item_data))
                debug_log(f"Added item {item_id} to rarity group: {rarity}")
            else:
                # Default to common if rarity is not recognized
                items_by_rarity["common"].append((item_id, item_data))
                debug_log(f"Added item {item_id} to default common rarity group (unrecognized rarity: {rarity})")
        
        # Calculate approximate total items to place based on number of rooms
        # This ensures we don't flood every room with items
        num_rooms = len(self.rooms)
        base_items_per_room = 2  # Average items per room
        target_item_count = num_rooms * base_items_per_room
        debug_log(f"Target item count for world: {target_item_count} (based on {num_rooms} rooms)")
        
        # Prepare a list of all candidate items with their rarity
        all_candidate_items = []
        for rarity, items in items_by_rarity.items():
            for item in items:
                all_candidate_items.append((item, rarity))
        
        # If we have no items to place, return early
        if not all_candidate_items:
            debug_log("No items available to place in the world")
            return 0
        
        debug_log(f"Total candidate items for placement: {len(all_candidate_items)}")
        
        # Create a weighted distribution for random selection
        weighted_rarities = []
        weights = []
        for rarity in rarity_weights:
            if items_by_rarity[rarity]:  # Only include rarities that have items
                weighted_rarities.append(rarity)
                weights.append(rarity_weights[rarity])
        
        debug_log(f"Using weighted rarities for distribution: {weighted_rarities} with weights {weights}")
        
        # Place items using weighted random selection
        total_items_placed = 0
        
        # Create a list of rooms where items can be placed
        eligible_rooms = [room_id for room_id in self.rooms.keys() 
                          if not self.room_states.get(room_id, {}).get("locked", False)]
        debug_log(f"Found {len(eligible_rooms)} eligible unlocked rooms for item placement")
        
        # Place items randomly based on weighted rarity
        for _ in range(target_item_count):
            if not weighted_rarities or not eligible_rooms:
                debug_log("No more valid rarities or eligible rooms - stopping item placement")
                break  # No more rarities with items or no more eligible rooms
            
            # Select a rarity based on weights
            try:
                selected_rarity = rng.choices(weighted_rarities, weights=weights, k=1)[0]
                debug_log(f"Random selection chose rarity: {selected_rarity}")
            except IndexError:
                debug_log("IndexError during rarity selection - no more valid rarities")
                break  # No more valid rarities to select from
            
            # If there are no items left of this rarity, remove it and try again
            if not items_by_rarity[selected_rarity]:
                idx = weighted_rarities.index(selected_rarity)
                weighted_rarities.pop(idx)
                weights.pop(idx)
                debug_log(f"No items left in rarity {selected_rarity} - removing from weighted options")
                continue
            
            # Select a random item of the chosen rarity
            item_id, item_data = rng.choice(items_by_rarity[selected_rarity])
            debug_log(f"Selected item {item_id} from rarity {selected_rarity}")
            
            # Remove this item from the pool to avoid multiple placements
            items_by_rarity[selected_rarity].remove((item_id, item_data))
            
            # Place the item
            if self._place_single_item(item_id, item_data):
                total_items_placed += 1
                debug_log(f"Successfully placed {selected_rarity} item: {item_id}")
            else:
                debug_log(f"Failed to place {selected_rarity} item: {item_id}")
            
            # If we've placed enough items, stop
            if total_items_placed >= target_item_count:
                debug_log("Reached target item count - stopping item placement")
                break
        
        debug_log(f"Placed {total_items_placed} items using weighted random selection")
        return total_items_placed
    
    def _place_single_item(self, item_id, item_data):
        """
        Helper method to place a single item in an appropriate room.
        
        Args:
            item_id: The ID of the item to place
            item_data: The item's data dictionary
        
        Returns:
            bool: True if the item was successfully placed, False otherwise
        """
        # Check if the item has allowed_rooms specified
        allowed_rooms = item_data.get("allowed_rooms", [])
        
        # Find eligible rooms for this item
        eligible_rooms = []
        
        if allowed_rooms:
            # Item has specific room restrictions
            debug_log(f"Item {item_id} has room restrictions: {allowed_rooms}")
            for room_id in allowed_rooms:
                # Check if the room exists and is not locked
                if room_id in self.rooms and not self.room_states.get(room_id, {}).get("locked", False):
                    eligible_rooms.append(room_id)
        else:
            # No specific room restrictions, can go in any unlocked room
            eligible_rooms = [room_id for room_id in self.rooms.keys() 
                              if not self.room_states.get(room_id, {}).get("locked", False)]
        
        # If no eligible rooms, item can't be placed
        if not eligible_rooms:
            debug_log(f"No eligible rooms to place item {item_id}")
            return False
        
        # Select a random room from eligible rooms
        chosen_room_id = rng.choice(eligible_rooms)
        debug_log(f"Selected room {chosen_room_id} for item {item_id}")
        
        # Place the item in the chosen room
        self.item_locations[item_id] = chosen_room_id
        
        # Update spawn counter for this item
        self.item_spawn_counts[item_id] = self.item_spawn_counts.get(item_id, 0) + 1
        debug_log(f"Placed item {item_id} in room {chosen_room_id} (spawn count: {self.item_spawn_counts[item_id]})")
        
        return True
    
    def _normalize_rarity(self, rarity):
        """Normalize rarity to standardized string format.

        Supports both numeric (legacy) and string formats.
        Valid rarities: common, uncommon, rare, epic, legendary, secret, unique
        """
        # If already a valid string rarity, return it
        valid_rarities = ["common", "uncommon", "rare", "epic", "legendary", "secret", "unique"]
        if isinstance(rarity, str) and rarity.lower() in valid_rarities:
            return rarity.lower()

        # Convert numeric rarity to string format (backward compatibility)
        if isinstance(rarity, (int, float)):
            if rarity < 2:
                return "legendary"
            elif rarity < 5:
                return "epic"
            elif rarity < 10:
                return "rare"
            elif rarity < 20:
                return "uncommon"
            else:
                return "common"

        # Default to common for unrecognized formats
        return "common"

    def _get_directory_rarity_multiplier(self, room_id):
        """Get rarity spawn multipliers based on directory depth.

        Directory hierarchy determines which rarities can spawn:
        - /home, /var: Common items dominate
        - /bin, /etc, /usr: Uncommon items more frequent
        - /lib: Rare items appear
        - /dev: Epic items spawn
        - /root: Legendary items exclusive

        Returns a dict of multipliers for each rarity tier.
        """
        # Default multipliers (all rarities allowed)
        base_multipliers = {
            "common": 1.0,
            "uncommon": 1.0,
            "rare": 1.0,
            "epic": 1.0,
            "legendary": 1.0,
            "secret": 0,  # Never spawn naturally
            "unique": 0   # Never spawn naturally
        }

        # Extract directory from room_id (e.g., "home_grove" -> "home")
        room_dir = room_id.split('_')[0] if '_' in room_id else room_id

        # Home and var: Common items only, some uncommon
        if room_dir in ['home', 'var']:
            return {
                "common": 2.0,      # Double common spawn rate
                "uncommon": 0.5,    # Reduced uncommon
                "rare": 0,          # No rare
                "epic": 0,          # No epic
                "legendary": 0,     # No legendary
                "secret": 0,
                "unique": 0
            }

        # Bin, etc, usr: Common and uncommon, some rare
        elif room_dir in ['bin', 'etc', 'usr']:
            return {
                "common": 1.2,
                "uncommon": 1.5,    # Increased uncommon
                "rare": 0.3,        # Small chance of rare
                "epic": 0,
                "legendary": 0,
                "secret": 0,
                "unique": 0
            }

        # Lib: Common, uncommon, rare
        elif room_dir in ['lib']:
            return {
                "common": 0.8,
                "uncommon": 1.2,
                "rare": 1.5,        # Increased rare
                "epic": 0.2,        # Small chance of epic
                "legendary": 0,
                "secret": 0,
                "unique": 0
            }

        # Dev: Uncommon, rare, epic
        elif room_dir in ['dev']:
            return {
                "common": 0.3,      # Reduced common
                "uncommon": 0.8,
                "rare": 1.2,
                "epic": 2.0,        # Double epic spawn rate
                "legendary": 0.1,   # Tiny chance of legendary
                "secret": 0,
                "unique": 0
            }

        # Root: All rarities, legendary exclusive
        elif room_dir in ['root']:
            return {
                "common": 0.2,      # Very rare common
                "uncommon": 0.5,
                "rare": 1.0,
                "epic": 1.5,
                "legendary": 3.0,   # Triple legendary spawn rate
                "secret": 0,        # Still requires special trigger
                "unique": 0
            }

        # Default for unrecognized directories
        return base_multipliers

    def _get_class_rarity_weights(self, power_scaling):
        """Get rarity weights based on class power scaling.

        Base weights follow the Great Kernel Panic specification:
        Common: 60%, Uncommon: 25%, Rare: 10%, Epic: 4%, Legendary: 1%
        These are modified by class power scaling.
        """
        if power_scaling == "aggressive":
            # Weavers get more rare/powerful items
            return {
                "common": 45,
                "uncommon": 28,
                "rare": 17,
                "epic": 7,
                "legendary": 3,
                "secret": 0,
                "unique": 0
            }
        elif power_scaling == "defensive":
            # Guardians get more consistent, common items
            return {
                "common": 70,
                "uncommon": 20,
                "rare": 7,
                "epic": 2,
                "legendary": 1,
                "secret": 0,
                "unique": 0
            }
        else:  # balanced (shaman)
            # Base Great Kernel Panic spawn rates
            return {
                "common": 60,
                "uncommon": 25,
                "rare": 10,
                "epic": 4,
                "legendary": 1,
                "secret": 0,  # Secret items never spawn normally
                "unique": 0   # Unique items never spawn normally
            }
    
    def _organize_rooms_by_zone(self):
        """Organize rooms by their zone classification."""
        rooms_by_zone = {}
        
        for room_id, room_data in self.rooms.items():
            zone = room_data.get("zone", "neutral")
            if zone not in rooms_by_zone:
                rooms_by_zone[zone] = []
            rooms_by_zone[zone].append(room_id)
        
        debug_log(f"Organized rooms into {len(rooms_by_zone)} zones: {list(rooms_by_zone.keys())}")
        return rooms_by_zone
    
    def _place_items_in_zone(self, zone, zone_rooms, player_class, rarity_weights, loot_preferences, multiplier):
        """Place items within a specific zone."""
        debug_log(f"Placing items in {zone} zone with {len(zone_rooms)} rooms")
        
        # Filter items suitable for this zone and class
        suitable_items = self._get_suitable_items_for_zone(zone, player_class, loot_preferences)
        
        if not suitable_items:
            debug_log(f"No suitable items found for {zone} zone")
            return 0
        
        # Calculate items to place based on zone size and multiplier
        base_items_per_room = 3  # Increased from 2 to ensure more variety
        target_items = int(len(zone_rooms) * base_items_per_room * multiplier)
        
        # For safe zones, ensure at least one healing item per room
        if zone == "safe":
            target_items = max(target_items, len(zone_rooms) + 2)  # Guarantee extras for safe zones
        
        # Filter out home_grove from random placement (it gets starter items)
        zone_rooms_filtered = [r for r in zone_rooms if r != "home_grove"]
        if not zone_rooms_filtered:
            debug_log(f"No rooms available for placement in {zone} zone after filtering home_grove")
            return 0

        # Retry until target reached. Cap total attempts so a saturated zone
        # (all rooms at max_items_per_room, or no item/rarity match) can't loop forever.
        items_placed = 0
        max_attempts = target_items * 4
        attempts = 0
        while items_placed < target_items and attempts < max_attempts:
            attempts += 1
            if not suitable_items:
                break

            room_id = rng.choice(zone_rooms_filtered)
            room_data = self.rooms.get(room_id, {})
            allowed_rarities = self._get_allowed_rarities_for_room(room_id, room_data)

            item_id, item_data = self._select_weighted_item(suitable_items, rarity_weights, allowed_rarities, room_id)
            if not item_id:
                continue

            if self._place_item_in_room(item_id, item_data, room_id):
                items_placed += 1
                item_type = item_data.get("type", "")
                if item_type not in ["consumable", "enhancement"]:
                    suitable_items = [(id, data) for id, data in suitable_items if id != item_id]

        return items_placed
    
    def _get_suitable_items_for_zone(self, zone, player_class, loot_preferences):
        """Get items suitable for a zone and class."""
        suitable_items = []

        for item_id, item_data in self.items.items():
            # Skip already placed items
            if item_id in self.item_locations:
                continue

            # Keys are placed via _place_keys, not through zone loot — otherwise
            # they monopolize core/root and starve other zones.
            if item_data.get("type", "").lower() == "key":
                continue

            # Check class restrictions
            if not self._item_suitable_for_class(item_data, player_class):
                continue

            # Loot preferences act as a soft bias, not a hard filter. Most gear
            # (weapons, armor, trinkets, consumables, lore) should be reachable
            # by any class; preference can later weight selection if needed.
            # Only hard-restricted items (with explicit allowed_classes) are gated.

            # NOTE: allowed_zones check moved to _item_fits_room — item zones
            # use directory prefixes (bin, usr, var) while room zones are story
            # categories (core, safe, void), so per-room prefix matching is
            # the only way the filter ever lets items through.

            suitable_items.append((item_id, item_data))
        
        debug_log(f"Found {len(suitable_items)} suitable items for {zone} zone and {player_class} class")
        return suitable_items
    
    def _item_suitable_for_class(self, item_data, player_class):
        """Check if item is suitable for the player class."""
        if "allowed_classes" in item_data:
            allowed = item_data["allowed_classes"]
            if isinstance(allowed, str):
                allowed = [allowed]
            return player_class.lower() in [c.lower() for c in allowed]
        return True  # No restrictions
    
    def _item_matches_preferences(self, item_data, loot_preferences):
        """Check if item matches class loot preferences."""
        item_type = item_data.get("type", "").lower()
        item_tags = item_data.get("tags", [])
        
        for preference in loot_preferences:
            if preference.lower() in item_type or preference.lower() in [tag.lower() for tag in item_tags]:
                return True
        return False
    
    def _select_weighted_item(self, suitable_items, rarity_weights, allowed_rarities=None, room_id=None):
        """Select an item based on rarity weights and optional rarity filter.

        Args:
            suitable_items: List of (item_id, item_data) tuples
            rarity_weights: Dict of base rarity weights from class
            allowed_rarities: Optional list of allowed rarities for this room
            room_id: Room ID to apply directory-depth multipliers

        Returns:
            (item_id, item_data) tuple or (None, None)
        """
        if not suitable_items:
            return None, None

        # Organize by rarity
        items_by_rarity = {}
        for item_id, item_data in suitable_items:
            rarity = item_data.get("rarity", "common")
            # Normalize rarity
            rarity = self._normalize_rarity(rarity)
            if rarity not in items_by_rarity:
                items_by_rarity[rarity] = []
            items_by_rarity[rarity].append((item_id, item_data))

        # Select rarity based on weights
        all_available = [r for r in rarity_weights.keys() if r in items_by_rarity]

        # Apply rarity filter if provided. Fall back to all-available if the
        # filter empties the pool — sparse zones (only rare/epic candidates)
        # shouldn't silently place nothing.
        if allowed_rarities:
            filtered = [r for r in all_available if r in allowed_rarities]
            available_rarities = filtered if filtered else all_available
        else:
            available_rarities = all_available

        if not available_rarities:
            return None, None

        # Apply directory-depth multipliers if room_id provided
        if room_id:
            dir_multipliers = self._get_directory_rarity_multiplier(room_id)
            # Combine class weights with directory multipliers
            weights = [rarity_weights[r] * dir_multipliers.get(r, 1.0) for r in available_rarities]
            # Filter out zero-weight rarities
            filtered_rarities = [(r, w) for r, w in zip(available_rarities, weights) if w > 0]
            if not filtered_rarities:
                return None, None
            available_rarities, weights = zip(*filtered_rarities)
        else:
            weights = [rarity_weights[r] for r in available_rarities]

        selected_rarity = rng.choices(list(available_rarities), weights=list(weights), k=1)[0]

        # Select random item from rarity
        return rng.choice(items_by_rarity[selected_rarity])

    def _count_items_in_room(self, room_id: str) -> int:
        """Count how many items are currently in a room."""
        return sum(1 for item_id, loc in self.item_locations.items() if loc == room_id)

    def _get_allowed_rarities_for_room(self, room_id: str, room_data: dict) -> list:
        """Determine which item rarities are allowed in a room based on characteristics."""
        # Get room characteristics
        enemies = room_data.get('enemies', [])
        enemy_count = len(enemies)
        zone = room_data.get('zone', 'neutral')
        is_boss_room = any('boss' in str(e).lower() or 'overlord' in str(e).lower() for e in enemies)

        # Determine allowed rarities
        if is_boss_room:
            # Boss rooms: All rarities including legendary
            return ['common', 'uncommon', 'rare', 'epic', 'legendary']
        elif enemy_count >= 2:
            # 2-3 enemy rooms: Epic and rare (and lower)
            return ['common', 'uncommon', 'rare', 'epic']
        elif enemy_count == 1:
            # 1 enemy rooms: Common + uncommon for variety
            return ['common', 'uncommon']
        elif zone == 'safe':
            # Safe zones: Uncommon (and common)
            return ['common', 'uncommon']
        else:
            # Default: Common and uncommon
            return ['common', 'uncommon']

    def place_starter_items(self, player_class: str) -> None:
        """Place class-appropriate starter items in home_grove after character creation."""
        # Get starter weapon from class data
        class_info = self.class_data.get(player_class.lower(), {})
        starter_weapon = class_info.get("starter_weapon")

        if starter_weapon and starter_weapon in self.items:
            # Force-place directly into item_locations — skip the item cap check so
            # the weapon always lands in home_grove regardless of how many YAML items
            # were pre-loaded into the room during world state initialization.
            if starter_weapon not in self.item_locations:
                self.item_locations[starter_weapon] = "home_grove"
                self.item_spawn_counts[starter_weapon] = 1
                debug_log(f"Placed {starter_weapon} in home_grove for {player_class}")
            else:
                debug_log(f"Starter weapon {starter_weapon} already placed in {self.item_locations[starter_weapon]}, moving to home_grove")
                self.item_locations[starter_weapon] = "home_grove"
        else:
            logger.warning(f"Starter weapon '{starter_weapon}' for class '{player_class}' not found in items data")

        # health_packet is already guaranteed in home_grove via the room YAML

    def _item_fits_room(self, item_data, room_id) -> bool:
        """Check item's allowed_rooms / allowed_zones constraints against a room.
        Zones are matched against the room_id's directory prefix (var_dungeon → 'var')."""
        allowed_rooms = item_data.get("allowed_rooms", [])
        if allowed_rooms and room_id not in allowed_rooms:
            return False
        allowed_zones = item_data.get("allowed_zones", [])
        if allowed_zones:
            room_prefix = room_id.split("_", 1)[0]
            room_zone = self.rooms.get(room_id, {}).get("zone", "")
            if room_prefix not in allowed_zones and room_zone not in allowed_zones:
                return False
        return True

    def _place_item_in_room(self, item_id, item_data, room_id, max_items_per_room=5):
        """Place a specific item in a specific room."""
        # Check if room is locked
        if self.room_states.get(room_id, {}).get("locked", False):
            return False

        # Check item's own zone/room constraints
        if not self._item_fits_room(item_data, room_id):
            return False

        # Check per-room item limit
        current_room_items = self._count_items_in_room(room_id)
        if current_room_items >= max_items_per_room:
            debug_log(f"Room {room_id} already has {current_room_items} items (limit: {max_items_per_room}), skipping {item_id}")
            return False

        # Check if this item is already placed (to prevent overriding fixed items)
        if item_id in self.item_locations:
            debug_log(f"Item {item_id} already placed in {self.item_locations[item_id]}, skipping dynamic placement")
            return False

        # Place the item
        self.item_locations[item_id] = room_id
        self.item_spawn_counts[item_id] = self.item_spawn_counts.get(item_id, 0) + 1

        debug_log(f"Placed {item_id} in room {room_id}")
        return True
    
    def get_room(self, room_id):
        """Get room data by ID"""
        room = self.rooms.get(room_id)
        if room is None:
            debug_log(f"WARNING: Attempted to get non-existent room: {room_id}")
        else:
            debug_log(f"Retrieved room data for {room_id}")
        return room
    
    def get_room_state(self, room_id):
        """Get the state of a room"""
        state = self.room_states.get(room_id, {"visited": False, "locked": False})
        if room_id not in self.room_states:
            debug_log(f"WARNING: Requested state for unknown room {room_id}, returning default state")
        return state
    
    def set_room_visited(self, room_id):
        """Mark a room as visited"""
        if room_id in self.room_states:
            prev_state = self.room_states[room_id]["visited"]
            self.room_states[room_id]["visited"] = True
            if not prev_state:  # Only log if changing from unvisited to visited
                debug_log(f"Marked room {room_id} as visited for the first time")
        else:
            debug_log(f"WARNING: Attempted to mark non-existent room {room_id} as visited")
    
    def unlock_room(self, room_id):
        """Unlock a room"""
        if room_id in self.room_states:
            if self.room_states[room_id]["locked"]:
                self.room_states[room_id]["locked"] = False
                debug_log(f"Unlocked room {room_id}")
                return True
            else:
                debug_log(f"Room {room_id} is already unlocked")
                return False
        debug_log(f"WARNING: Attempted to unlock non-existent room {room_id}")
        return False
    
    def get_items_in_room(self, room_id):
        """Get all items in a room"""
        debug_log(f"[Instance {self.instance_id}] Getting items in room {room_id}")
        debug_log(f"[Instance {self.instance_id}] Total items in item_locations: {len(self.item_locations)}")
        debug_log(f"[Instance {self.instance_id}] Full item_locations: {self.item_locations}")

        # Get all items from the item_locations dictionary
        items_from_locations = [item_id for item_id, location in self.item_locations.items() if location == room_id]
        debug_log(f"Items from locations for {room_id}: {items_from_locations}")

        # As a backup, check the room data directly (some items might not be in the tracking dict)
        room_data = self.get_room(room_id)
        if room_data and "items" in room_data:
            items_in_room_data = room_data.get("items", []) or []  # Handle None by returning empty list
            debug_log(f"Items from room data for {room_id}: {items_in_room_data}")
            # Combine both sources, ensuring no duplicates
            combined_items = list(set(items_from_locations + items_in_room_data))

            # Filter out permanently removed items
            filtered_items = [item_id for item_id in combined_items if item_id not in self.removed_items]
            if len(filtered_items) != len(combined_items):
                removed_count = len(combined_items) - len(filtered_items)
                debug_log(f"Filtered out {removed_count} permanently removed items from room {room_id}")

            debug_log(f"Found {len(filtered_items)} items in room {room_id}: {filtered_items}")
            return filtered_items

        # Filter removed items from locations-only list as well
        filtered_items = [item_id for item_id in items_from_locations if item_id not in self.removed_items]
        debug_log(f"Found {len(filtered_items)} items in room {room_id}: {filtered_items}")
        return filtered_items
    
    def get_enemies_in_room(self, room_id):
        """Get all enemies in a room"""
        debug_log(f"Getting enemies in room {room_id}")
        # Get all enemies from the enemy_locations dictionary
        enemies_from_locations = [enemy_id for enemy_id, location in self.enemy_locations.items() if location == room_id]
        
        # As a backup, check the room data directly (some enemies might not be in the tracking dict)
        room_data = self.get_room(room_id)
        if room_data and "enemies" in room_data:
            enemies_in_room_data = room_data.get("enemies", []) or []  # Handle None by returning empty list
            # Combine both sources, ensuring no duplicates
            combined_enemies = list(set(enemies_from_locations + enemies_in_room_data))
            debug_log(f"Found {len(combined_enemies)} enemies in room {room_id}: {combined_enemies}")
            return combined_enemies
        
        debug_log(f"Found {len(enemies_from_locations)} enemies in room {room_id}: {enemies_from_locations}")
        return enemies_from_locations
    
    def get_npcs_in_room(self, room_id):
        """Get all NPCs in a room"""
        debug_log(f"Getting NPCs in room {room_id}")
        # Get all NPCs from the npc_locations dictionary
        npcs_from_locations = [npc_id for npc_id, location in self.npc_locations.items() if location == room_id]
        
        # As a backup, check the room data directly (some npcs might not be in the tracking dict)
        room_data = self.get_room(room_id)
        if room_data and "npcs" in room_data:
            npcs_in_room_data = room_data.get("npcs", []) or []  # Handle None by returning empty list
            # Combine both sources, ensuring no duplicates
            combined_npcs = list(set(npcs_from_locations + npcs_in_room_data))
            debug_log(f"Found {len(combined_npcs)} NPCs in room {room_id}: {combined_npcs}")
            return combined_npcs
        
        debug_log(f"Found {len(npcs_from_locations)} NPCs in room {room_id}: {npcs_from_locations}")
        return npcs_from_locations
    
    def get_item(self, item_id):
        """Get item data by ID"""
        item = self.items.get(item_id)
        if item is None:
            debug_log(f"WARNING: Requested non-existent item: {item_id}")
        return item
    
    def get_enemy(self, enemy_id, player_class=None):
        """Get enemy data by ID, optionally scaled for player class"""
        enemy = self.enemies.get(enemy_id)
        if enemy is None:
            debug_log(f"WARNING: Requested non-existent enemy: {enemy_id}")
            debug_log(f"Available enemy IDs: {list(self.enemies.keys())}")
            return enemy
        
        debug_log(f"Retrieved enemy data for {enemy_id}")
        
        # Apply class-based scaling if player class is provided
        if player_class:
            enemy = self.scale_enemy_stats(enemy, player_class)

        # Apply difficulty-mode scaling (enemy HP/damage) on top of class scaling.
        from src import difficulty
        enemy = difficulty.scale_enemy(enemy)

        return enemy
    
    def get_npc(self, npc_id):
        """Get NPC data by ID"""
        npc = self.npcs.get(npc_id)
        if npc is None:
            debug_log(f"WARNING: Requested non-existent NPC: {npc_id}")
        return npc
    
    def remove_item_from_room(self, item_id):
        """Remove an item from its current room (when picked up)"""
        if item_id in self.item_locations:
            room = self.item_locations[item_id]
            del self.item_locations[item_id]
            debug_log(f"Removed item {item_id} from room {room}")

            # Mark item as permanently removed (won't respawn from room YAML)
            self.removed_items.add(item_id)
            debug_log(f"Marked item {item_id} as permanently removed")
            return True
        debug_log(f"WARNING: Attempted to remove item {item_id} that is not in any room")
        return False
    
    def add_item_to_room(self, item_id, room_id):
        """Add an item to a room (when dropped)"""
        self.item_locations[item_id] = room_id
        debug_log(f"Added item {item_id} to room {room_id}")

        # If item was previously removed, allow it to be picked up again
        if item_id in self.removed_items:
            self.removed_items.remove(item_id)
            debug_log(f"Removed {item_id} from permanently removed list (item was dropped)")
    
    def remove_enemy_from_room(self, enemy_id):
        """Remove an enemy from its current room (when defeated)"""
        room_id = None
        
        # First try to find in enemy_locations dictionary
        if enemy_id in self.enemy_locations:
            room_id = self.enemy_locations[enemy_id]
            del self.enemy_locations[enemy_id]
            debug_log(f"Removed enemy {enemy_id} from enemy_locations (room: {room_id})")
        
        # If not found, check if this might be a display name issue
        # Sometimes the combat system uses a different name than the enemy ID
        if room_id is None:
            # Try to find by checking enemy display names in all rooms
            for potential_enemy_id, location in self.enemy_locations.items():
                enemy_data = self.enemies.get(potential_enemy_id)
                if enemy_data and enemy_data.get("name") == enemy_id:
                    room_id = location
                    del self.enemy_locations[potential_enemy_id]
                    enemy_id = potential_enemy_id  # Use the actual ID for further operations
                    debug_log(f"Removed enemy with display name {enemy_id} from enemy_locations (room: {room_id})")
                    break
        
        # If we found the room, also make sure to remove from the room's direct data
        if room_id:
            room_data = self.get_room(room_id)
            if room_data and "enemies" in room_data:
                if enemy_id in room_data["enemies"]:
                    room_data["enemies"].remove(enemy_id)
                    debug_log(f"Removed enemy {enemy_id} from room {room_id} data")
                
                # Check if there are similar IDs (with extensions) to remove
                enemy_base_id = enemy_id.split('.')[0]
                for e_id in list(room_data["enemies"]):
                    if e_id.startswith(enemy_base_id):
                        room_data["enemies"].remove(e_id)
                        debug_log(f"Removed related enemy {e_id} from room {room_id} data")
            
            # Emit enemy defeated event
            enemy_data = self.get_enemy(enemy_id)
            event_bus.emit_event(
                EventType.ENEMY_DEFEATED,
                {
                    "enemy_id": enemy_id,
                    "room": room_id,
                    "enemy_name": enemy_data.get("name", enemy_id) if enemy_data else enemy_id,
                    "was_boss": enemy_data.get("is_boss", False) if enemy_data else False
                },
                "GameWorld"
            )
            
            # Check if all enemies in room are defeated
            remaining_enemies = self.get_enemies_in_room(room_id)
            if not remaining_enemies:
                event_bus.emit_event(
                    EventType.ALL_ENEMIES_DEFEATED,
                    {
                        "room": room_id,
                        "last_enemy_defeated": enemy_id
                    },
                    "GameWorld"
                )
            
            return True
            
        debug_log(f"WARNING: Could not find enemy {enemy_id} to remove")
        return False
    
    def mark_enemy_as_fled(self, enemy_id, room_id):
        """Mark an enemy as fled from a room for later respawning."""
        debug_log(f"Marking enemy {enemy_id} as fled from room {room_id}")
        if room_id not in self.fled_enemies:
            self.fled_enemies[room_id] = []
        if enemy_id not in self.fled_enemies[room_id]:
            self.fled_enemies[room_id].append(enemy_id)
        
        # Remove from current location
        if enemy_id in self.enemy_locations:
            del self.enemy_locations[enemy_id]
    
    def respawn_fled_enemies(self, room_id):
        """Respawn enemies that were fled from when player re-enters room."""
        if room_id in self.fled_enemies and self.fled_enemies[room_id]:
            debug_log(f"Respawning fled enemies in room {room_id}: {self.fled_enemies[room_id]}")
            for enemy_id in self.fled_enemies[room_id]:
                self.enemy_locations[enemy_id] = room_id
                debug_log(f"Respawned enemy {enemy_id} in room {room_id}")
            
            # Clear the fled enemies list for this room
            self.fled_enemies[room_id] = []
    
    def get_exits(self, room_id):
        """Get available exits from a room"""
        room = self.get_room(room_id)
        if not room:
            debug_log(f"WARNING: Attempted to get exits for non-existent room: {room_id}")
            return []
        exits = room.get("exits", [])
        debug_log(f"Room {room_id} has exits: {exits}")
        return exits
    
    def can_move_to(self, from_room, to_room):
        """Check if player can move from one room to another"""
        debug_log(f"Checking if player can move from {from_room} to {to_room}")
        
        # First check if the exit exists
        if to_room not in self.get_exits(from_room):
            debug_log(f"Move failed: {to_room} is not an exit from {from_room}")
            return False, "That exit doesn't exist."
        
        # Check if destination is hidden
        room_state = self.get_room_state(to_room)
        if room_state.get("hidden", False):
            debug_log(f"Move failed: {to_room} is hidden")
            return False, "That path is not visible."
        
        # Check if destination is locked
        if room_state.get("locked", False):
            key_required = room_state.get("key_required")
            if key_required:
                debug_log(f"Move failed: {to_room} is locked and requires key: {key_required}")
                return False, f"That room is locked. You need {key_required} to enter."
            else:
                debug_log(f"Move failed: {to_room} is locked")
                return False, "That room is locked."
                
        debug_log(f"Move allowed: {from_room} to {to_room}")
        return True, None
    
    
    def discover_room(self, room_id):
        """Make a hidden room visible
        
        Args:
            room_id: The ID of the room to discover
            
        Returns:
            bool: True if the room was successfully discovered, False otherwise
        """
        if room_id in self.room_states:
            if self.room_states[room_id].get("hidden", False):
                self.room_states[room_id]["hidden"] = False
                debug_log(f"Discovered hidden room: {room_id}")
                return True
            else:
                debug_log(f"Room {room_id} is already discovered (not hidden)")
        else:
            debug_log(f"WARNING: Attempted to discover non-existent room: {room_id}")
        return False 

    def get_formatted_room_description(self, room_id):
        """
        Returns a formatted, user-friendly description of a room,
        including its name, description, items, enemies, and NPCs.
        """
        room_data = self.get_room(room_id)
        if not room_data:
            return "You are in a void. Something is terribly wrong."

        # Name and description
        name = room_data.get('name', 'An Unnamed Room')
        description = room_data.get('description', 'A featureless space.')
        full_description = f"[bold cyan]{name}[/bold cyan]\n{description}\n"

        # Items
        items_in_room = self.get_items_in_room(room_id)
        if items_in_room:
            full_description += "\n[bold yellow]You see the following items:[/bold yellow]\n"
            for item_id in items_in_room:
                item_name = self.items.get(item_id, {}).get('name', item_id)
                full_description += f"- {item_name}\n"

        # Enemies
        enemies_in_room = self.get_enemies_in_room(room_id)
        if enemies_in_room:
            full_description += "\n[bold red]Enemies:[/bold red]\n"
            for enemy_id in enemies_in_room:
                enemy_name = self.enemies.get(enemy_id, {}).get('name', enemy_id)
                full_description += f"- {enemy_name}\n"

        # NPCs
        npcs_in_room = self.get_npcs_in_room(room_id)
        if npcs_in_room:
            full_description += "\n[bold green]People:[/bold green]\n"
            for npc_id in npcs_in_room:
                npc_name = self.npcs.get(npc_id, {}).get('name', npc_id)
                full_description += f"- {npc_name}\n"

        return full_description.strip()