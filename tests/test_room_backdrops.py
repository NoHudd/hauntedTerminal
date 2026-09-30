"""Per-room backdrop art: every file names a real room and is backdrop-sized."""
from pathlib import Path

import pytest
from PIL import Image

from src.scene.sprite_store import SpriteStore

ROOM_ART = sorted(Path("assets/sprites/backdrops/rooms").glob("*.png"))
ROOM_IDS = {p.stem for p in Path("data/rooms").glob("*.yml")}


def test_there_is_room_art() -> None:
    assert ROOM_ART


@pytest.mark.parametrize("path", ROOM_ART, ids=lambda p: p.stem)
def test_room_art_names_a_room_and_is_backdrop_sized(path: Path) -> None:
    # A typo'd file name would silently fall back to the zone backdrop.
    assert path.stem in ROOM_IDS
    assert Image.open(path).size == (100, 36)


def test_room_art_wins_over_the_zone_backdrop() -> None:
    store = SpriteStore()
    room = store.get_backdrop("usr_lib_arcane", "ancient", 100, 36)
    zone = store.get_backdrop("no_such_room", "ancient", 100, 36)
    assert room.tobytes() != zone.tobytes()
