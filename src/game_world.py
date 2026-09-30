#!/usr/bin/env python3
from utils.debug_tools import debug_log

TUTORIAL_ENEMY = "glitched_process.tmp"


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
        enemy_id = TUTORIAL_ENEMY
        if enemy_id not in self.enemies:
            debug_log(f"Tutorial enemy {enemy_id} not found in enemies data")
            return
        if enemy_id not in self.enemy_locations:
            self.enemy_locations[enemy_id] = room_id
            debug_log(f"Tutorial enemy {enemy_id} spawned in {room_id}")

    def scale_enemy_stats(self, enemy, player_class):
        """Scale an enemy for the player's class, in place (callers pass a copy)."""
        if not enemy or not player_class:
            return enemy

        base_health = enemy.health
        base_damage = enemy.damage
        
        # Per-class enemy scaling is neutralized: it previously made enemies
        # TOUGHER for the fragile "aggressive" class (Weaver) and EASIER for the
        # tanky "defensive" class (Guardian), compounding class imbalance. All
        # classes now face the same enemies; challenge comes from the global
        # difficulty mode instead. (power_scaling kept for loot flavor.)
        health_multiplier = 1.0
        damage_multiplier = 1.0
        
        # Apply scaling
        enemy.health = max(1, int(base_health * health_multiplier))
        enemy.damage = max(1, int(base_damage * damage_multiplier))

        for attack in enemy.attack_patterns:
            if "damage" in attack:
                attack["damage"] = max(1, int(attack["damage"] * damage_multiplier))

        debug_log(f"Enemy scaled: {base_health}HP -> {enemy.health}HP, {base_damage}DMG -> {enemy.damage}DMG")
        return enemy

    def _initialize_world_state(self):
        """Initialize item and enemy locations from room data"""
        # Roll each room's enemies from the difficulty-tier pools once, here at
        # world-init. The result flows into enemy_locations below, which get_state
        # persists — so reloads keep the same world (set_state skips this init).
        from src import enemy_pools, rng
        rolled_enemies = enemy_pools.roll_room_enemies(self.rooms, self.enemies, rng)
        for room_id, room_data in self.rooms.items():
            debug_log(f"Initializing state for room: {room_id}")
            # Initialize room state
            self.room_states[room_id] = {
                "visited": False,
                "locked": room_data.locked,
                "hidden": room_data.hidden,
                "key_required": room_data.key_required,
            }
            
            if self.room_states[room_id]["locked"]:
                debug_log(f"Room {room_id} is locked. Key required: {self.room_states[room_id]['key_required']}")
            if self.room_states[room_id]["hidden"]:
                debug_log(f"Room {room_id} is hidden")
            
            # Initialize enemies in this room (rolled from tier pools, or pinned)
            enemy_count = 0
            for enemy_id in rolled_enemies.get(room_id, []):
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
            for npc_id in room_data.npcs or []:
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
            for item_id in room_data.items or []:
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
        """Class data as typed CharacterClass models (delegates to the shared loader)."""
        from src.data_loader import load_class_data
        return load_class_data()
    
    def get_room(self, room_id):
        """Get room data by ID"""
        room = self.rooms.get(room_id)
        if room is None:
            debug_log(f"WARNING: Attempted to get non-existent room: {room_id}")
        else:
            debug_log(f"Retrieved room data for {room_id}", category="world")
        return room
    
    def get_room_state(self, room_id):
        """Get the state of a room"""
        state = self.room_states.get(room_id, {"visited": False, "locked": False})
        if room_id not in self.room_states:
            debug_log(f"WARNING: Requested state for unknown room {room_id}, returning default state")
        return state
    
    def _room_state(self, room_id):
        return self.room_states.setdefault(room_id, {"visited": False, "locked": False})

    def mark_hidden_files_listed(self, room_id):
        """`ls -a` ran here: this room's dotfiles are now known to the player,
        so Tab may offer them."""
        self._room_state(room_id)["hiddenListed"] = True

    def hidden_files_listed(self, room_id) -> bool:
        state = self.room_states.get(room_id, {})
        # "hidden_listed" was the first spelling, in saves from 2026-09-29.
        return bool(state.get("hiddenListed") or state.get("hidden_listed"))

    def mark_flag_captured(self, room_id):
        self._room_state(room_id)["flagCaptured"] = True

    def flag_captured(self, room_id) -> bool:
        return bool(self.room_states.get(room_id, {}).get("flagCaptured", False))

    def mark_flag_taught(self, room_id):
        self._room_state(room_id)["flagTaught"] = True

    def flag_taught(self, room_id) -> bool:
        return bool(self.room_states.get(room_id, {}).get("flagTaught", False))

    def flag_counts(self, exclude=None):
        """(main got, main total, secret got, secret total) over rooms with a
        flag. Hidden rooms are secrets. `exclude` leaves one room out."""
        main_got = main_total = secret_got = secret_total = 0
        for rid, room in self.rooms.items():
            if rid == exclude or getattr(room, "flag", None) is None:
                continue
            got = int(self.flag_captured(rid))
            if room.hidden:
                secret_total += 1
                secret_got += got
            else:
                main_total += 1
                main_got += got
        return main_got, main_total, secret_got, secret_total

    def reveal_doors(self, key_id):
        """A key was gained: the doors it opens become visible (still locked
        until walked into). Returns the room ids newly revealed."""
        item = self.items.get(key_id)
        revealed = []
        for rid in getattr(item, "unlocks", None) or []:
            state = self._room_state(str(rid))
            if not state.get("keyRevealed"):
                state["keyRevealed"] = True
                revealed.append(str(rid))
        return revealed

    def door_visible(self, room_id):
        """False while the room or any ancestor is locked and not yet revealed
        by its key. Flag-gated rooms (/boot) always stay in view."""
        from src.room_paths import ancestors, room_at, room_path

        target = room_path(room_id)
        for path in ancestors(target) + [target]:
            rid = room_at(path)
            if rid is None:
                continue
            if getattr(self.get_room(rid), "flags_required", 0):
                continue
            state = self.room_states.get(rid, {})
            if state.get("locked", False) and not state.get("keyRevealed", False):
                return False
        return True

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
    
    # ------------------------------------------------------------------
    # Room contents.
    #
    # The *_locations dicts are the ONLY runtime truth. World init seeds them
    # from each room's YAML (see _initialize_world_state), and set_state
    # restores them from a save.
    #
    # These getters used to also union in the room's static YAML list "as a
    # backup". That made defeat/pickup unrepresentable across a save: killing an
    # enemy removed it from enemy_locations and mutated the in-memory Room model,
    # but _load_game_data_for_load re-reads the YAML fresh, so every scripted
    # boss came back to life on load. Do not reintroduce the fallback.
    # ------------------------------------------------------------------

    def get_items_in_room(self, room_id):
        """Item ids currently on the floor of room_id."""
        items = [
            item_id
            for item_id, location in self.item_locations.items()
            if location == room_id and item_id not in self.removed_items
        ]
        debug_log(f"Found {len(items)} items in room {room_id}: {items}", category="world")
        return items

    def get_enemies_in_room(self, room_id):
        """Enemy ids currently alive in room_id."""
        enemies = [
            enemy_id
            for enemy_id, location in self.enemy_locations.items()
            if location == room_id
        ]
        debug_log(f"Found {len(enemies)} enemies in room {room_id}: {enemies}", category="world")
        return enemies

    def get_npcs_in_room(self, room_id):
        """NPC ids currently present in room_id."""
        npcs = [
            npc_id
            for npc_id, location in self.npc_locations.items()
            if location == room_id
        ]
        debug_log(f"Found {len(npcs)} NPCs in room {room_id}: {npcs}", category="world")
        return npcs
    
    def get_item(self, item_id):
        """A private copy of an item template; it may end up in the inventory."""
        item = self.items.get(item_id)
        if item is None:
            debug_log(f"WARNING: Requested non-existent item: {item_id}")
            return None
        return item.model_copy(deep=True)
    
    def get_enemy(self, enemy_id, player_class=None):
        """Get enemy data by ID, optionally scaled for player class"""
        enemy = self.enemies.get(enemy_id)
        if enemy is None:
            debug_log(f"WARNING: Requested non-existent enemy: {enemy_id}")
            debug_log(f"Available enemy IDs: {list(self.enemies.keys())}")
            return enemy

        debug_log(f"Retrieved enemy data for {enemy_id}")

        # A private copy: scaling mutates it, and a fight holds it for its
        # whole duration, so the shared template must never be handed out.
        enemy = enemy.model_copy(deep=True)

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
                if enemy_data and enemy_data.name == enemy_id:
                    room_id = location
                    del self.enemy_locations[potential_enemy_id]
                    enemy_id = potential_enemy_id  # Use the actual ID for further operations
                    debug_log(f"Removed enemy with display name {enemy_id} from enemy_locations (room: {room_id})")
                    break
        
        # NOTE: the loaded Room models are shared, immutable-by-convention content
        # templates. We deliberately do NOT strip the enemy from room_data.enemies
        # here — deleting it from enemy_locations above is the whole removal, and
        # mutating the template used to be a workaround for the YAML fallback that
        # get_enemies_in_room no longer has.
        if room_id:
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

    def is_room_cleared(self, room_id):
        """Whether a room is done: its flag captured (if it has one), and then
        visited if it never had enemies, otherwise its enemies genuinely dealt
        with — not merely
        absent right now. A fled enemy is removed from enemy_locations too,
        but respawn_fled_enemies puts it right back on the player's next
        ROOM_ENTERED for this room, so "currently no enemies present" alone
        is not enough; fled_enemies must also be empty for this room."""
        room = self.get_room(room_id)
        if getattr(room, "flag", None) is not None and not self.flag_captured(room_id):
            return False
        ever_had_enemies = bool(getattr(room, "enemies", None)) or \
            getattr(room, "enemy_tier", None) is not None
        if not ever_had_enemies:
            # Nothing to fight: visiting is what clears it.
            return bool(self.room_states.get(room_id, {}).get("visited", False))
        still_present = bool(self.get_enemies_in_room(room_id))
        still_fled_pending = bool(self.fled_enemies.get(room_id))
        return not still_present and not still_fled_pending

    def get_exits(self, room_id):
        """Get available exits from a room"""
        room = self.get_room(room_id)
        if not room:
            debug_log(f"WARNING: Attempted to get exits for non-existent room: {room_id}")
            return []
        exits = room.exits
        debug_log(f"Room {room_id} has exits: {exits}")
        return exits

    def visible_exits(self, room_id):
        """The exits a player can see from here, as `ls` shows them: no hidden
        room before `ls -a` finds it, no locked door before its key reveals it.
        Anything that names or completes a door uses this."""
        return [
            exit_id for exit_id in self.get_exits(room_id)
            if self.is_discovered(exit_id) and self.door_visible(exit_id)
        ]
    
    def is_discovered(self, room_id):
        """Whether a room is visible at all. Undiscovered rooms behave like paths
        that do not exist — `ls -a` in the parent is what reveals them."""
        return not self.get_room_state(room_id).get("hidden", False)

    def check_access(self, room_id, player=None):
        """Can the player enter room_id? Returns (allowed, denial or None).

        Movement is not restricted by the exit graph — you may `cd` to any path,
        exactly as in a real shell. What restricts you is permission, and, as on
        a real filesystem, you need it on *every ancestor directory*, not just
        the destination. So /usr being sealed also seals /usr/games beneath it.

        A denial is a dict: {"path", "room_id", "reason", "key_required",
        "class_restriction"}, where reason is "missing" | "locked" | "class" |
        "flags" (a "flags" denial adds "flags_required" and "flags_have").
        """
        from src.room_paths import ancestors, room_at, room_path

        target_path = room_path(room_id)
        for path in ancestors(target_path) + [target_path]:
            rid = room_at(path)
            if rid is None:
                continue
            state = self.get_room_state(rid)

            if state.get("hidden", False):
                return False, {
                    "path": path, "room_id": rid, "reason": "missing",
                    "key_required": None, "class_restriction": None,
                }
            # Class restriction is reported before the lock: a key the player can
            # never use is not the useful half of the message.
            room = self.get_room(rid)
            restriction = getattr(room, "class_restriction", "") if room else ""
            if restriction and player is not None:
                if str(getattr(player, "player_class", "")).lower() != str(restriction).lower():
                    return False, {
                        "path": path, "room_id": rid, "reason": "class",
                        "key_required": None, "class_restriction": restriction,
                    }

            if state.get("locked", False):
                # A door its key has not revealed yet does not exist, as far
                # as the player can tell.
                return False, {
                    "path": path, "room_id": rid,
                    "reason": "locked" if state.get("keyRevealed") else "missing",
                    "key_required": state.get("key_required"),
                    "class_restriction": None,
                }

            required = getattr(room, "flags_required", 0) if room else 0
            if required:
                have = self.flag_counts(exclude=rid)[0]
                if have < required:
                    return False, {
                        "path": path, "room_id": rid, "reason": "flags",
                        "key_required": None, "class_restriction": None,
                        "flags_required": required, "flags_have": have,
                    }

        debug_log(f"Access granted to {room_id} ({target_path})")
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
        name = room_data.name or 'An Unnamed Room'
        description = room_data.description or 'A featureless space.'
        full_description = f"[bold cyan]{name}[/bold cyan]\n{description}\n"

        # Items
        items_in_room = self.get_items_in_room(room_id)
        if items_in_room:
            full_description += "\n[bold yellow]You see the following items:[/bold yellow]\n"
            for item_id in items_in_room:
                it = self.items.get(item_id)
                item_name = it.name if it else item_id
                full_description += f"- {item_name}\n"

        # Enemies
        enemies_in_room = self.get_enemies_in_room(room_id)
        if enemies_in_room:
            full_description += "\n[bold red]Enemies:[/bold red]\n"
            for enemy_id in enemies_in_room:
                e = self.enemies.get(enemy_id)
                enemy_name = e.name if e else enemy_id
                full_description += f"- {enemy_name}\n"

        # NPCs
        npcs_in_room = self.get_npcs_in_room(room_id)
        if npcs_in_room:
            full_description += "\n[bold green]People:[/bold green]\n"
            for npc_id in npcs_in_room:
                npc = self.npcs.get(npc_id)
                npc_name = npc.name if npc else npc_id
                full_description += f"- {npc_name}\n"

        return full_description.strip()