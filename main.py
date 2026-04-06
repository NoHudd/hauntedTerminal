#!/usr/bin/env python3
import os
import sys
import shutil
from src.game_engine import main

if __name__ == "__main__":
    # Create necessary directories if they don't exist
    os.makedirs("data/rooms", exist_ok=True)
    os.makedirs("data/items", exist_ok=True)
    os.makedirs("data/enemies", exist_ok=True)
    os.makedirs("data/npcs", exist_ok=True)

    # Copy debug.log to combat.log on each restart (overwrites old combat.log)
    if os.path.exists("debug.log"):
        shutil.copy2("debug.log", "combat.log")
        # Clear debug.log for fresh logging this session
        with open("debug.log", "w") as f:
            f.write("")
    else:
        # Create empty combat.log if debug.log doesn't exist
        with open("combat.log", "w") as f:
            f.write("=== Combat Log (Fresh Session) ===\n")

    # Run the game
    main() 