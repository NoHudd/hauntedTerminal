"""New-run world generation: scatter loot, keys and starter gear.

Runs once at new-game setup. It writes GameWorld's item_locations and
item_spawn_counts and reads its content; the runtime never calls back in here.
"""
import logging

from src import rng
from utils.debug_tools import debug_log

logger = logging.getLogger(__name__)


class ItemPlacer:
    """Places items into a freshly initialized GameWorld."""

    def __init__(self, world):
        self.world = world

    def place_items(self, player_class=None):
        """
        Place items in the game world based on class, zones, and rarity.
        
        Args:
            player_class: Player class to determine item placement strategy
        """
        debug_log(f"Starting class-based item placement for player_class: {player_class}")
        
        # Always place the class-specific starter weapon first
        if player_class and player_class in self.world.class_data:
            self._place_starter_weapon(player_class)
        
        if not player_class or player_class not in self.world.class_data:
            debug_log("Invalid or missing player class, using default placement")
            return self._place_items_default(player_class)
            
        return self._place_items_class_based(player_class)
    
    def _place_starter_weapon(self, player_class):
        """Ensure the class-specific starter weapon is available in safe zones."""
        debug_log(f"Ensuring starter weapon availability for class: {player_class}")
        
        class_info = self.world.class_data[player_class]
        starter_weapon = class_info.starter_weapon
        
        if not starter_weapon:
            debug_log(f"No starter weapon defined for class {player_class}")
            return
            
        # Check if the weapon item exists in the items collection
        weapon_found = False
        for item_id, item_data in self.world.items.items():
            name_match = item_data.name.lower().replace(" ", "_") == starter_weapon
            if item_id == starter_weapon or name_match:
                weapon_found = True
                # Ensure it can spawn in safe zones like home_grove (live model mutation)
                if "safe" not in item_data.allowed_zones:
                    item_data.allowed_zones.append("safe")
                debug_log(f"Starter weapon {starter_weapon} configured for dynamic placement")
                break
                
        if not weapon_found:
            debug_log(f"Starter weapon {starter_weapon} not found in items data")
    
    def _place_items_class_based(self, player_class):
        """Place items based on player class preferences and zone affinity."""
        debug_log(f"Executing class-based placement for {player_class}")

        class_info = self.world.class_data[player_class]
        preferred_zones = class_info.preferred_zones
        loot_preferences = class_info.loot_preference
        power_scaling = class_info.power_scaling

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

    def _keys_granted_by_enemies(self):
        """Key ids obtainable as enemy drops, so they are not also scattered."""
        granted = set()
        for enemy in self.world.enemies.values():
            for drop in enemy.drops:
                item_id = drop.item
                if item_id and self.is_key(item_id):
                    granted.add(str(item_id))
        return granted

    def is_key(self, item_id):
        item = self.world.items.get(item_id)
        if item is None:
            return False
        item_type = item.get("type") if isinstance(item, dict) else item.type
        return str(item_type).lower() == "key"

    def rooms_reachable_with(self, held_keys):
        """Rooms a player holding held_keys could actually walk into.

        Traversal needs permission on every ancestor, so a room is reachable only
        if nothing on the way to it is locked without a held key. Hidden rooms
        count as reachable — `ls -a` in the (reachable) parent reveals them.
        Class-restricted rooms never count: two thirds of players cannot enter
        them, so nothing required for progression may live there.
        """
        from src.room_paths import ancestors, room_at, room_path

        reachable = []
        for room_id in self.world.rooms:
            target = room_path(room_id)
            ok = True
            for path in ancestors(target) + [target]:
                rid = room_at(path)
                if rid is None:
                    continue
                room = self.world.get_room(rid)
                if getattr(room, "class_restriction", "") or "":
                    ok = False
                    break
                state = self.world.room_states.get(rid, {})
                if state.get("locked", False) and state.get("key_required") not in held_keys:
                    ok = False
                    break
            if ok:
                reachable.append(room_id)
        return reachable

    def _place_keys(self):
        """Place progression keys so every run is completable.

        Keys are placed in dependency order: each one lands in a room the player
        can already reach with the keys placed before it. Reachability only ever
        grows, so this cannot strand a key behind the door it opens — the failure
        the old "scatter into any unlocked room" version could produce once locks
        started carrying the difficulty ramp.
        """
        from_drops = self._keys_granted_by_enemies()
        unplaced = [
            item_id for item_id in self.world.items
            if self.is_key(item_id)
            and item_id not in self.world.item_locations
            and item_id not in from_drops
        ]
        if not unplaced:
            return

        rng.shuffle(unplaced)
        held = set()

        while unplaced:
            spots = [
                room_id for room_id in self.rooms_reachable_with(held)
                if room_id != "home_grove"  # starter room keeps its authored items
            ]
            if not spots:
                debug_log(f"WARNING: no reachable room left for keys {unplaced}")
                return

            key_id = unplaced.pop(0)
            allowed = self.world.get_item(key_id).get("allowed_rooms") or []
            preferred = [r for r in spots if r in allowed] or spots

            room_id = rng.choice(preferred)
            self.world.item_locations[key_id] = room_id
            self.world.item_spawn_counts[key_id] = 1
            held.add(key_id)
            debug_log(f"Placed key {key_id} in {room_id} (reachable with {sorted(held)})")


    def _ensure_home_grove_basics(self):
        """Ensure home_grove has essential consumables for good player experience."""
        # item_locations maps item_id -> room_id, so check it correctly
        home_grove_items = [item_id for item_id, loc in self.world.item_locations.items() if loc == "home_grove"]

        # Check if there's already a healing consumable in home_grove
        def _tags(iid):
            it = self.world.items.get(iid)
            return it.tags if it else []
        has_health_item = any(
            "healing" in _tags(item_id)
            for item_id in home_grove_items
        )

        # health_packet is always placed via room YAML, so this is just a safety net
        if not has_health_item and "health_packet" in self.world.items:
            if "health_packet" not in self.world.item_locations:
                self.world.item_locations["health_packet"] = "home_grove"
                self.world.item_spawn_counts["health_packet"] = 1
                debug_log("Added health_packet to home_grove as safety net")
    
    def _place_items_default(self, player_class=None):
        """Fallback placement for an unknown/missing class.

        player_class was read here but never a parameter: this path raised
        NameError the moment it ran, which is why nobody noticed the fallback
        was broken — reaching it needs a class outside classes.yaml.
        """
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
        for item_id, item_data in self.world.items.items():
            # Typed template -> plain dict for this placement pass (read-only).
            if not isinstance(item_data, dict):
                item_data = item_data.model_dump(exclude_unset=True)
            # Skip if item is already placed in a fixed location
            if item_id in self.world.item_locations:
                debug_log(f"Skipping item {item_id} - already placed")
                continue
            
            # Skip items that don't match the player's class if specified
            if player_class and not self._item_suitable_for_class(item_data, player_class):
                debug_log(f"Skipping item {item_id} - class restriction mismatch vs {player_class}")
                continue
            
            # Check if the item has already reached its max spawn count
            max_spawn = item_data.get("max_spawn", 1)
            current_spawn = self.world.item_spawn_counts.get(item_id, 0)
            
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
        num_rooms = len(self.world.rooms)
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
        # Locked rooms are eligible: a lock is a *when*, not a *never*. The
        # tier-3 rooms behind keys are exactly where good loot belongs, and
        # starving them left players unlocking a door onto an empty room.
        eligible_rooms = list(self.world.rooms.keys())
        debug_log(f"Found {len(eligible_rooms)} eligible rooms for item placement")
        
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
                if room_id in self.world.rooms:
                    eligible_rooms.append(room_id)
        else:
            # No specific room restrictions: any room, locked or not.
            eligible_rooms = list(self.world.rooms.keys())
        
        # If no eligible rooms, item can't be placed
        if not eligible_rooms:
            debug_log(f"No eligible rooms to place item {item_id}")
            return False
        
        # Select a random room from eligible rooms
        chosen_room_id = rng.choice(eligible_rooms)
        debug_log(f"Selected room {chosen_room_id} for item {item_id}")
        
        # Place the item in the chosen room
        self.world.item_locations[item_id] = chosen_room_id
        
        # Update spawn counter for this item
        self.world.item_spawn_counts[item_id] = self.world.item_spawn_counts.get(item_id, 0) + 1
        debug_log(f"Placed item {item_id} in room {chosen_room_id} (spawn count: {self.world.item_spawn_counts[item_id]})")
        
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
        
        for room_id, room_data in self.world.rooms.items():
            zone = room_data.zone or "neutral"
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
            room_data = self.world.rooms.get(room_id, {})
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

        for item_id, item_data in self.world.items.items():
            # Typed template -> plain dict for this placement pass (read-only).
            if not isinstance(item_data, dict):
                item_data = item_data.model_dump(exclude_unset=True)
            # Skip already placed items
            if item_id in self.world.item_locations:
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
        return sum(1 for item_id, loc in self.world.item_locations.items() if loc == room_id)

    def _get_allowed_rarities_for_room(self, room_id: str, room_data) -> list:
        """Determine which item rarities are allowed in a room based on characteristics."""
        # Get room characteristics (room_data is a typed Room model)
        enemies = room_data.enemies
        enemy_count = len(enemies)
        zone = room_data.zone or 'neutral'
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
        class_info = self.world.class_data.get(player_class.lower())
        starter_weapon = class_info.starter_weapon if class_info else None

        if starter_weapon and starter_weapon in self.world.items:
            # Force-place directly into item_locations — skip the item cap check so
            # the weapon always lands in home_grove regardless of how many YAML items
            # were pre-loaded into the room during world state initialization.
            if starter_weapon not in self.world.item_locations:
                self.world.item_locations[starter_weapon] = "home_grove"
                self.world.item_spawn_counts[starter_weapon] = 1
                debug_log(f"Placed {starter_weapon} in home_grove for {player_class}")
            else:
                debug_log(f"Starter weapon {starter_weapon} already placed in {self.world.item_locations[starter_weapon]}, moving to home_grove")
                self.world.item_locations[starter_weapon] = "home_grove"
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
            r = self.world.rooms.get(room_id)
            room_zone = r.zone if r else ""
            if room_prefix not in allowed_zones and room_zone not in allowed_zones:
                return False
        return True

    def _place_item_in_room(self, item_id, item_data, room_id, max_items_per_room=5):
        """Place a specific item in a specific room."""
        # Check item's own zone/room constraints
        if not self._item_fits_room(item_data, room_id):
            return False

        # Check per-room item limit
        current_room_items = self._count_items_in_room(room_id)
        if current_room_items >= max_items_per_room:
            debug_log(f"Room {room_id} already has {current_room_items} items (limit: {max_items_per_room}), skipping {item_id}")
            return False

        # Check if this item is already placed (to prevent overriding fixed items)
        if item_id in self.world.item_locations:
            debug_log(f"Item {item_id} already placed in {self.world.item_locations[item_id]}, skipping dynamic placement")
            return False

        # Place the item
        self.world.item_locations[item_id] = room_id
        self.world.item_spawn_counts[item_id] = self.world.item_spawn_counts.get(item_id, 0) + 1

        debug_log(f"Placed {item_id} in room {room_id}")
        return True
