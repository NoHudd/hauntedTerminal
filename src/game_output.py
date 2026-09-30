#!/usr/bin/env python3
"""GameOutput — the domain's output sink.

The command/combat layer no
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

import logging
import re
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class GameOutput:
    """A text sink that either forwards live or accumulates."""

    def __init__(self, forward: Callable[..., None] | None = None) -> None:
        self._forward = forward
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

    def replace(self, content: Any) -> None:
        """Emit content that replaces the panel rather than appending to it,
        for animation frames written long after their command started."""
        if self._forward is not None:
            self._forward(content, replace=True)
        else:
            self.messages.append(str(content))

    def error(self, message: str, log_message: str | None = None) -> None:
        """Show a player-facing error and log it with markup stripped."""
        self.write(message)
        clean = re.sub(r"\[.*?\]", "", log_message or message)
        logger.error(f"Command error: {clean}")

    def drain(self) -> list[str]:
        """Return accumulated output (forward-unset mode), then clear."""
        lines = self.messages[:]
        self.messages.clear()
        return lines
