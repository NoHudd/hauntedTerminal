"""The command box: Tab finishes the ghost-text suggestion, like a shell."""
from __future__ import annotations

from typing import Callable

from textual.binding import Binding
from textual.widgets import Input


class CommandInput(Input):
    """Input whose Tab accepts the inline suggestion when there is one.

    With nothing to complete — or while `can_complete()` says no (in combat) —
    Tab moves focus exactly as before. Combat Selection Mode and the
    Tab-then-L log shortcut both depend on that fallback.
    """

    BINDINGS = [Binding("tab", "complete_or_leave", show=False)]

    can_complete: Callable[[], bool] = staticmethod(lambda: True)

    def action_complete_or_leave(self) -> None:
        # `_suggestion` is Textual's private ghost-text state (checked on 8.2.8);
        # right-arrow is the built-in way to accept it.
        suggestion = self._suggestion
        if (
            self.can_complete()
            and self.cursor_at_end
            and len(suggestion) > len(self.value)
        ):
            self.action_cursor_right()
            return
        self.app.action_focus_next()
