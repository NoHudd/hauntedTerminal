"""SpriteStore: PNG resolution, placeholder fallback, caching."""
from pathlib import Path

from PIL import Image

from src.scene.sprite_store import SpriteStore, to_renderable


def _make_store(tmp_path: Path) -> SpriteStore:
    for sub in ("classes", "enemies", "npcs", "ui"):
        (tmp_path / sub).mkdir()
    return SpriteStore(assets_root=tmp_path)


def test_loads_existing_png(tmp_path):
    store = _make_store(tmp_path)  # creates the kind dirs first
    img = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
    img.save(tmp_path / "enemies" / "corrupt_process.bin.png")
    sprite = store.get_sprite("enemies", "corrupt_process.bin", 24, 24)
    assert sprite.size[0] <= 24 and sprite.size[1] <= 24
    assert store.has_art("enemies", "corrupt_process.bin")


def test_missing_png_returns_placeholder(tmp_path):
    store = _make_store(tmp_path)
    sprite = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    assert sprite.size == (24, 24)
    assert not store.has_art("enemies", "ghost.tmp")


def test_placeholder_deterministic_and_distinct(tmp_path):
    store = _make_store(tmp_path)
    a1 = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    a2 = SpriteStore(assets_root=tmp_path).get_sprite("enemies", "ghost.tmp", 24, 24)
    b = store.get_sprite("enemies", "other.bin", 24, 24)
    assert list(a1.getdata()) == list(a2.getdata())      # same id → same pixels
    assert list(a1.getdata()) != list(b.getdata())        # different id → different tint


def test_oversized_png_is_scaled_down(tmp_path):
    store = _make_store(tmp_path)  # creates the kind dirs first
    Image.new("RGBA", (64, 32), (0, 0, 255, 255)).save(tmp_path / "npcs" / "oracle.db.png")
    sprite = store.get_sprite("npcs", "oracle.db", 20, 20)
    assert sprite.size == (20, 10)  # aspect kept, fits box


def test_cache_returns_same_object(tmp_path):
    store = _make_store(tmp_path)
    s1 = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    s2 = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    assert s1 is s2


def test_to_renderable_produces_pixels(tmp_path):
    store = _make_store(tmp_path)
    sprite = store.get_sprite("enemies", "ghost.tmp", 8, 8)
    from rich_pixels import Pixels
    assert isinstance(to_renderable(sprite), Pixels)


def _make_backdrop_store(tmp_path):
    (tmp_path / "backdrops" / "rooms").mkdir(parents=True)
    return SpriteStore(assets_root=tmp_path)


def test_backdrop_room_override_beats_zone(tmp_path):
    store = _make_backdrop_store(tmp_path)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(tmp_path / "backdrops" / "dangerous.png")
    Image.new("RGBA", (10, 10), (0, 0, 255, 255)).save(tmp_path / "backdrops" / "rooms" / "var_dungeon.png")
    bd = store.get_backdrop("var_dungeon", "dangerous", 40, 20)
    assert bd.size == (40, 20)
    assert bd.getpixel((20, 10))[2] > bd.getpixel((20, 10))[0]  # blue (room) won


def test_backdrop_zone_fallback(tmp_path):
    store = _make_backdrop_store(tmp_path)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(tmp_path / "backdrops" / "dangerous.png")
    bd = store.get_backdrop("no_such_room", "dangerous", 40, 20)
    assert bd.getpixel((20, 10))[0] == 255  # red (zone) used


def test_backdrop_generated_when_no_art(tmp_path):
    store = _make_backdrop_store(tmp_path)
    bd = store.get_backdrop("mystery", "quantum", 40, 20)
    assert bd.size == (40, 20)
    # deterministic per zone
    bd2 = SpriteStore(assets_root=tmp_path).get_backdrop("mystery", "quantum", 40, 20)
    assert list(bd.getdata()) == list(bd2.getdata())
