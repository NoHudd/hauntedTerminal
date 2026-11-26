#!/usr/bin/env python3
"""
Development configuration for HFSE game
Simplified configuration that imports from settings.py
"""


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
    # No settings.py: use player defaults. Deliberately silent — this is the
    # normal case for every player, and printing to stdout here scribbles on the
    # terminal right before the TUI takes it over. Contributors who want the dev
    # flags copy config/settings.example.py to config/settings.py.
    DEV_MODE = False
    DEBUG_MODE = False
    DEBUG_COMMAND = False
    DEBUG_ITEM = False
    DEBUG_COMBAT = False
    DEBUG_ROOM = False
    DEBUG_PLAYER = False
    DEBUG_WORLD = False
    SKIP_INTRO = False
    DISABLE_ANIMATIONS = False
    DEBUG_LOG_FILE = "debug.log"

# Runtime-mutable UX flags (not part of settings.py). SettingsManager updates
# these live; the domain reads them (e.g. LsCommand for in-game hints).
SHOW_HINTS = True  # inline "→ take/cat/cd" affordances in room listings

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
