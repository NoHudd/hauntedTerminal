"""
QuitConfirmScreen — the "you have unsaved progress" prompt, as a real chooser.

This used to be three typed letters (y/n/c) buried in a paragraph of output, so
the most consequential decision in the game was also the least legible one. The
modal presents the three outcomes as a highlighted list: arrow keys to move,
Enter to confirm, ESC to back out. The letters still work for anyone who learned
them.

The screen decides nothing. It reports the chosen letter to its callback, which
feeds the domain's existing quit-confirmation flow unchanged.
"""
from collections.abc import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Static

# (letter the domain expects, label, help line, accent)
CHOICES: list[tuple[str, str, str, str]] = [
    ("y", "Save and quit", "Write a save file, then leave.", "green"),
    ("n", "Quit without saving", "Lose everything since your last save.", "red"),
    ("c", "Keep playing", "Go back to where you were.", "cyan"),
]


class QuitConfirmScreen(ModalScreen):
    """Arrow-key confirmation for quitting with unsaved progress."""

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "confirm", "Choose", show=False),
        Binding("escape", "cancel", "Keep playing", show=False),
        Binding("y", "pick_save", "Save and quit", show=False),
        Binding("n", "pick_quit", "Quit", show=False),
        Binding("c", "cancel", "Keep playing", show=False),
    ]

    def __init__(self, on_choice: Callable[[str], None]):
        super().__init__()
        self._on_choice = on_choice
        self._index = 0
        self._answered = False

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-confirm"):
            yield Static(id="quit-confirm-body")

    def on_mount(self) -> None:
        self._draw()

    # -- rendering ------------------------------------------------------------

    def _draw(self) -> None:
        lines = [
            "[bold yellow]Quit — you have unsaved progress[/bold yellow]",
            "",
        ]
        for i, (letter, label, blurb, accent) in enumerate(CHOICES):
            if i == self._index:
                lines.append(
                    f"[reverse bold {accent}]  ▶  {letter}  {label}  "
                    f"[/reverse bold {accent}]"
                )
                lines.append(f"        [dim]{blurb}[/dim]")
            else:
                lines.append(f"[dim]     {letter}  {label}[/dim]")
        lines += [
            "",
            "[dim]↑/↓ choose · ↵ confirm · esc keep playing[/dim]",
        ]
        try:
            self.query_one("#quit-confirm-body", Static).update("\n".join(lines))
        except NoMatches:
            # Not mounted yet (or under unit test): on_mount draws again.
            pass

    # -- actions --------------------------------------------------------------

    def action_move_up(self) -> None:
        self._index = (self._index - 1) % len(CHOICES)
        self._draw()

    def action_move_down(self) -> None:
        self._index = (self._index + 1) % len(CHOICES)
        self._draw()

    def action_confirm(self) -> None:
        self._choose(CHOICES[self._index][0])

    def action_pick_save(self) -> None:
        self._choose("y")

    def action_pick_quit(self) -> None:
        self._choose("n")

    def action_cancel(self) -> None:
        self._choose("c")

    def _choose(self, letter: str) -> None:
        # Guard against a double answer: dismissing is async, so a second key
        # press before the screen pops would otherwise send a second command
        # into a flow that is no longer expecting one.
        if self._answered:
            return
        self._answered = True
        self.dismiss()
        self._on_choice(letter)
