#!/usr/bin/env python3
import os
import yaml
from debug_tools import debug_log

# Cache for loaded data to avoid repeated disk reads
_class_data_cache = None
_weapon_data_cache = {}
_abilities_data_cache = None

def load_class_data():
    """Load character class data from YAML"""
    global _class_data_cache
    
    # Return cached data if available
    if _class_data_cache is not None:
        return _class_data_cache
    
    try:
        # Try to load from classes.yaml
        filepath = 'data/classes.yaml'
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                data = yaml.safe_load(file)
                if data is None:
                    debug_log("ERROR: Empty classes file")
                    return {}
                    
                # Store in cache
                _class_data_cache = data.get("classes", {})
                debug_log(f"Loaded class data: {list(_class_data_cache.keys())}")
                return _class_data_cache
        else:
            debug_log("ERROR: Classes file not found at path: " + filepath)
            return {}
            
    except Exception as e:
        debug_log(f"ERROR loading class data: {e}")
        return {}

def load_weapon_data(weapon_id):
    """Load data for a specific weapon from weapons.yaml"""
    global _weapon_data_cache
    
    # Return cached data if available
    if weapon_id in _weapon_data_cache:
        return _weapon_data_cache[weapon_id]
    
    try:
        # Load from weapons.yaml
        filepath = 'data/items/weapons.yaml'
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                data = yaml.safe_load(file)
                if data is None or "weapons" not in data:
                    debug_log(f"ERROR: Invalid weapons file structure in {filepath}")
                    return None
                
                # Find the weapon in the data
                weapons = data.get("weapons", {})
                if weapon_id in weapons:
                    weapon_data = weapons[weapon_id]
                    # Add ID to the weapon data
                    weapon_data["id"] = weapon_id
                    # Add to cache
                    _weapon_data_cache[weapon_id] = weapon_data
                    debug_log(f"Loaded weapon data for {weapon_id}")
                    return weapon_data
                else:
                    debug_log(f"ERROR: Weapon {weapon_id} not found in weapons.yaml")
                    return None
        else:
            debug_log(f"ERROR: Weapons file not found at path: {filepath}")
            return None
            
    except Exception as e:
        debug_log(f"ERROR loading weapon data: {e}")
        return None

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
    """Load enemies from starter_enemies.yaml."""
    return load_yaml("data/enemies/enemies.yaml").get("enemies", {})

# (Optional) Load all rooms
def load_room_data():
    """Load all rooms from data/rooms."""
    rooms = {}
    room_folder = "data/rooms/"
    for filename in os.listdir(room_folder):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            room_id = filename.replace(".yaml", "").replace(".yml", "")
            rooms[room_id] = load_yaml(os.path.join(room_folder, filename))
    return rooms
