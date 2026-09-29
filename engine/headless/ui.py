"""Headless UI adapter.

Implements the surface the domain actually calls on ``self.ui`` (see
src/ui/ui_interface.py UIProtocol, plus the few extras used in practice) but,
instead of rendering, records every output line into a buffer. This lets the
engine run and be driven with no Textual App and no terminal — the prerequisite
for automated engine tests and scripted playthroughs.

Strangler note: this captures output at the existing ``update_output`` seam
rather than rewriting the ~160 call sites. The later Result-object migration
(Phase 2b) can replace this without changing tests, which assert on drained text.

Deliberately omits ``call_from_thread``: the one caller (command_handler.py)
``hasattr``-guards it and falls back to a plain ``update_output`` when absent, so
output still flows through the buffer.
"""
from __future__ import annotations

from typing import Any


class HeadlessUI:
    """A UIProtocol-compatible sink that records output instead of rendering."""

    def __init__(self) -> None:
        self.output_log: list[str] = []
        # Set when the domain asks to quit; tests assert on it instead of the
        # process exiting.
        self.quit_requested = False
        # Every tutorial hint shown, in order, so tests can assert which step
        # fired without depending on its wording.
        self.hints: list[dict[str, Any]] = []
        # Back-refs the engine assigns via _bind_ui_refs; unused here but must
        # be assignable.
        self._player_ref: object | None = None
        self._world_ref: object | None = None
        self._room_aliases_ref: object | None = None
        # The finale is delivered by event (the TUI performs it; headless just
        # records the text so tests/sim can assert on the ending). The bus
        # arrives from the engine via attach_bus.
        self.bus: Any = None

    def attach_bus(self, bus: Any, state_manager: Any) -> None:
        from src.events import EventType
        self.shutdown()
        self.bus = bus
        self.state_manager = state_manager
        bus.subscribe(EventType.GAME_WON, self._on_game_won)
        bus.subscribe(EventType.GAME_QUIT, self._on_game_quit)
        bus.subscribe(EventType.TUTORIAL_HINT, self._on_tutorial_hint)

    def _on_tutorial_hint(self, event: Any) -> None:
        data = getattr(event, "data", None) or {}
        self.hints.append(data)
        self.output_log.append(str(data.get("text", "")))

    def _on_game_quit(self, event: Any) -> None:
        self.quit_requested = True
        self.output_log.append("[quit]")

    def _on_game_won(self, event: Any) -> None:
        data = getattr(event, "data", None) or {}
        self.output_log.append("\n\n".join(data.get("sections", [])))
        self.output_log.append(f"[stats] {data.get('stats', {})}")

    # --- output capture -----------------------------------------------------

    def update_output(self, content: str) -> None:
        self.output_log.append(str(content))

    def append_output(self, content: str) -> None:
        self.output_log.append(str(content))

    def update_output_renderable(self, renderable: object) -> None:
        self.output_log.append(str(renderable))

    def display_message(self, message: str) -> None:
        self.output_log.append(str(message))

    def clear_console(self) -> None:
        self.output_log.clear()

    # --- buffer access for drivers/tests ------------------------------------

    def drain(self) -> list[str]:
        """Return output recorded since the last drain, then clear it."""
        lines = self.output_log[:]
        self.output_log.clear()
        return lines

    # --- no-op UI surface (state flows via the event bus, not these) --------

    def run(self) -> None:  # pragma: no cover - lifecycle no-op
        pass

    def shutdown(self) -> None:
        if self.bus is None:
            return
        from src.events import EventType
        self.bus.unsubscribe(EventType.GAME_WON, self._on_game_won)
        self.bus.unsubscribe(EventType.GAME_QUIT, self._on_game_quit)
        self.bus.unsubscribe(EventType.TUTORIAL_HINT, self._on_tutorial_hint)
        self.bus = None

    def _display_title_screen(self) -> None:
        self.output_log.append("[title screen]")
