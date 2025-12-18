"""
HFSE Development Settings - TEMPLATE
Copy this file to settings.py and edit the boolean values below.

Setup:
  cp config/settings.example.py config/settings.py
  # Then edit config/settings.py with your preferences
"""

# =============================================================================
# MASTER SWITCHES
# =============================================================================
DEV_MODE = True          # Enable development features
DEBUG_MODE = True        # Enable debug logging

# =============================================================================
# DEBUG CATEGORIES
# =============================================================================
DEBUG_COMMAND = True     # Log command parsing and execution
DEBUG_ITEM = True        # Log item interactions
DEBUG_COMBAT = True      # Log combat calculations
DEBUG_ROOM = True        # Log room navigation
DEBUG_PLAYER = True      # Log player state changes
DEBUG_WORLD = True       # Log world state changes

# =============================================================================
# UI SETTINGS
# =============================================================================
SKIP_INTRO = True        # Skip intro monologue/cutscenes
DISABLE_ANIMATIONS = True # Disable typewriter effects

# =============================================================================
# DEBUG OUTPUT
# =============================================================================
DEBUG_LOG_FILE = "debug.log"  # Location of debug log file
