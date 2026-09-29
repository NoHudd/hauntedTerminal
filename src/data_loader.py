#!/usr/bin/env python3
import os
import yaml
from utils.debug_tools import debug_log

# Cache for loaded data to avoid repeated disk reads
_class_data_cache = None
_items_cache = None
_abilities_data_cache = None

def load_class_data():
    """Load character classes as typed engine CharacterClass models (id -> model)."""
    global _class_data_cache

    if _class_data_cache is not None:
        return _class_data_cache

    try:
        from engine.content.loader import load_classes
        _class_data_cache = {str(cid): klass for cid, klass in load_classes("data").items()}
        debug_log(f"Loaded class data: {list(_class_data_cache.keys())}")
        return _class_data_cache
    except Exception as e:
        debug_log(f"ERROR loading class data: {e}")
        return {}

def load_item(item_id):
    """A private copy of one item template (any category), or None."""
    global _items_cache
    if _items_cache is None:
        from engine.content.loader import load_items
        _items_cache = {str(k): v for k, v in load_items("data").items()}
    item = _items_cache.get(item_id)
    if item is None:
        debug_log(f"Item {item_id} not found")
        return None
    return item.model_copy(deep=True)

def load_abilities_data():
    """Load abilities from abilities.yaml"""
    global _abilities_data_cache
    
    # Return cached data if available
    if _abilities_data_cache is not None:
        return _abilities_data_cache
    
    try:
        # Try to load from abilities.yaml
        filepath = 'data/abilities.yaml'
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                data = yaml.safe_load(file)
                if data is None:
                    debug_log("ERROR: Empty abilities file")
                    return {"abilities": {}}
                
                # Store in cache
                _abilities_data_cache = data
                debug_log(f"Loaded abilities data with {len(data.get('abilities', {}))} abilities")
                return data
        else:
            debug_log(f"ERROR: Abilities file not found at path: {filepath}")
            return {"abilities": {}}
            
    except Exception as e:
        debug_log(f"ERROR loading abilities data: {e}")
        return {"abilities": {}}

def get_abilities_for_class(class_name):
    """Get all abilities for a specific class"""
    all_abilities = load_abilities_data().get("abilities", {})
    class_abilities = {}
    
    for ability_id, ability_data in all_abilities.items():
        # Check if this ability belongs to the specified class
        if ability_data.get("class") == class_name or "all" in ability_data.get("class", ""):
            class_abilities[ability_id] = ability_data
    
    if not class_abilities:
        debug_log(f"WARNING: No abilities found for class '{class_name}'")
        
    return class_abilities

# Helper to load a YAML file
def load_yaml(filepath):
    """Load data from a YAML file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                data = yaml.safe_load(file)
                return data or {}
        else:
            debug_log(f"ERROR: File not found: {filepath}")
            return {}
    except Exception as e:
        debug_log(f"ERROR loading YAML file {filepath}: {e}")
        return {}

# (Optional) Load all enemies
def load_enemy_data():
    """Load all enemies as typed engine Enemy models (id -> model, dots kept)."""
    try:
        from engine.content.loader import load_enemies
        enemies = {str(eid): e for eid, e in load_enemies("data").items()}
        debug_log(f"Total enemies loaded: {len(enemies)}")
        return enemies
    except Exception as e:
        debug_log(f"ERROR loading enemy data: {e}")
        return {}

def load_room_data():
    """Load all rooms as typed engine Room models (id -> model)."""
    try:
        from engine.content.loader import load_rooms
        return {str(rid): r for rid, r in load_rooms("data").items()}
    except Exception as e:
        debug_log(f"ERROR loading room data: {e}")
        return {}


def load_npc_data():
    """Load all NPCs as typed NPC models (id -> NPC, dots kept in the id)."""
    try:
        from engine.content.loader import load_npcs
        return {str(nid): npc for nid, npc in load_npcs("data").items()}
    except Exception as e:
        debug_log(f"ERROR loading npc data: {e}")
        return {}


# Tutorial hints cache
_tutorial_hints_cache = None


def load_tutorial_hints():
    """Tutorial hint text (step id -> template) from data/tutorial_hints.yaml.

    Templates may contain {player_name} and {weapon_name}; the caller formats
    them. Returns {} if the file is missing or malformed — a broken tutorial
    should not stop the game from starting.
    """
    global _tutorial_hints_cache
    if _tutorial_hints_cache is not None:
        return _tutorial_hints_cache

    data = load_yaml("data/tutorial_hints.yaml")
    if not isinstance(data, dict):
        debug_log("ERROR: tutorial_hints.yaml is not a mapping")
        data = {}
    _tutorial_hints_cache = {str(k): str(v) for k, v in data.items()}
    debug_log(f"Loaded {len(_tutorial_hints_cache)} tutorial hints")
    return _tutorial_hints_cache
