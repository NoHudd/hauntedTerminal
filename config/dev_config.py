#!/usr/bin/env python3
"""
Development configuration for HFSE game
Simplified configuration that imports from settings.py
"""

import os

# Import all settings from the settings module
try:
    from config.settings import (
        DEV_MODE,
        DEBUG_MODE,
        DEBUG_COMMAND,
        DEBUG_ITEM,
        DEBUG_COMBAT,
        DEBUG_ROOM,
        DEBUG_PLAYER,
        DEBUG_WORLD,
        SKIP_INTRO,
        DISABLE_ANIMATIONS,
        DEBUG_LOG_FILE
    )
except ImportError:
    # Fallback to defaults if settings.py doesn't exist
    print("Warning: config/settings.py not found. Using default settings.")
    print("Copy config/settings.example.py to config/settings.py to customize.")

    DEV_MODE = True
    DEBUG_MODE = True
    DEBUG_COMMAND = True
    DEBUG_ITEM = True
    DEBUG_COMBAT = True
    DEBUG_ROOM = True
    DEBUG_PLAYER = True
    DEBUG_WORLD = True
    SKIP_INTRO = True
    DISABLE_ANIMATIONS = True
    DEBUG_LOG_FILE = "debug.log"

# Export all for backward compatibility
__all__ = [
    'DEV_MODE',
    'DEBUG_MODE',
    'DEBUG_COMMAND',
    'DEBUG_ITEM',
    'DEBUG_COMBAT',
    'DEBUG_ROOM',
    'DEBUG_PLAYER',
    'DEBUG_WORLD',
    'SKIP_INTRO',
    'DISABLE_ANIMATIONS',
    'DEBUG_LOG_FILE'
]

# Print active development settings if in dev mode
if DEV_MODE and DEBUG_MODE:
    print("=== DEVELOPMENT MODE ACTIVE ===")
    print(f"DEBUG_MODE: {DEBUG_MODE}")
    print(f"SKIP_INTRO: {SKIP_INTRO}")
    print(f"DISABLE_ANIMATIONS: {DISABLE_ANIMATIONS}")
    print("===============================")
