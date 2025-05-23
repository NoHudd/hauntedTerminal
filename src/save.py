#!/usr/bin/env python3
import os
import json
import time

class SaveManager:
    """Handles saving and loading game data."""
    
    def __init__(self, save_dir="saves"):
        """Initialize the save manager with the save directory."""
        self.save_dir = save_dir
        # Ensure the save directory exists
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
    
    def save_game(self, player, world_state, save_name=None):
        """
        Save the current game state to a JSON file.
        
        Args:
            player: Player object with game state
            world_state: Dictionary with world state information
            save_name: Optional name for the save file, defaults to timestamp
        
        Returns:
            str: Path to the saved file
        """
        if not save_name:
            # Generate a filename based on timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            save_name = f"save_{timestamp}.json"
        
        # Create the full file path
        save_path = os.path.join(self.save_dir, save_name)
        
        # Create save data structure
        save_data = {
            "player": {
                "name": player.name,
                "player_class": player.player_class,
                "base_damage": player.base_damage,
                "health": player.health,
                "max_health": player.max_health,
                "permanent_health_boost": player.permanent_health_boost,
                "permanent_damage_boost": player.permanent_damage_boost,
                "inventory": player.inventory,
                "equipped_weapon": player.equipped_weapon,
                "current_room": player.current_room,
                "spells": player.spells
            },
            "world": world_state,
            "timestamp": time.time(),
            "save_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Write to file
        with open(save_path, 'w') as file:
            json.dump(save_data, file, indent=2)
        
        return save_path
    
    def load_game(self, filename):
        """
        Load a game from a save file.
        
        Args:
            filename: Name of the save file to load
        
        Returns:
            dict: The loaded save data or None if file not found
        """
        file_path = os.path.join(self.save_dir, filename)
        
        try:
            with open(file_path, 'r') as file:
                save_data = json.load(file)
            return save_data
        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            return None
    
    def get_save_files(self):
        """
        Get a list of available save files.
        
        Returns:
            list: List of dictionaries with save file info (filename, date, player name)
        """
        save_files = []
        
        for filename in os.listdir(self.save_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.save_dir, filename)
                try:
                    with open(file_path, 'r') as file:
                        save_data = json.load(file)
                    
                    save_info = {
                        "filename": filename,
                        "date": save_data.get("save_date", "Unknown date"),
                        "player_name": save_data.get("player", {}).get("name", "Unknown"),
                        "player_class": save_data.get("player", {}).get("player_class", "Unknown"),
                        "location": save_data.get("player", {}).get("current_room", "Unknown")
                    }
                    
                    save_files.append(save_info)
                except (json.JSONDecodeError, KeyError):
                    # Skip corrupt save files
                    continue
        
        # Sort by date (newest first)
        save_files.sort(key=lambda x: x["date"], reverse=True)
        return save_files
    
    def delete_save(self, filename):
        """
        Delete a save file.
        
        Args:
            filename: Name of the save file to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        file_path = os.path.join(self.save_dir, filename)
        
        try:
            os.remove(file_path)
            return True
        except FileNotFoundError:
            return False

# Create a singleton instance
save_manager = SaveManager() 