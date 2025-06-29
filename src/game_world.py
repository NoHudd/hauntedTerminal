#!/usr/bin/env python3
import random
from utils.debug_tools import debug_log

class GameWorld:
    """Manages the game world, including rooms, items, enemies, and NPCs"""
    
    def __init__(self, rooms, items, enemies, npcs):
        """Initialize with data loaded from YAML files"""
        debug_log("Initializing GameWorld")
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
        
        # Room states (e.g., locked doors)
        self.room_states = {}
        
        # Track how many of each item have been spawned (for max_spawn)
        self.item_spawn_counts = {}
        
        # Initialize the world state from room data
        debug_log("Starting world state initialization")
        self._initialize_world_state()
        debug_log("World state initialization complete")
    
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
    
    def place_items(self, player_class=None):
        """
        Place items in the game world based on their configuration and rarity.
        
        Args:
            player_class: Optional player class to filter items by class restriction
        """
        debug_log(f"Placing items for player_class: {player_class}")
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
            if player_class:
                should_skip = False
                
                # Check for class_restriction field
                if "class_restriction" in item_data:
                    # Handle both string and list restrictions
                    class_restriction = item_data["class_restriction"]
                    if isinstance(class_restriction, str):
                        if class_restriction.lower() != player_class.lower():
                            debug_log(f"Skipping item {item_id} - class restriction mismatch: {class_restriction} vs {player_class}")
                            should_skip = True
                    elif isinstance(class_restriction, list):
                        if player_class.lower() not in [r.lower() for r in class_restriction]:
                            debug_log(f"Skipping item {item_id} - class restriction mismatch: {class_restriction} vs {player_class}")
                            should_skip = True
                
                # Also check for allowed_classes field (used in weapons)
                elif "allowed_classes" in item_data:
                    allowed_classes = item_data["allowed_classes"]
                    if isinstance(allowed_classes, str):
                        if allowed_classes.lower() != player_class.lower():
                            debug_log(f"Skipping item {item_id} - allowed classes mismatch: {allowed_classes} vs {player_class}")
                            should_skip = True
                    elif isinstance(allowed_classes, list):
                        if player_class.lower() not in [c.lower() for c in allowed_classes]:
                            debug_log(f"Skipping item {item_id} - allowed classes mismatch: {allowed_classes} vs {player_class}")
                            should_skip = True
                
                if should_skip:
                    continue  # Skip this item, player can't use it
            
            # Check if the item has already reached its max spawn count
            max_spawn = item_data.get("max_spawn", 1)
            current_spawn = self.item_spawn_counts.get(item_id, 0)
            
            if current_spawn >= max_spawn:
                debug_log(f"Skipping item {item_id} - already at max spawn count: {max_spawn}")
                continue  # Skip if we've already spawned the maximum number
            
            # Get the item's rarity (default to "common" if not specified)
            rarity = item_data.get("rarity", "common")
            
            # Convert numeric rarity to string rarity if needed
            if isinstance(rarity, (int, float)):
                # Convert numeric rarity to one of our category strings
                if rarity < 2:
                    rarity = "legendary"
                elif rarity < 5:
                    rarity = "epic"
                elif rarity < 10:
                    rarity = "rare"
                elif rarity < 20:
                    rarity = "uncommon"
                else:
                    rarity = "common"
                debug_log(f"Converted numeric rarity to string: {rarity} for item {item_id}")
            
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
                selected_rarity = random.choices(weighted_rarities, weights=weights, k=1)[0]
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
            item_id, item_data = random.choice(items_by_rarity[selected_rarity])
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
        chosen_room_id = random.choice(eligible_rooms)
        debug_log(f"Selected room {chosen_room_id} for item {item_id}")
        
        # Place the item in the chosen room
        self.item_locations[item_id] = chosen_room_id
        
        # Update spawn counter for this item
        self.item_spawn_counts[item_id] = self.item_spawn_counts.get(item_id, 0) + 1
        debug_log(f"Placed item {item_id} in room {chosen_room_id} (spawn count: {self.item_spawn_counts[item_id]})")
        
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
        debug_log(f"Getting items in room {room_id}")
        # Get all items from the item_locations dictionary
        items_from_locations = [item_id for item_id, location in self.item_locations.items() if location == room_id]
        
        # As a backup, check the room data directly (some items might not be in the tracking dict)
        room_data = self.get_room(room_id)
        if room_data and "items" in room_data:
            items_in_room_data = room_data.get("items", []) or []  # Handle None by returning empty list
            # Combine both sources, ensuring no duplicates
            combined_items = list(set(items_from_locations + items_in_room_data))
            debug_log(f"Found {len(combined_items)} items in room {room_id}: {combined_items}")
            return combined_items
        
        debug_log(f"Found {len(items_from_locations)} items in room {room_id}: {items_from_locations}")
        return items_from_locations
    
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
    
    def get_enemy(self, enemy_id):
        """Get enemy data by ID"""
        enemy = self.enemies.get(enemy_id)
        if enemy is None:
            debug_log(f"WARNING: Requested non-existent enemy: {enemy_id}")
            debug_log(f"Available enemy IDs: {list(self.enemies.keys())}")
        else:
            debug_log(f"Retrieved enemy data for {enemy_id}")
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
            return True
        debug_log(f"WARNING: Attempted to remove item {item_id} that is not in any room")
        return False
    
    def add_item_to_room(self, item_id, room_id):
        """Add an item to a room (when dropped)"""
        self.item_locations[item_id] = room_id
        debug_log(f"Added item {item_id} to room {room_id}")
    
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
            
            return True
            
        debug_log(f"WARNING: Could not find enemy {enemy_id} to remove")
        return False
    
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
    
    def get_state(self):
        """Get the current state of the world (for saving)"""
        debug_log("Getting world state for saving")
        return {
            "item_locations": self.item_locations,
            "enemy_locations": self.enemy_locations,
            "npc_locations": self.npc_locations,
            "room_states": self.room_states,
            "item_spawn_counts": self.item_spawn_counts
        }
    
    def set_state(self, state_data):
        """Set the state of the world (for loading)"""
        debug_log("Setting world state from save data")
        self.item_locations = state_data.get("item_locations", {})
        self.enemy_locations = state_data.get("enemy_locations", {})
        self.npc_locations = state_data.get("npc_locations", {})
        self.room_states = state_data.get("room_states", {})
        self.item_spawn_counts = state_data.get("item_spawn_counts", {})
        debug_log(f"Loaded: {len(self.item_locations)} items, {len(self.enemy_locations)} enemies, {len(self.npc_locations)} NPCs")
    
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