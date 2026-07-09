"""
LogViewerScreen — dev-tools modal for viewing debug logs in real-time.
"""

import os

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import RichLog

LOG_CATEGORIES = ["combat", "command", "item", "room", "player", "world", "system"]


def line_passes(line: str, level_filter: int, category_filter) -> bool:
    """Whether a log line survives the active filters.

    level_filter: 0=all, 1=warnings+errors, 2=errors-only.
    category_filter: None=all, else keep only lines tagged [CATEGORY].
    """
    if level_filter == 2 and "- ERROR -" not in line:
        return False
    if level_filter == 1 and "- ERROR -" not in line and "- WARNING -" not in line:
        return False
    if category_filter and f"[{category_filter.upper()}]" not in line:
        return False
    return True


class LogViewerScreen(ModalScreen):
    """Modal overlay for viewing debug logs in real-time."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
        ("j", "scroll_down", "Scroll Down"),
        ("k", "scroll_up", "Scroll Up"),
        ("h", "scroll_left", "Scroll Left"),
        ("l", "scroll_right", "Scroll Right"),
        ("g", "scroll_home", "Go to Top"),
        ("G", "scroll_end", "Go to Bottom"),
        ("d", "page_down", "Page Down"),
        ("u", "page_up", "Page Up"),
        ("f", "cycle_level", "Level Filter"),
        ("c", "cycle_category", "Category Filter"),
    ]

    _LEVEL_NAMES = ["all", "warn+err", "err-only"]

    _HINTS = (
        "f level · c category · g/G top/bottom · j/k scroll · u/d page · q close"
    )

    def __init__(self):
        super().__init__()
        self._log_position = 0
        self._refresh_timer = None
        self._level_filter: int = 0
        self._category_filter = None

    def compose(self) -> ComposeResult:
        """Create log viewer UI."""
        yield RichLog(highlight=True, markup=True, id="log-display", max_lines=5000)

    def _colorize_log_line(self, line: str) -> str:
        """Return the line wrapped in Rich markup based on content."""
        # Level detection takes priority
        if "- ERROR -" in line:
            return f"[bold red]{line}[/bold red]"
        if "- WARNING -" in line:
            return f"[yellow]{line}[/yellow]"
        if "- INFO -" in line:
            return line
        if "- DEBUG -" in line:
            return f"[dim]{line}[/dim]"

        # Category detection
        if "[COMBAT]" in line:
            return f"[red]{line}[/red]"
        if "[COMMAND]" in line:
            return f"[cyan]{line}[/cyan]"
        if "[ITEM]" in line:
            return f"[green]{line}[/green]"
        if "[ROOM]" in line:
            return f"[blue]{line}[/blue]"
        if "[PLAYER]" in line:
            return f"[magenta]{line}[/magenta]"
        if "[WORLD]" in line:
            return f"[dim cyan]{line}[/dim cyan]"
        if "[SYSTEM]" in line:
            return f"[dim]{line}[/dim]"

        return line

    def on_mount(self) -> None:
        """Initialize log viewer when mounted."""
        from config.dev_config import DEBUG_LOG_FILE

        self.log_file = DEBUG_LOG_FILE
        log_widget = self.query_one("#log-display", RichLog)
        log_widget.border_title = "Logs — level: all · category: all"
        log_widget.border_subtitle = self._HINTS

        # Load last 100 lines from log file
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    # Load the ENTIRE current session (debug.log is cleared each run),
                    # so the viewer can scroll all the way back to the start.
                    for line in f.readlines():
                        stripped = line.rstrip()
                        if not line_passes(stripped, self._level_filter, self._category_filter):
                            continue
                        log_widget.write(self._colorize_log_line(stripped))

                    f.seek(0, 2)  # Seek to end
                    self._log_position = f.tell()
            else:
                log_widget.write(
                    "[yellow]Debug log file not found. Logs will appear here when generated.[/yellow]"
                )
        except Exception as e:
            log_widget.write(f"[red]Error loading log file: {e}[/red]")

        # Auto-refresh every 500 ms
        self._refresh_timer = self.set_interval(0.5, self._refresh_log)

    def _refresh_log(self) -> None:
        """Refresh log content with new lines."""
        try:
            if not os.path.exists(self.log_file):
                return

            log_widget = self.query_one("#log-display", RichLog)

            with open(self.log_file, 'r') as f:
                f.seek(self._log_position)
                new_lines = f.readlines()

                for line in new_lines:
                    stripped = line.rstrip()
                    if not line_passes(stripped, self._level_filter, self._category_filter):
                        continue
                    log_widget.write(self._colorize_log_line(stripped))

                self._log_position = f.tell()

        except Exception:
            pass

    def _full_refresh_log(self) -> None:
        """Reload the entire log, applying current filters, and update the title."""
        try:
            log_widget = self.query_one("#log-display", RichLog)
            log_widget.clear()
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    for line in f.readlines():
                        stripped = line.rstrip()
                        if not line_passes(stripped, self._level_filter, self._category_filter):
                            continue
                        log_widget.write(self._colorize_log_line(stripped))
                    self._log_position = f.tell()
            lvl = self._LEVEL_NAMES[self._level_filter]
            cat = self._category_filter or "all"
            log_widget.border_title = f"Logs — level: {lvl} · category: {cat}"
        except Exception:
            pass

    def action_cycle_level(self) -> None:
        """Cycle level filter: all → warnings+errors → errors-only."""
        self._level_filter = (self._level_filter + 1) % 3
        self._full_refresh_log()

    def action_cycle_category(self) -> None:
        """Cycle category focus: all → each category → all."""
        cats = [None] + LOG_CATEGORIES
        i = cats.index(self._category_filter)
        self._category_filter = cats[(i + 1) % len(cats)]
        self._full_refresh_log()

    def action_dismiss(self) -> None:
        """Close the log viewer."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        self.app.pop_screen()

    def action_scroll_down(self) -> None:
        """Scroll down one line (vim: j)."""
        self.query_one("#log-display", RichLog).scroll_relative(y=1, animate=False)

    def action_scroll_up(self) -> None:
        """Scroll up one line (vim: k)."""
        self.query_one("#log-display", RichLog).scroll_relative(y=-1, animate=False)

    def action_scroll_left(self) -> None:
        """Scroll left (vim: h)."""
        self.query_one("#log-display", RichLog).scroll_relative(x=-2, animate=False)

    def action_scroll_right(self) -> None:
        """Scroll right (vim: l)."""
        self.query_one("#log-display", RichLog).scroll_relative(x=2, animate=False)

    def action_scroll_home(self) -> None:
        """Scroll to top (vim: g)."""
        self.query_one("#log-display", RichLog).scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        """Scroll to bottom (vim: G)."""
        self.query_one("#log-display", RichLog).scroll_end(animate=False)

    def action_page_down(self) -> None:
        """Scroll down one page (vim: ctrl+d)."""
        self.query_one("#log-display", RichLog).scroll_page_down(animate=False)

    def action_page_up(self) -> None:
        """Scroll up one page (vim: ctrl+u)."""
        self.query_one("#log-display", RichLog).scroll_page_up(animate=False)
