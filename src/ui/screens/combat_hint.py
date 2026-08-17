"""
CombatModeHintScreen — modal popup to help players understand combat input modes.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static


class CombatModeHintScreen(ModalScreen):
    """Modal popup to help players understand combat input modes."""

    BINDINGS = [
        ("enter", "dismiss", "Continue"),
        ("1", "dismiss", "Attack 1"),
        ("2", "dismiss", "Attack 2"),
        ("3", "dismiss", "Attack 3"),
        ("4", "dismiss", "Attack 4"),
        ("5", "dismiss", "Attack 5"),
        ("6", "dismiss", "Attack 6"),
        ("7", "dismiss", "Attack 7"),
        ("8", "dismiss", "Attack 8"),
        ("9", "dismiss", "Attack 9"),
    ]

    def compose(self) -> ComposeResult:
        """Create the hint modal UI."""
        yield Static(id="combat-hint-content")

    def on_mount(self) -> None:
        """Set up the hint content."""
        hint_content = """
[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]
[bold yellow]                    ⚔  SELECTION MODE  ⚔[/bold yellow]
[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]

[white]Combat opens in [bold]Selection Mode[/bold] automatically.[/white]

[bold green]To attack:[/bold green]
  • Press [bold cyan]1-9[/bold cyan] for a quick attack

[bold green]To flee:[/bold green]
  • Press [bold cyan]0[/bold cyan]

[bold green]To use an item instead:[/bold green]
  • Press [bold cyan]TAB[/bold cyan] to type [bold]use [item][/bold], then
    [bold cyan]TAB[/bold cyan] again to return to Selection Mode

[dim]────────────────────────────────────────────────────────────────[/dim]
[dim italic]Press ENTER or a number key to continue...[/dim italic]
"""
        self.query_one("#combat-hint-content").update(hint_content)
