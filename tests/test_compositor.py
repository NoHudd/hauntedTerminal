"""Compositor: pure image assembly for the explore scene."""
from PIL import Image

from src.scene.compositor import Placed, compose_explore


def _sprite(color):
    return Image.new("RGBA", (10, 10), color)


def _backdrop():
    return Image.new("RGBA", (100, 30), (5, 5, 5, 255))


def test_empty_room_returns_backdrop_and_no_caption():
    bd = _backdrop()
    img, caption = compose_explore(bd, [])
    assert img.size == bd.size
    assert caption == ""


def test_npc_left_enemy_right():
    npc = Placed(_sprite((0, 255, 0, 255)), "Oracle", "npc")
    enemy = Placed(_sprite((255, 0, 0, 255)), "Daemon", "enemy")
    img, caption = compose_explore(_backdrop(), [npc, enemy])
    # green pixels only in left half, red only in right half (bottom rows)
    left = img.crop((0, 20, 50, 30))
    right = img.crop((50, 20, 100, 30))
    assert any(p[1] == 255 for p in left.getdata())
    assert not any(p[0] == 255 and p[1] == 0 for p in left.getdata())
    assert any(p[0] == 255 and p[1] == 0 for p in right.getdata())


def test_caption_names_all_entities():
    entities = [
        Placed(_sprite((0, 255, 0, 255)), "Oracle", "npc"),
        Placed(_sprite((255, 0, 0, 255)), "Daemon", "enemy"),
    ]
    _, caption = compose_explore(_backdrop(), entities)
    assert "Oracle" in caption and "Daemon" in caption


def test_caps_at_three_per_side():
    enemies = [Placed(_sprite((255, 0, 0, 255)), f"E{i}", "enemy") for i in range(5)]
    _, caption = compose_explore(_backdrop(), enemies)
    assert caption.count("E") == 3 or "+2" in caption  # 3 drawn, overflow noted
