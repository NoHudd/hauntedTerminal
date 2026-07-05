#!/usr/bin/env python3
"""GameOutput — the domain's output sink.

Phase 2b of the rewrite (docs/REWRITE_PLAN.md): the command/combat layer no
longer holds a UI reference. It writes narrative text to this sink, which
forwards each line to a callback the engine injects (dependency inversion). The
domain now depends on this small abstraction instead of a concrete Textual UI.

Two modes:
- forward set (normal): each write is pushed straight to the injected callback,
  preserving the original live, ordered, thread-safe output behavior.
- forward unset: writes accumulate and can be read with drain() (handy for tests
  that want to inspect output without a UI).

State (rooms, stats, inventory) still flows through the event bus, unchanged.
"""
from __future__ import annotations

from collections.abc import Callable


class GameOutput:
    """A text sink that either forwards live or accumulates."""

    def __init__(self, forward: Callable[[str], None] | None = None) -> None:
        self._forward = forward
        self.messages: list[str] = []

    def write(self, content: str) -> None:
        """Emit one line of narrative/command output."""
        text = str(content)
        if self._forward is not None:
            self._forward(text)
        else:
            self.messages.append(text)

    def drain(self) -> list[str]:
        """Return accumulated output (forward-unset mode), then clear."""
        lines = self.messages[:]
        self.messages.clear()
        return lines
