"""One icon per item type, so every view names an item the same way."""
from __future__ import annotations

# Plain glyphs, no U+FE0F variation selector: it jams against the following
# text in many terminals.
ITEM_TYPE_ICONS: dict[str, str] = {
    "weapon": "🗡",
    "armor": "🛡",
    "consumable": "💊",
    "key": "🔑",
    "lore": "📜",
}
UNKNOWN_ICON = "📦"


def item_icon(item_type: str | None) -> str:
    return ITEM_TYPE_ICONS.get(str(item_type or "").lower(), UNKNOWN_ICON)
