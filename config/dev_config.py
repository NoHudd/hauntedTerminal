#!/usr/bin/env python3
"""
Development configuration for HFSE game
Simplified configuration that loads .env file
"""

import os
from pathlib import Path

def load_env_file():
    """
    Load environment variables from .env file in the project root.
    This only sets values that aren't already set in the environment.
    """
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        return
        
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Only set if not already in environment
                if key not in os.environ:
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    os.environ[key] = value

# Load the .env file before setting any variables
load_env_file()

# Main configuration flags used by the system
DEV_MODE = os.environ.get("HFSE_DEV_MODE", "False").lower() in ["true", "1", "yes"]
DEBUG_MODE = os.environ.get("HFSE_DEBUG", "False").lower() in ["true", "1", "yes"]

# Print active development settings if in dev mode
if DEV_MODE and DEBUG_MODE:
    print("=== DEVELOPMENT MODE ACTIVE ===")
    print(f"DEBUG_MODE: {DEBUG_MODE}")
    print(f"SKIP_INTRO: {os.environ.get('HFSE_SKIP_INTRO', 'false')}")
    print(f"DISABLE_ANIMATIONS: {os.environ.get('HFSE_DISABLE_ANIMATIONS', 'false')}")
    print("===============================") 
