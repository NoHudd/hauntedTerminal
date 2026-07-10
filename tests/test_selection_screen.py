"""SelectionScreen: card model + pure key-mapping helpers."""
from src.ui.screens.selection_screen import SelectionCard, SelectionScreen, digit_to_index


def _cards():
    return [
        SelectionCard(command="1", title="Easy", subtitle="forgiving", art_key="difficulty_easy"),
        SelectionCard(
            command="2", title="Medium", subtitle="intended", art_key="difficulty_medium"
        ),
        SelectionCard(command="3", title="Hard", subtitle="punishing", art_key="difficulty_hard"),
    ]


def test_digit_to_index_valid_and_bounds():
    assert digit_to_index("1", 3) == 0
    assert digit_to_index("3", 3) == 2
    assert digit_to_index("4", 3) is None   # out of range
    assert digit_to_index("0", 3) is None
    assert digit_to_index("x", 3) is None


def test_card_defaults():
    c = _cards()[0]
    assert c.accent == "white"
    assert c.command == "1"


def test_screen_instantiates_and_tracks_selection():
    picked = []
    screen = SelectionScreen("Choose difficulty", _cards(), on_pick=picked.append)
    assert screen._index == 0
    screen._move(1)
    assert screen._index == 1
    screen._move(-1)
    screen._move(-1)          # clamped at 0
    assert screen._index == 0
    screen._move(1)
    screen._move(1)
    screen._move(1)           # clamped at last
    assert screen._index == 2
