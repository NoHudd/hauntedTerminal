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
from typing import Any


class GameOutput:
    """A text sink that either forwards live or accumulates."""

    def __init__(
        self,
        forward: Callable[[Any], None] | None = None,
        forward_frame: Callable[[Any], None] | None = None,
    ) -> None:
        self._forward = forward
        # Frame writes are streaming animation updates (typewriter): each frame
        # REPLACES the previous one on screen instead of appending a new line.
        self._forward_frame = forward_frame or forward
        self.messages: list[str] = []

    def write(self, content: Any) -> None:
        """Emit one line of output.

        content may be a plain/markup string OR a Rich renderable (e.g.
        rich.text.Text built with per-span styles). On the live path the object
        is forwarded intact so the UI can render its styles — stringifying here
        was a Phase 2b regression that flattened Text colors (ls/map/keys/journal
        rendered without their per-item styling). The accumulate path stores a
        string since tests only assert on plain text.
        """
        if self._forward is not None:
            self._forward(content)
        else:
            self.messages.append(str(content))

    def write_frame(self, content: Any) -> None:
        """Emit one animation frame: replaces the previous frame on screen.

        Accumulate mode keeps only the latest frame (coalesced), so headless
        logs show the final text once instead of a per-character flood."""
        if self._forward_frame is not None:
            self._forward_frame(content)
        else:
            if self.messages:
                self.messages[-1] = str(content)
            else:
                self.messages.append(str(content))

    def drain(self) -> list[str]:
        """Return accumulated output (forward-unset mode), then clear."""
        lines = self.messages[:]
        self.messages.clear()
        return lines
