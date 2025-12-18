#!/usr/bin/env python3
import os
import json
import time
import logging
from src.events import event_bus, EventType

logger = logging.getLogger(__name__)

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
                "total_damage": player.total_damage,
                "health": player.health,
                "max_health": player.max_health,
                "permanent_health_boost": player.permanent_health_boost,
                "permanent_damage_boost": player.permanent_damage_boost,
                "inventory": player.inventory,
                "equipped_weapon": player.equipped_weapon,
                "current_room": player.current_room,
                "previous_room": player.previous_room,
                "player_id": player.player_id,
                "tutorial_state": player.tutorial_state,
                "spells": player.spells
            },
            "world": world_state,
            "timestamp": time.time(),
            "save_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            # Write to file
            with open(save_path, 'w') as file:
                json.dump(save_data, file, indent=2)
            
            logger.info(f"Game saved successfully to {save_path}")
            
            # Emit save completion event
            event_bus.emit_event(
                EventType.GAME_SAVED,
                {
                    "save_path": save_path,
                    "save_name": save_name,
                    "player_name": player.name,
                    "timestamp": save_data["timestamp"]
                },
                "SaveManager"
            )
            
            return save_path
            
        except Exception as e:
            logger.error(f"Failed to save game: {e}")
            raise
    
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
            
            logger.info(f"Game loaded successfully from {filename}")
            
            # Emit load completion event
            event_bus.emit_event(
                EventType.GAME_LOADED,
                {
                    "filename": filename,
                    "file_path": file_path,
                    "player_name": save_data.get("player", {}).get("name", "Unknown"),
                    "timestamp": save_data.get("timestamp"),
                    "save_date": save_data.get("save_date")
                },
                "SaveManager"
            )
            
            return save_data
            
        except FileNotFoundError:
            logger.warning(f"Save file not found: {filename}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse save file {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load game from {filename}: {e}")
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

    def get_most_recent_save(self):
        """
        Get the most recent save file.
        
        Returns:
            dict: Save info for the most recent save, or None if no saves exist
        """
        save_files = self.get_save_files()
        return save_files[0] if save_files else None
    
    def load_most_recent_save(self):
        """
        Load the most recent save file.
        
        Returns:
            dict: The loaded save data or None if no saves exist
        """
        most_recent = self.get_most_recent_save()
        if most_recent:
            return self.load_game(most_recent["filename"])
        return None

# Create a singleton instance
save_manager = SaveManager()

# Convenience functions for easy access
def load_most_recent_save():
    """Load the most recent save file."""
    return save_manager.load_most_recent_save() 