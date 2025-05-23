#!/usr/bin/env python3
import os
import sys
from src.game_engine import main

if __name__ == "__main__":
    # Create necessary directories if they don't exist
    os.makedirs("data/rooms", exist_ok=True)
    os.makedirs("data/items", exist_ok=True)
    os.makedirs("data/enemies", exist_ok=True)
    os.makedirs("data/npcs", exist_ok=True)
    
    # Run the game
    main() 