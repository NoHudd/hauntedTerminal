"""
CharacterPanel — the player's model and the gear they have on, below Stats.

The battle scene is the only other place the class sprite appears, so outside
a fight this is where a new player sees who they are and what they're
wielding. An empty slot names the command that fills it.
"""

from __future__ import annotations

import time

from PIL import Image
from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from engine.view_models import InventoryItemView, InventoryView, StatsView
from src.item_icons import item_icon
from src.rarity import RaritySystem
from src.scene.effects import BOB_PERIOD, bob_offset
from src.scene.sprite_store import SpriteStore, to_renderable

SPRITE_PX = 18      # figure box; half-block rendering draws it 9 rows tall


def _equipped(inventory: InventoryView | None, kind: str) -> InventoryItemView | None:
    for item in inventory.items if inventory else []:
        if item.is_equipped and item.item_type == kind:
            return item
    return None


def _name(item: InventoryItemView) -> str:
    color = RaritySystem.get_rarity_color(item.rarity)
    return f"[{color}]{item.name}[/{color}]"


def gear_lines(player: StatsView, inventory: InventoryView | None) -> list[str]:
    """The text column: weapon then armor, each with the number it adds."""
    lines = [f"{item_icon('weapon')} [bold]Weapon[/bold]"]
    weapon = _equipped(inventory, "weapon")
    if weapon is not None:
        lines += [_name(weapon), f"[cyan]+{weapon.damage or 0} DMG[/cyan]"]
    else:
        lines.append("[dim]none — type equip <name>[/dim]")

    lines += ["", f"{item_icon('armor')} [bold]Armor[/bold]"]
    armor = _equipped(inventory, "armor")
    if armor is not None:
        lines += [_name(armor), f"[cyan]-{player.defense_pct}% dmg taken[/cyan]"]
    else:
        lines.append("[dim]none — type equip <name>[/dim]")
    return lines


class CharacterPanel(Static):
    """Sidebar panel: class sprite beside the equipped weapon and armor."""

    _BOB_TICK_SECONDS = BOB_PERIOD / 4

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = SpriteStore()
        self._player: StatsView | None = None
        self._inventory: InventoryView | None = None
        self._reduce_motion = False
        self._bob = 0

    def on_mount(self) -> None:
        self.border_title = "🧍 Character"
        self.set_interval(self._BOB_TICK_SECONDS, self._bob_tick)

    def update_character(
        self,
        player: StatsView | None,
        inventory: InventoryView | None,
        reduce_motion: bool = False,
    ) -> None:
        if player is None:
            return
        self._player, self._inventory = player, inventory
        self._reduce_motion = reduce_motion
        if reduce_motion:
            self._bob = 0
        self._render_panel()

    def _bob_tick(self) -> None:
        """Idle bob, like the battle scene: redraw only when the lift flips."""
        if self._player is None or self._reduce_motion:
            return
        new_bob = bob_offset(time.monotonic())
        if new_bob != self._bob:
            self._bob = new_bob
            self._render_panel()

    def _sprite(self, player_class: str) -> Image.Image:
        figure = self._store.get_sprite("classes", player_class, SPRITE_PX, SPRITE_PX)
        # Spare rows above so the bob lifts the figure without clipping it;
        # an even height keeps half-block cells whole.
        canvas = Image.new("RGBA", (SPRITE_PX, SPRITE_PX + 2), (0, 0, 0, 0))
        x = (SPRITE_PX - figure.width) // 2
        y = canvas.height - figure.height - self._bob   # feet on the floor
        canvas.paste(figure, (x, y), figure)
        return canvas

    def _render_panel(self) -> None:
        if self._player is None:
            return
        grid = Table.grid(padding=(0, 2))
        # Pixels doesn't report a width, so pin it (half-block: 1 px per
        # column) or the sprite column swallows the gear text.
        grid.add_column(width=SPRITE_PX, no_wrap=True)
        grid.add_column(ratio=1)
        grid.add_row(
            to_renderable(self._sprite(self._player.player_class)),
            Text.from_markup("\n".join(gear_lines(self._player, self._inventory))),
        )
        self.update(grid)
