"""Content-layer exceptions."""
from __future__ import annotations


class ContentError(Exception):
    """Raised when game content fails to validate or link.

    This is the fail-loud replacement for the old log-only
    ``_validate_data_references`` (game_engine.py). A ContentError means the
    content graph is broken (dangling id-reference, missing required field,
    invalid value) and the game must not start.
    """


class ContentValidationError(ContentError):
    """A single YAML document failed schema validation."""


class DanglingReferenceError(ContentError):
    """An id-reference points at content that does not exist."""
