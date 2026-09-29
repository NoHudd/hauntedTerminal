"""Suite-wide settings.

Both switches make a hidden failure a test failure: the event bus normally
logs and swallows a listener's exception, and ViewBuilder normally returns a
placeholder view when a build fails.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.events import EventBus
from src.viewmodels.view_builder import ViewBuilder


@pytest.fixture(autouse=True)
def _fail_loudly(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(EventBus, "strict_by_default", True)
    monkeypatch.setattr(ViewBuilder, "raise_errors", True)
    yield
