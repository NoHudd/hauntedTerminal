#!/usr/bin/env python3
"""
Rarity System for HFSE Items

Provides consistent rarity tiers, colors, and display formatting
for weapons and other items throughout the game.
"""

from enum import Enum
from typing import Dict, Tuple

class RarityTier(Enum):
    """Item rarity tiers with associated display properties."""
    COMMON = ("common", "white", "⚪")
    UNCOMMON = ("uncommon", "green", "🟢")
    RARE = ("rare", "blue", "🔵")
    EPIC = ("epic", "magenta", "🟣")
    LEGENDARY = ("legendary", "yellow", "🟡")
    
    def __init__(self, name: str, color: str, emoji: str):
        self.rarity_name = name
        self.color = color
        self.emoji = emoji

class RaritySystem:
    """Handles rarity-related functionality for items."""
    
    # Rarity color mapping for Rich text markup
    RARITY_COLORS = {
        "common": "white",
        "uncommon": "green", 
        "rare": "blue",
        "epic": "magenta",
        "legendary": "yellow"
    }
    
    # Rarity emojis for visual distinction
    RARITY_EMOJIS = {
        "common": "⚪",
        "uncommon": "🟢", 
        "rare": "🔵",
        "epic": "🟣",
        "legendary": "🟡"
    }
    
    # Rarity order for sorting (lowest to highest)
    RARITY_ORDER = {
        "common": 1,
        "uncommon": 2,
        "rare": 3, 
        "epic": 4,
        "legendary": 5
    }
    
    @staticmethod
    def get_rarity_color(rarity: str) -> str:
        """Get the Rich color markup for a rarity."""
        return RaritySystem.RARITY_COLORS.get(rarity.lower(), "white")
    
    @staticmethod
    def get_rarity_emoji(rarity: str) -> str:
        """Get the emoji for a rarity."""
        return RaritySystem.RARITY_EMOJIS.get(rarity.lower(), "⚪")
    
    @staticmethod
    def get_rarity_order(rarity: str) -> int:
        """Get the numeric order for sorting by rarity."""
        return RaritySystem.RARITY_ORDER.get(rarity.lower(), 1)
    
    @staticmethod
    def format_item_name_with_rarity(item_name: str, rarity: str, show_emoji: bool = False) -> str:
        """
        Format an item name with rarity color and indicator.
        
        Args:
            item_name: The base item name
            rarity: The item rarity
            show_emoji: Whether to include rarity emoji (deprecated, kept for compatibility)
            
        Returns:
            Formatted string with Rich markup
        """
        color = RaritySystem.get_rarity_color(rarity)
        rarity_text = f"({rarity.title()})"
        
        return f"[{color}]{item_name} {rarity_text}[/{color}]"
    
    @staticmethod
    def format_inventory_item(item_id: str, item_data: dict, is_equipped: bool = False) -> str:
        """
        Format an item for inventory display with rarity.
        
        Args:
            item_id: The item identifier
            item_data: The item data dictionary
            is_equipped: Whether the item is currently equipped
            
        Returns:
            Formatted string for inventory display
        """
        item_type = item_data.get("type", "")
        rarity = item_data.get("rarity", "common")
        damage = item_data.get("damage", 0)
        healing = item_data.get("healing", 0)
        item_name = item_data.get("name", item_id)
        
        # Get rarity formatting
        color = RaritySystem.get_rarity_color(rarity)
        
        # Build the display line with colored rarity
        item_display = f"[{color}]{item_name} ({rarity.title()})[/{color}]"
        
        # Add damage info for weapons
        if item_type == "weapon" and damage > 0:
            item_display += f" [{color}]({damage} dmg)[/{color}]"
        elif item_type == "consumable" and healing > 0:
            item_display += f" [{color}]({healing} heal)[/{color}]"
        
        # Check if this item is equipped
        if is_equipped:
            item_display += " [cyan](equipped)[/]"
        
        return item_display
    
    @staticmethod
    def get_all_rarities() -> list:
        """Get list of all available rarities in order."""
        return ["common", "uncommon", "rare", "epic", "legendary"]
    
    @staticmethod
    def is_valid_rarity(rarity: str) -> bool:
        """Check if a rarity string is valid."""
        return rarity.lower() in RaritySystem.RARITY_COLORS