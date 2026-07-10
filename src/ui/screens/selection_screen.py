"""
SelectionScreen — full-screen horizontal art-card picker (difficulty, class).

Picking a card calls `on_pick(card)`; the caller (textual_ui) translates that into
the same COMMAND_ENTERED "1"/"2"/"3" the typed flow uses, so the backend never
knows a picker exists. Card art comes from assets/sprites/ui/<art_key>.png via
SpriteStore (auto-placeholder when missing).
"""
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from src.scene.sprite_store import SpriteStore, to_renderable

_CARD_ART_PX = 40


def digit_to_index(key: str, count: int) -> Optional[int]:
    """Map a typed digit "1".."9" to a card index, None if out of range."""
    if not key.isdigit():
        return None
    n = int(key)
    if 1 <= n <= count:
        return n - 1
    return None


@dataclass(frozen=True)
class SelectionCard:
    """One pickable card."""
    command: str      # what gets sent as COMMAND_ENTERED on pick ("1", "2", …)
    title: str
    subtitle: str
    art_key: str      # assets/sprites/ui/<art_key>.png
    accent: str = "white"


class SelectionScreen(ModalScreen):
    """Horizontal card picker: ←/→ or h/l to move, 1-N direct, Enter confirms."""

    BINDINGS = [
        ("left", "prev", "Previous"),
        ("h", "prev", "Previous"),
        ("right", "next", "Next"),
        ("l", "next", "Next"),
        ("enter", "confirm", "Confirm"),
    ] + [(str(n), f"pick_{n}", f"Pick {n}") for n in range(1, 10)]

    CSS = """
    SelectionScreen {
        align: center middle;
        background: $background;  /* opaque: hide the text fallback behind the modal */
    }
    #picker-body {
        width: auto;
        height: auto;
    }
    #picker-heading {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        width: 100%;
    }
    #picker-row {
        width: auto;
        height: auto;
    }
    .picker-card {
        /* Content must fit _CARD_ART_PX-wide pixel art: 1 px = 1 cell across.
           46 = 40 art + 2x2 padding + 2 border, so the shield edge never clips. */
        width: 46;
        height: auto;
        border: round $panel;
        padding: 1 2;
        margin: 0 2;
        content-align: center middle;
        color: $text-muted;
    }
    .picker-card.card-selected {
        border: thick $accent;
        color: $text;
        background: $accent 10%;
    }
    #picker-hint {
        text-align: center;
        color: $text-disabled;
        padding-top: 1;
        width: 100%;
    }
    """

    def __init__(self, heading: str, cards: List[SelectionCard],
                 on_pick: Callable[[SelectionCard], None]):
        super().__init__()
        self._heading = heading
        self._cards = cards
        self._on_pick = on_pick
        self._index = 0
        self._picked = False
        self._store = SpriteStore()
        self._mounted_at = 0.0

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-body"):
            yield Static(self._heading, id="picker-heading")
            with Horizontal(id="picker-row"):
                for i, card in enumerate(self._cards):
                    yield Static(self._card_body(card), classes="picker-card", id=f"picker-card-{i}")
            yield Static(
                f"←/→ choose · Enter confirm · 1-{len(self._cards)} direct",
                id="picker-hint",
            )

    _CONFIRM_GRACE_SECONDS = 0.25  # swallow key events leaking from the previous screen

    def on_mount(self) -> None:
        self._mounted_at = time.monotonic()
        self._highlight()

    def _card_body(self, card: SelectionCard) -> Group:
        art = to_renderable(self._store.get_sprite("ui", card.art_key, _CARD_ART_PX, _CARD_ART_PX))
        title = Text(card.title.upper(), style=f"bold {card.accent}", justify="center")
        subtitle = Text(card.subtitle, style="dim", justify="center")
        return Group(art, Text(""), title, subtitle)

    def _highlight(self) -> None:
        for i in range(len(self._cards)):
            widget = self.query_one(f"#picker-card-{i}", Static)
            widget.set_class(i == self._index, "card-selected")

    def _move(self, delta: int) -> None:
        self._index = max(0, min(len(self._cards) - 1, self._index + delta))
        if self.is_mounted:
            self._highlight()

    def _confirm(self) -> None:
        if self._picked:
            return  # double-Enter guard; caller pops the screen on state change
        if self._mounted_at and time.monotonic() - self._mounted_at < self._CONFIRM_GRACE_SECONDS:
            return  # the Enter that OPENED this screen must not also answer it
        self._picked = True
        self._on_pick(self._cards[self._index])

    # -- actions ---------------------------------------------------------------

    def action_prev(self) -> None:
        self._move(-1)

    def action_next(self) -> None:
        self._move(1)

    def action_confirm(self) -> None:
        self._confirm()

    def __getattr__(self, name: str):
        # action_pick_1 .. action_pick_9 without nine copy-paste methods
        if name.startswith("action_pick_"):
            idx = digit_to_index(name.rsplit("_", 1)[1], len(self._cards))
            if idx is None:
                return lambda: None

            def _pick():
                self._index = idx
                if self.is_mounted:
                    self._highlight()
                self._confirm()
            return _pick
        raise AttributeError(name)
