"""The opening story tells a new player the hunt exists and how /boot opens."""
import inspect

from rich.markup import render

from src.ui import title_menu


def _story() -> str:
    source = inspect.getsource(title_menu)
    start = source.index("opening_story = '''") + len("opening_story = '''")
    return source[start:source.index("'''", start)]


def test_prologue_introduces_the_hunt() -> None:
    story = _story()
    plain = render(story).plain
    assert "flag" in plain.lower()
    assert "/boot" in plain
    assert len(plain.strip().splitlines()) <= 30
