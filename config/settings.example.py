"""
Haunted Terminal Settings - TEMPLATE
Copy this file to settings.py and edit the boolean values below.

Setup:
  cp config/settings.example.py config/settings.py
  # Then edit config/settings.py with your preferences

Defaults below are PLAYER settings (clean playthrough). Flip to True
for local dev work (verbose logging, skip intro, no animations).
"""

# =============================================================================
# MASTER SWITCHES
# =============================================================================
DEV_MODE = False          # Enable development features
DEBUG_MODE = False        # Enable debug logging

# =============================================================================
# DEBUG CATEGORIES
# =============================================================================
DEBUG_COMMAND = False     # Log command parsing and execution
DEBUG_ITEM = False        # Log item interactions
DEBUG_COMBAT = False      # Log combat calculations
DEBUG_ROOM = False        # Log room navigation
DEBUG_PLAYER = False      # Log player state changes
DEBUG_WORLD = False       # Log world state changes

# =============================================================================
# UI SETTINGS
# =============================================================================
SKIP_INTRO = False        # Skip intro monologue/cutscenes
DISABLE_ANIMATIONS = False # Disable typewriter effects

# =============================================================================
# DEBUG OUTPUT
# =============================================================================
DEBUG_LOG_FILE = "debug.log"  # Location of debug log file
