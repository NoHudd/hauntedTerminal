"""
SpriteStore — resolves entity ids to PIL images.

Convention: assets/sprites/<kind>/<entity_id>.png. Missing art falls back to a
deterministic generated placeholder (tinted block + initial) so every entity
renders from day one. Pure PIL — no Textual imports (headless-testable).
"""
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw
from rich_pixels import HalfcellRenderer, Pixels

_PLACEHOLDER_ALPHA = 230


def to_renderable(img: Image.Image) -> Pixels:
    """Convert a PIL image to a Rich renderable (2 px per terminal cell)."""
    return Pixels.from_image(img, renderer=HalfcellRenderer())


def _placeholder_color(entity_id: str) -> tuple[int, int, int]:
    """Deterministic mid-brightness tint from the id hash."""
    digest = hashlib.md5(entity_id.encode()).digest()
    # Keep channels in 60..200 so it's visible on dark and light themes
    return tuple(60 + (b % 141) for b in digest[:3])


def _make_placeholder(entity_id: str, w: int, h: int) -> Image.Image:
    color = _placeholder_color(entity_id)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled block with a 1px darker border — obvious "art goes here"
    dark = tuple(max(0, c - 50) for c in color)
    draw.rectangle([1, 1, w - 2, h - 2], fill=(*color, _PLACEHOLDER_ALPHA), outline=(*dark, 255))
    initial = (entity_id[:1] or "?").upper()
    draw.text((w // 2 - 3, h // 2 - 5), initial, fill=(*dark, 255))
    return img


class SpriteStore:
    """Loads and caches sprites; generates placeholders for missing art."""

    def __init__(self, assets_root: Path = Path("assets/sprites")):
        self._root = Path(assets_root)
        self._cache: dict[tuple, Image.Image] = {}

    def _png_path(self, kind: str, entity_id: str) -> Path:
        return self._root / kind / f"{entity_id}.png"

    def has_art(self, kind: str, entity_id: str) -> bool:
        return self._png_path(kind, entity_id).is_file()

    def get_sprite(self, kind: str, entity_id: str, max_w: int, max_h: int) -> Image.Image:
        key = (kind, entity_id, max_w, max_h)
        if key in self._cache:
            return self._cache[key]

        path = self._png_path(kind, entity_id)
        if path.is_file():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_w, max_h), Image.NEAREST)  # pixel art: no smoothing
        else:
            img = _make_placeholder(entity_id, max_w, max_h)

        self._cache[key] = img
        return img

    def get_backdrop(self, room_id: str, zone: str, w: int, h: int) -> Image.Image:
        key = ("backdrop", room_id, zone, w, h)
        if key in self._cache:
            return self._cache[key]

        room_png = self._root / "backdrops" / "rooms" / f"{room_id}.png"
        zone_png = self._root / "backdrops" / f"{zone}.png"
        if room_png.is_file():
            img = Image.open(room_png).convert("RGBA").resize((w, h), Image.NEAREST)
        elif zone_png.is_file():
            img = Image.open(zone_png).convert("RGBA").resize((w, h), Image.NEAREST)
        else:
            img = self._generated_backdrop(zone, w, h)

        self._cache[key] = img
        return img

    @staticmethod
    def _generated_backdrop(zone: str, w: int, h: int) -> Image.Image:
        """Dim vertical gradient tinted by zone hash — dark enough to sit behind sprites."""
        base = _placeholder_color(f"zone:{zone}")
        img = Image.new("RGBA", (w, h))
        px = img.load()
        for y in range(h):
            fade = 0.25 + 0.35 * (y / max(1, h - 1))   # darker sky, lighter floor
            row = tuple(int(c * fade) for c in base)
            for x in range(w):
                px[x, y] = (*row, 255)
        return img
