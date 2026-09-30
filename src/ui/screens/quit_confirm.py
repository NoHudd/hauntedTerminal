"""
QuitConfirmScreen — the "you have unsaved progress" prompt, as a real chooser.

This used to be three typed letters (y/n/c) buried in a paragraph of output, so
the most consequential decision in the game was also the least legible one. The
modal presents each outcome as a highlighted list: arrow keys to move,
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

Choice = tuple[str, str, str, str]  # (letter the domain expects, label, help line, accent)

LEAVE_CHOICES: list[Choice] = [
    ("m", "Save and main menu", "Write a save file, then go to the title menu.", "cyan"),
    ("y", "Save and quit", "Write a save file, then leave.", "green"),
    ("n", "Quit without saving", "Lose everything since your last save.", "red"),
    ("c", "Keep playing", "Go back to where you were.", "yellow"),
]

MID_FIGHT_CHOICES: list[Choice] = [
    ("c", "Keep fighting", "Back to the fight.", "green"),
    ("x", "Main menu", "Your last autosave is kept; this fight is lost.", "cyan"),
    ("n", "Quit", "Your last autosave is kept; this fight is lost.", "red"),
]


class QuitConfirmScreen(ModalScreen):
    """Arrow-key chooser for leaving a run (or a fight)."""

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "confirm", "Choose", show=False),
        Binding("escape", "cancel", "Back", show=False),
        Binding("m", "pick('m')", show=False),
        Binding("y", "pick('y')", show=False),
        Binding("n", "pick('n')", show=False),
        Binding("x", "pick('x')", show=False),
        Binding("c", "cancel", show=False),
    ]

    def __init__(self, on_choice: Callable[[str], None],
                 choices: list[Choice] = LEAVE_CHOICES,
                 heading: str = "Quit — you have unsaved progress"):
        super().__init__()
        self._on_choice = on_choice
        self._choices = choices
        self._heading = heading
        self._index = 0
        self._answered = False

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-confirm"):
            yield Static(id="quit-confirm-body")

    def on_mount(self) -> None:
        self._draw()

    # -- rendering ------------------------------------------------------------

    def _draw(self) -> None:
        lines = [f"[bold yellow]{self._heading}[/bold yellow]", ""]
        for i, (letter, label, blurb, accent) in enumerate(self._choices):
            if i == self._index:
                lines.append(
                    f"[reverse bold {accent}]  ▶  {letter}  {label}  "
                    f"[/reverse bold {accent}]"
                )
                lines.append(f"        [dim]{blurb}[/dim]")
            else:
                lines.append(f"[dim]     {letter}  {label}[/dim]")
        back = next(label for letter, label, *_ in self._choices if letter == "c")
        lines += ["", f"[dim]↑/↓ choose · ↵ confirm · esc {back.lower()}[/dim]"]
        try:
            self.query_one("#quit-confirm-body", Static).update("\n".join(lines))
        except NoMatches:
            # Not mounted yet (or under unit test): on_mount draws again.
            pass

    # -- actions --------------------------------------------------------------

    def action_move_up(self) -> None:
        self._index = (self._index - 1) % len(self._choices)
        self._draw()

    def action_move_down(self) -> None:
        self._index = (self._index + 1) % len(self._choices)
        self._draw()

    def action_confirm(self) -> None:
        self._choose(self._choices[self._index][0])

    def action_pick(self, letter: str) -> None:
        if any(choice[0] == letter for choice in self._choices):
            self._choose(letter)

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
