#!/usr/bin/env python3
"""
Rarity System for HFSE Items

Single source of truth for all rarity tiers. Each entry is (color, emoji, sort_order).
Adding a new rarity only requires one line here.
"""

# (color, emoji, sort_order)
RARITIES: dict[str, tuple[str, str, int]] = {
    "common":    ("white",   "⚪", 1),
    "uncommon":  ("green",   "🟢", 2),
    "rare":      ("blue",    "🔵", 3),
    "epic":      ("magenta", "🟣", 4),
    "legendary": ("yellow",  "🟡", 5),
    "unique":    ("red",     "🔴", 6),
}

_DEFAULT = ("white", "⚪", 1)


class RaritySystem:
    """Convenience accessors for the RARITIES table."""

    # Keep RARITY_COLORS as a property so existing code that reads it directly still works
    RARITY_COLORS = {k: v[0] for k, v in RARITIES.items()}
    RARITY_EMOJIS = {k: v[1] for k, v in RARITIES.items()}
    RARITY_ORDER  = {k: v[2] for k, v in RARITIES.items()}

    @staticmethod
    def get_rarity_color(rarity: str) -> str:
        return RARITIES.get(str(rarity).lower(), _DEFAULT)[0]

    @staticmethod
    def get_rarity_emoji(rarity: str) -> str:
        return RARITIES.get(str(rarity).lower(), _DEFAULT)[1]

    @staticmethod
    def get_rarity_order(rarity: str) -> int:
        return RARITIES.get(str(rarity).lower(), _DEFAULT)[2]

    @staticmethod
    def format_item_name_with_rarity(item_name: str, rarity: str, show_emoji: bool = False) -> str:
        color = RaritySystem.get_rarity_color(rarity)
        return f"[{color}]{item_name} ({str(rarity).title()})[/{color}]"

    @staticmethod
    def format_inventory_item(item_id: str, item_data: dict, is_equipped: bool = False) -> str:
        item_type = item_data.get("type", "")
        rarity    = str(item_data.get("rarity", "common"))
        damage    = item_data.get("damage", 0)
        healing   = item_data.get("healing", 0)
        item_name = item_data.get("name", item_id)

        color = RaritySystem.get_rarity_color(rarity)
        item_display = f"[{color}]{item_name} ({rarity.title()})[/{color}]"

        if item_type == "weapon" and damage > 0:
            item_display += f" [{color}]({damage} dmg)[/{color}]"
        elif item_type == "consumable" and healing > 0:
            item_display += f" [{color}]({healing} heal)[/{color}]"

        if is_equipped:
            item_display += " [cyan](equipped)[/]"

        return item_display

    @staticmethod
    def get_all_rarities() -> list:
        return sorted(RARITIES.keys(), key=lambda r: RARITIES[r][2])

    @staticmethod
    def is_valid_rarity(rarity: str) -> bool:
        return str(rarity).lower() in RARITIES
