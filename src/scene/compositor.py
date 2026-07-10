"""
Compositor — pure functions that assemble the scene image.

Takes PIL images (from SpriteStore) and merges them onto a backdrop with alpha.
NPCs occupy the left half, enemies the right half, up to 3 each, bottom-aligned.
Returns the merged image plus a Rich-markup caption line. No Textual imports.
"""
from dataclasses import dataclass

from PIL import Image

from src.scene.effects import FxState

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


# --- battle mode -------------------------------------------------------------

_BATTLE_MARGIN = 2  # px from the arena edges


def whiten(img: Image.Image) -> Image.Image:
    """White-flash version of a sprite; transparent pixels stay transparent."""
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    out = Image.blend(img.convert("RGBA"), white, 0.8)
    out.putalpha(img.getchannel("A"))
    return out


def compose_battle(
    backdrop: Image.Image,
    player_img: Image.Image,
    enemy_img: Image.Image,
    fx: FxState,
) -> Image.Image:
    """Pokemon framing: enemy top-right, player bottom-left. dx moves toward opponent."""
    img = backdrop.copy()
    w, h = img.size

    enemy = whiten(enemy_img) if fx.enemy_flash else enemy_img
    player = whiten(player_img) if fx.player_flash else player_img

    ew, eh = enemy.size
    ex = max(0, w - ew - _BATTLE_MARGIN - fx.enemy_dx)   # enemy lunges LEFT
    ey = max(0, _BATTLE_MARGIN + fx.enemy_dy)            # bob: enemy drifts down
    img.paste(enemy, (ex, ey), enemy)

    pw, ph = player.size
    px_ = min(w - pw, _BATTLE_MARGIN + fx.player_dx)     # player lunges RIGHT
    py = max(0, h - ph - _BATTLE_MARGIN - fx.player_dy)  # bob: player lifts up
    img.paste(player, (px_, py), player)
    return img


def hp_bar(hp: int, max_hp: int, width: int = 12) -> str:
    """Rich-markup HP bar, colored by remaining fraction."""
    max_hp = max(1, max_hp)
    hp = max(0, min(hp, max_hp))
    frac = hp / max_hp
    filled = round(width * frac)
    color = "green" if frac > 0.5 else ("yellow" if frac > 0.25 else "red")
    return f"[{color}]{'▉' * filled}[/{color}][dim]{'░' * (width - filled)}[/dim]"


def nameplate(name: str, hp: int, max_hp: int, icon: str = "", pop: str = "") -> str:
    """One-line fighter nameplate for above/below the arena image."""
    lead = f"{icon} " if icon else ""
    tail = f"  {pop}" if pop else ""
    return f"[bold]{lead}{name.upper()}[/bold]  HP {hp}/{max_hp} {hp_bar(hp, max_hp)}{tail}"
