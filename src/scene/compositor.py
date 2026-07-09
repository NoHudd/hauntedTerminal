"""
Compositor — pure functions that assemble the scene image.

Takes PIL images (from SpriteStore) and merges them onto a backdrop with alpha.
NPCs occupy the left half, enemies the right half, up to 3 each, bottom-aligned.
Returns the merged image plus a Rich-markup caption line. No Textual imports.
"""
from dataclasses import dataclass

from PIL import Image

MAX_PER_SIDE = 3
_FLOOR_MARGIN = 1  # px above the bottom edge


@dataclass(frozen=True)
class Placed:
    """One entity ready for placement."""
    image: Image.Image
    name: str
    kind: str  # "npc" | "enemy"


def _slot_xs(half_start: int, half_width: int, count: int) -> list[int]:
    """Center-points for `count` sprites evenly spread across one half."""
    step = half_width // (count + 1)
    return [half_start + step * (i + 1) for i in range(count)]


def compose_explore(backdrop: Image.Image, entities: list[Placed]) -> tuple[Image.Image, str]:
    img = backdrop.copy()
    w, h = img.size

    npcs = [e for e in entities if e.kind == "npc"][:MAX_PER_SIDE]
    enemies = [e for e in entities if e.kind == "enemy"][:MAX_PER_SIDE]
    overflow = len(entities) - len(npcs) - len(enemies)

    for group, half_start in ((npcs, 0), (enemies, w // 2)):
        xs = _slot_xs(half_start, w // 2, len(group))
        for placed, cx in zip(group, xs):
            sw, sh = placed.image.size
            x = max(0, min(w - sw, cx - sw // 2))
            y = max(0, h - sh - _FLOOR_MARGIN)
            img.paste(placed.image, (x, y), placed.image)

    chips = [f"[bold magenta]👤 {e.name}[/bold magenta]" for e in npcs]
    chips += [f"[bold red]💀 {e.name}[/bold red]" for e in enemies]
    if overflow > 0:
        chips.append(f"[dim]+{overflow} more[/dim]")
    caption = "   ".join(chips)
    return img, caption
