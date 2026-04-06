"""
LogViewerScreen — dev-tools modal for viewing debug logs in real-time.
"""

import os

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import RichLog


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
        ("f", "toggle_filter", "Filter Warnings"),
    ]

    def __init__(self):
        super().__init__()
        self._log_position = 0
        self._refresh_timer = None
        self._filter_active: bool = False

    def compose(self) -> ComposeResult:
        """Create log viewer UI."""
        yield RichLog(highlight=True, markup=True, id="log-display", max_lines=500)

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

        # Load last 100 lines from log file
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                    for line in recent_lines:
                        stripped = line.rstrip()
                        if self._filter_active and '- ERROR -' not in stripped and '- WARNING -' not in stripped:
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
                    if self._filter_active and '- ERROR -' not in stripped and '- WARNING -' not in stripped:
                        continue
                    log_widget.write(self._colorize_log_line(stripped))

                self._log_position = f.tell()

        except Exception:
            pass

    def _full_refresh_log(self) -> None:
        """Reload the entire log, applying current filter."""
        try:
            log_widget = self.query_one("#log-display", RichLog)
            log_widget.clear()
            if not os.path.exists(self.log_file):
                return
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    stripped = line.rstrip()
                    if self._filter_active and '- ERROR -' not in stripped and '- WARNING -' not in stripped:
                        continue
                    log_widget.write(self._colorize_log_line(stripped))
                self._log_position = f.tell()
        except Exception:
            pass

    def action_toggle_filter(self) -> None:
        """Toggle to show only WARNING/ERROR lines."""
        self._filter_active = not self._filter_active
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
