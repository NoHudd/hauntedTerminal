"""
InventoryPanel widget — renders the player's inventory in the sidebar.
"""

from __future__ import annotations

from textual.widgets import Static

import logging
from src.item_icons import item_icon
from src.rarity import RaritySystem
from engine.view_models import InventoryItemView, InventoryView

logger = logging.getLogger(__name__)


class InventoryPanel(Static):
    """Sidebar panel that displays the player's inventory."""

    def update_inventory(self, inventory_view: InventoryView | None) -> None:
        """Render inventory from an InventoryView."""
        if inventory_view is None:
            return

        items = inventory_view.items

        if not items:
            content = "[dim italic]Empty inventory[/dim italic]"
        else:
            # Stack items by name — count duplicates
            item_counts: dict[str, tuple[int, InventoryItemView, bool]] = {}
            for item in items:
                name = item.name
                is_equipped = item.is_equipped

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
                key=lambda x: (-RaritySystem.get_rarity_order(x[2].rarity), x[0])
            )

            inventory_lines = []
            rarity_sections: dict[str, list[str]] = {}
            for name, count, item_data, is_equipped in stacked_items:
                rarity = item_data.rarity
                if rarity not in rarity_sections:
                    rarity_sections[rarity] = []
                item_display = self._format_enhanced_inventory_item(
                    item_data.id, item_data, is_equipped, count
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

        def remove_update_class() -> None:
            try:
                self.remove_class("panel-update")
            except Exception:
                pass

        self.set_timer(0.5, remove_update_class)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_enhanced_inventory_item(
        self, item_id: str, item_data: InventoryItemView, is_equipped: bool = False, count: int = 1
    ) -> str:
        """Format an inventory item with enhanced visual styling."""
        name = item_data.name
        rarity = item_data.rarity
        rarity_color = RaritySystem.get_rarity_color(rarity)

        item_text = f"[{rarity_color}]{name}[/{rarity_color}]"
        count_text = f" [bold yellow]x{count}[/bold yellow]" if count > 1 else ""

        stat_info = ""
        item_type = item_data.item_type

        if item_type == "weapon":
            stat_info = f" [cyan]+{item_data.damage} DMG[/cyan]"
        elif item_data.healing:
            over = f" over {item_data.healTurns} turns" if item_data.healTurns else ""
            stat_info = f" [green]+{item_data.healing} HP{over}[/green]"

        equipped_indicator = " [green bold]⚡EQUIPPED[/green bold]" if is_equipped else ""
        type_icon = self._get_item_type_icon(item_type)

        return f"{type_icon} {item_text}{count_text}{stat_info}{equipped_indicator}"

    def _get_item_type_icon(self, item_type: str) -> str:
        return item_icon(item_type)
