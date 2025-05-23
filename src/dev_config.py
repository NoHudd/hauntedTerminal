#!/usr/bin/env python3
"""
Development configuration for HFSE game
Enable/disable various development features
"""

import os

# Development mode master switch
# Set to False in production
DEV_MODE = os.environ.get("HFSE_DEV_MODE", "False").lower() in ["true", "1", "yes"]

# Debug logging is controlled in debug_tools.py
# This is just a convenience reference to the env var
DEBUG_MODE = os.environ.get("HFSE_DEBUG", "False").lower() in ["true", "1", "yes"]

# Development cheats
GOD_MODE = False  # Player is invincible
UNLIMITED_INVENTORY = False  # No inventory size limits
REVEAL_MAP = False  # Auto-reveal all rooms
UNLOCK_ALL = False  # All doors are unlocked
FREE_ITEMS = False  # Items cost nothing

# Auto-grant permissions for all commands
ADMIN_MODE = False

# Development testing
SKIP_INTRO = True  # Skip intro sequence
FAST_START = False  # Start with basic items and in a specific room

# Performance tuning
DISABLE_ANIMATIONS = False  # Disable all animations
MINIMAL_UI = False  # Use minimal UI for faster rendering

# Testing helpers
TEST_SEED = None  # Set a specific random seed for testing
RECORD_ACTIONS = False  # Record all player actions for replay

# Check if we should override any settings from environment variables
if DEV_MODE:
    GOD_MODE = os.environ.get("HFSE_GOD_MODE", "False").lower() in ["true", "1", "yes"]
    UNLIMITED_INVENTORY = os.environ.get("HFSE_UNLIMITED_INVENTORY", "False").lower() in ["true", "1", "yes"]
    REVEAL_MAP = os.environ.get("HFSE_REVEAL_MAP", "False").lower() in ["true", "1", "yes"]
    UNLOCK_ALL = os.environ.get("HFSE_UNLOCK_ALL", "False").lower() in ["true", "1", "yes"]
    FREE_ITEMS = os.environ.get("HFSE_FREE_ITEMS", "False").lower() in ["true", "1", "yes"]
    ADMIN_MODE = os.environ.get("HFSE_ADMIN_MODE", "False").lower() in ["true", "1", "yes"]
    SKIP_INTRO = os.environ.get("HFSE_SKIP_INTRO", "False").lower() in ["true", "1", "yes"]
    FAST_START = os.environ.get("HFSE_FAST_START", "False").lower() in ["true", "1", "yes"]
    DISABLE_ANIMATIONS = os.environ.get("HFSE_DISABLE_ANIMATIONS", "False").lower() in ["true", "1", "yes"]
    MINIMAL_UI = os.environ.get("HFSE_MINIMAL_UI", "False").lower() in ["true", "1", "yes"]
    RECORD_ACTIONS = os.environ.get("HFSE_RECORD_ACTIONS", "False").lower() in ["true", "1", "yes"]
    
    # Get test seed if provided
    if os.environ.get("HFSE_TEST_SEED"):
        try:
            TEST_SEED = int(os.environ.get("HFSE_TEST_SEED"))
        except ValueError:
            # If not an integer, use the string as a seed
            TEST_SEED = os.environ.get("HFSE_TEST_SEED")

# Print active development settings if in dev mode
if DEV_MODE and DEBUG_MODE:
    print("=== DEVELOPMENT MODE ACTIVE ===")
    print(f"GOD_MODE: {GOD_MODE}")
    print(f"UNLIMITED_INVENTORY: {UNLIMITED_INVENTORY}")
    print(f"REVEAL_MAP: {REVEAL_MAP}")
    print(f"UNLOCK_ALL: {UNLOCK_ALL}")
    print(f"FREE_ITEMS: {FREE_ITEMS}")
    print(f"ADMIN_MODE: {ADMIN_MODE}")
    print(f"SKIP_INTRO: {SKIP_INTRO}")
    print(f"FAST_START: {FAST_START}")
    print(f"DISABLE_ANIMATIONS: {DISABLE_ANIMATIONS}")
    print(f"MINIMAL_UI: {MINIMAL_UI}")
    print(f"TEST_SEED: {TEST_SEED}")
    print(f"RECORD_ACTIONS: {RECORD_ACTIONS}")
    print("===============================") 