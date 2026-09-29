#!/usr/bin/env python3
import os
import json
import time
import logging

from src import difficulty

logger = logging.getLogger(__name__)

# Current on-disk save format version. v4 added the run's difficulty and the
# player's equipped armor and status effects; a v3 save loads with medium
# difficulty, no armor and no effects.
SAVE_VERSION = 4

# Saves older than this cannot be loaded. v2 and earlier predate the filesystem
# tree: they persist room_states captured when /usr, /var and /boot carried no
# locks, so restoring one would hand the player an unsealed boss room and a
# world whose paths no longer match its content. Rather than silently produce a
# broken run, we refuse them and say why.
MIN_SUPPORTED_VERSION = 3

# Autosaves fire on each story beat (a lore file read), plus every manual save.
# Without a cap the pool grows unbounded and every save/list operation slows
# with directory size (observed: 16k files).
MAX_SAVE_FILES = 20


class IncompatibleSaveError(Exception):
    """Raised when a save predates a world change that cannot be migrated."""


def save_version(save_data) -> int:
    """Envelope version of a loaded save. Pre-versioning saves count as v1."""
    if not isinstance(save_data, dict):
        return 0
    try:
        return int(save_data.get("version", 1))
    except (TypeError, ValueError):
        return 0


def _migrate_save(save_data):
    """Normalize a save envelope to the current version, or refuse it.

    v1 (no "version" field) used snake_case envelope keys; v2 added "version"
    and camelCase fields ("savedAt", "saveDate").

    v3 is where migration stops being possible. A save persists room_states —
    including which rooms are locked — and v2 saves were written when /usr, /var
    and /boot had no locks at all. Restoring one would reopen the boss room and
    hand back a world whose room paths no longer describe the tree the game now
    navigates. There is no honest way to reconstruct the intended run from that,
    so v2 and older are refused with a message rather than half-migrated into
    something subtly broken.
    """
    if not isinstance(save_data, dict):
        return save_data

    version = save_version(save_data)
    if version < MIN_SUPPORTED_VERSION:
        raise IncompatibleSaveError(
            f"save format v{version} is from before the filesystem rework and "
            f"cannot be loaded (current format is v{SAVE_VERSION})"
        )
    return save_data

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
        
        # Create save data structure (versioned envelope, camelCase fields).
        save_data = {
            "version": SAVE_VERSION,
            "player": player.to_dict(),
            "world": world_state,
            "difficulty": difficulty.current_mode(),
            "savedAt": time.time(),
            "saveDate": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            # Write to file
            with open(save_path, 'w') as file:
                json.dump(save_data, file, indent=2)
            
            logger.info(f"Game saved successfully to {save_path}")
            self._prune_old_saves()

            # NOTE: do NOT emit GAME_SAVED here. GAME_SAVED is the *request* event
            # (_on_save_requested handles it by calling save_game); re-emitting it on
            # completion re-triggers the handler → infinite recursion → save storm.
            # Callers show their own "saved" confirmation directly.
            return save_path
            
        except Exception as e:
            logger.error(f"Failed to save game: {e}")
            raise
    
    def _prune_old_saves(self):
        """Keep only the newest MAX_SAVE_FILES saves; delete the rest."""
        try:
            files = [
                os.path.join(self.save_dir, f)
                for f in os.listdir(self.save_dir)
                if f.endswith(".json")
            ]
            if len(files) <= MAX_SAVE_FILES:
                return
            files.sort(key=lambda p: (os.path.getmtime(p), p))
            for path in files[: len(files) - MAX_SAVE_FILES]:
                os.remove(path)
            logger.info(f"Pruned {len(files) - MAX_SAVE_FILES} old saves (cap {MAX_SAVE_FILES})")
        except Exception as e:
            # Pruning must never break saving itself.
            logger.warning(f"Save pruning failed: {e}")

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

            save_data = _migrate_save(save_data)
            logger.info(f"Game loaded successfully from {filename}")
            return save_data

        except IncompatibleSaveError as e:
            logger.warning(f"Refusing incompatible save {filename}: {e}")
            raise
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
        skipped = 0

        for filename in os.listdir(self.save_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.save_dir, filename)
                try:
                    with open(file_path, 'r') as file:
                        save_data = json.load(file)

                    # Saves the current build cannot load are not offered at all,
                    # so the load menu never presents a choice that then fails.
                    save_data = _migrate_save(save_data)
                    save_info = {
                        "filename": filename,
                        "date": save_data.get("saveDate", "Unknown date"),
                        "player_name": save_data.get("player", {}).get("name", "Unknown"),
                        "player_class": save_data.get("player", {}).get("player_class", "Unknown"),
                        "location": save_data.get("player", {}).get("current_room", "Unknown")
                    }
                    
                    save_files.append(save_info)
                except IncompatibleSaveError:
                    skipped += 1
                    continue
                except (json.JSONDecodeError, KeyError, OSError):
                    # Skip corrupt save files
                    continue

        if skipped:
            logger.info(
                f"Ignored {skipped} save(s) from an older, incompatible format"
            )

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