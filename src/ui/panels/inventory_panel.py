"""
InventoryPanel widget — renders the player's inventory in the sidebar.
"""

from textual.widgets import Static

import logging
from src.rarity import RaritySystem

logger = logging.getLogger(__name__)


class InventoryPanel(Static):
    """Sidebar panel that displays the player's inventory."""

    def update_inventory(self, inventory_view: dict) -> None:
        """Render inventory from an InventoryView dict."""
        if not inventory_view:
            return

        items = inventory_view.get('items', [])

        if not items:
            content = "[dim italic]Empty inventory[/dim italic]"
        else:
            # Stack items by name — count duplicates
            item_counts: dict = {}
            for item in items:
                name = item.get("name", item.get("id"))
                is_equipped = item.get("is_equipped", False)

                if name in item_counts:
                    count, data, was_equipped = item_counts[name]
                    item_counts[name] = (count + 1, data, was_equipped or is_equipped)
                else:
                    item_counts[name] = (1, item, is_equipped)

            stacked_items = [
                (name, count, data, equipped)
                for name, (count, data, equipped) in item_counts.items()
            ]
            stacked_items.sort(
                key=lambda x: (-RaritySystem.get_rarity_order(x[2].get("rarity", "common")), x[0])
            )

            inventory_lines = []
            rarity_sections: dict = {}
            for name, count, item_data, is_equipped in stacked_items:
                rarity = item_data.get("rarity", "common")
                if rarity not in rarity_sections:
                    rarity_sections[rarity] = []
                item_display = self._format_enhanced_inventory_item(
                    item_data.get("id"), item_data, is_equipped, count
                )
                rarity_sections[rarity].append(item_display)

            rarity_order = ["unique", "legendary", "epic", "rare", "uncommon", "common"]
            for rarity in rarity_order:
                if rarity in rarity_sections:
                    rarity_header = f"[{RaritySystem.RARITY_COLORS[rarity]} bold]═══ {rarity.upper()} ═══[/]"
                    inventory_lines.append(rarity_header)
                    inventory_lines.extend(rarity_sections[rarity])
                    inventory_lines.append("")

            content = "\n".join(inventory_lines).rstrip()

        self.add_class("panel-update")
        self.update(content)

        def remove_update_class():
            try:
                self.remove_class("panel-update")
            except Exception:
                pass

        self.set_timer(0.5, remove_update_class)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_enhanced_inventory_item(
        self, item_id: str, item_data: dict, is_equipped: bool = False, count: int = 1
    ) -> str:
        """Format an inventory item with enhanced visual styling."""
        name = item_data.get("name", item_id)
        rarity = item_data.get("rarity", "common")
        rarity_color = RaritySystem.get_rarity_color(rarity)

        item_text = f"[{rarity_color}]{name}[/{rarity_color}]"
        count_text = f" [bold yellow]x{count}[/bold yellow]" if count > 1 else ""

        stat_info = ""
        item_type = item_data.get("item_type", item_data.get("type", ""))

        if item_type == "weapon" and "damage" in item_data:
            damage = item_data["damage"]
            stat_info = f" [cyan]+{damage} DMG[/cyan]"
        elif item_type == "consumable":
            if "combat_effects" in item_data and "player_heal" in item_data["combat_effects"]:
                heal = item_data["combat_effects"]["player_heal"]
                stat_info = f" [green]+{heal} HP[/green]"
            elif "on_use" in item_data and "heal" in item_data["on_use"]:
                heal = item_data["on_use"]["heal"]
                stat_info = f" [green]+{heal} HP[/green]"

        equipped_indicator = " [green bold]⚡EQUIPPED[/green bold]" if is_equipped else ""
        type_icon = self._get_item_type_icon(item_type)

        return f"{type_icon} {item_text}{count_text}{stat_info}{equipped_indicator}"

    def _get_item_type_icon(self, item_type: str) -> str:
        """Get an appropriate icon for item type."""
        icons = {
            "weapon": "⚔️",
            "consumable": "🧪",
            "script": "📜",
            "key": "🗝️",
            "armor": "🛡️",
            "tool": "🔧",
            "misc": "📦",
        }
        return icons.get(item_type, "📄")
