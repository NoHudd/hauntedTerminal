"""Turn what the player typed into an item id."""
import re

from utils.debug_tools import debug_log

_SEPARATORS = re.compile(r"[\s_.\-]+")


def name_key(s: str) -> str:
    """Comparison form of an item name: case and separators don't matter, so
    `health_packet`, `health packet`, `health-packet` and `healthPacket` all
    compare equal."""
    return _SEPARATORS.sub("", s.lower())


class ItemResolver:
    """Item lookup by id, display name, shortcut or partial match."""

    SHORTCUTS = {
        # Consumables
        "hp": ["health_packet", "stable_cache"],
        "health": ["health_packet", "stable_cache"],
        "potion": ["health_packet", "stable_cache", "overflowing_buffer"],
        "heal": ["health_packet", "stable_cache"],
        "packet": ["health_packet"],

        # Weapons
        "shield": ["segfault_shield"],
        "pointer": ["null_pointer"],
        "whisper": ["daemon_whisper"],

        # Other consumables
        "buffer": ["overflowing_buffer"],
        "cache": ["stable_cache"],
        "backup": ["legacy_backup"],
        "seed": ["sudo_seed"]
    }

    def __init__(self, world, player):
        self.world = world
        self.player = player

    def _find_in(self, search_term, item_ids, get_item_fn):
        """Find an item ID whose id or display name matches, ignoring case and
        separators."""
        target = name_key(search_term)
        if not target:
            return None
        for item_id in item_ids:
            if name_key(item_id) == target:
                return item_id
            item_data = get_item_fn(item_id)
            if item_data and name_key(item_data.name) == target:
                return item_id
        return None

    def find_in_list(self, search_term, item_list):
        """Find item ID in a room's item list by name or ID."""
        return self._find_in(search_term, item_list, self.world.get_item)

    def find_in_inventory(self, search_term):
        """Find item in player inventory by name or ID."""
        return self._find_in(
            search_term, self.player.inventory, self.player.get_item_from_inventory
        )

    def player_keys(self):
        """Get list of keys in player inventory."""
        keys = []
        for item_id, item_data in self.player.inventory.items():
            if item_data and (item_data.type == "key" or "key" in item_id.lower()):
                keys.append(item_id)
        return keys

    def resolve_shortcut(self, item_input, location="room"):
        """Resolve item shortcuts and partial matches to actual item IDs."""
        # Inventory lookups go through player's resolver (handles instance suffixes)
        if location == "inventory":
            return self.player.resolve_inventory_item(item_input)

        # Get available items based on location
        if location == "room":
            current_room = self.player.current_room
            available_items = self.world.get_items_in_room(current_room)
        else:
            available_items = []

        debug_log(f"Resolving item shortcut '{item_input}' in {location}, available items: {available_items}")

        # First, check if it's an exact match
        if item_input in available_items:
            return item_input

        key = name_key(item_input)
        if not key:
            return None

        # Same name, any spelling (case, _, -, spaces, camelCase)
        spelled = self.find_in_list(item_input, available_items)
        if spelled:
            return spelled

        # Check shortcuts
        if key in self.SHORTCUTS:
            shortcut_items = self.SHORTCUTS[key]
            for shortcut_item in shortcut_items:
                if shortcut_item in available_items:
                    debug_log(f"Shortcut '{item_input}' resolved to '{shortcut_item}'")
                    return shortcut_item

        # Check partial matches (starts with the input)
        partial_matches = [item for item in available_items if name_key(item).startswith(key)]
        if len(partial_matches) == 1:
            debug_log(f"Partial match '{item_input}' resolved to '{partial_matches[0]}'")
            return partial_matches[0]
        elif len(partial_matches) > 1:
            debug_log(f"Multiple partial matches for '{item_input}': {partial_matches}")
            # For health items, prefer health_packet
            if "health_packet" in partial_matches:
                return "health_packet"
            return partial_matches[0]  # Return first match as fallback

        # Check if input contains key words that match item names
        for available_item in available_items:
            if key in name_key(available_item):
                debug_log(f"Substring match '{item_input}' found in '{available_item}'")
                return available_item

        debug_log(f"No match found for '{item_input}'")
        return None
