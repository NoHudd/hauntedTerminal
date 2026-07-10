"""Compositor battle mode: placement, flash tint, HP bars, nameplates."""
from PIL import Image

from src.scene.compositor import compose_battle, hp_bar, nameplate, whiten
from src.scene.effects import FxState


def _backdrop():
    return Image.new("RGBA", (100, 40), (5, 5, 5, 255))


def _sprite(color):
    return Image.new("RGBA", (10, 10), color)


def test_enemy_top_right_player_bottom_left():
    img = compose_battle(
        _backdrop(), _sprite((0, 255, 0, 255)), _sprite((255, 0, 0, 255)), FxState()
    )
    # red (enemy) somewhere in the top-right quadrant
    tr = img.crop((50, 0, 100, 20))
    assert any(p[0] == 255 and p[1] == 0 for p in tr.getdata())
    # green (player) somewhere in the bottom-left quadrant
    bl = img.crop((0, 20, 50, 40))
    assert any(p[1] == 255 and p[0] == 0 for p in bl.getdata())


def test_lunge_moves_player_right():
    player, enemy = _sprite((0, 255, 0, 255)), _sprite((255, 0, 0, 255))
    still = compose_battle(_backdrop(), player, enemy, FxState())
    lunged = compose_battle(_backdrop(), player, enemy, FxState(player_dx=6))

    def leftmost_green(im):
        px = list(im.getdata())
        w = im.size[0]
        return min(i % w for i, p in enumerate(px) if p[1] == 255 and p[0] == 0)

    assert leftmost_green(lunged) == leftmost_green(still) + 6


def test_flash_whitens_enemy():
    flashed = compose_battle(
        _backdrop(), _sprite((0, 255, 0, 255)), _sprite((120, 0, 0, 255)), FxState(enemy_flash=True)
    )
    tr = flashed.crop((50, 0, 100, 20))
    assert any(p[0] > 200 and p[1] > 200 and p[2] > 200 for p in tr.getdata())


def test_whiten_preserves_alpha():
    img = Image.new("RGBA", (4, 4), (10, 10, 10, 0))  # fully transparent
    assert all(p[3] == 0 for p in whiten(img).getdata())


def test_hp_bar_proportions_and_color():
    full = hp_bar(100, 100, width=10)
    assert full.count("▉") == 10 and "green" in full
    half = hp_bar(50, 100, width=10)
    assert half.count("▉") == 5
    low = hp_bar(10, 100, width=10)
    assert "red" in low
    assert hp_bar(-5, 100, width=10).count("▉") == 0   # clamped


def test_nameplate_contains_everything():
    line = nameplate("daemon.exe", 34, 50, icon="💀", pop="[red]-12![/red]")
    assert "DAEMON.EXE" in line and "34/50" in line and "-12!" in line and "💀" in line
