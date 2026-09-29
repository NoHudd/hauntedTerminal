"""GameOutput: the domain's text sink."""
from __future__ import annotations

import logging

import pytest

from src.game_output import GameOutput


def test_error_writes_markup_to_player_and_logs_it_stripped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    out = GameOutput()
    with caplog.at_level(logging.ERROR, logger="src.game_output"):
        out.error("[red]No such item.[/red]")

    assert out.drain() == ["[red]No such item.[/red]"]
    assert "Command error: No such item." in caplog.text


def test_error_logs_the_separate_log_message_when_given(
    caplog: pytest.LogCaptureFixture,
) -> None:
    out = GameOutput()
    with caplog.at_level(logging.ERROR, logger="src.game_output"):
        out.error("[red]Nope.[/red]", log_message="take failed: bad id")

    assert out.drain() == ["[red]Nope.[/red]"]
    assert "Command error: take failed: bad id" in caplog.text


def test_error_forwards_live_when_a_sink_is_set() -> None:
    seen: list[object] = []
    GameOutput(forward=seen.append).error("boom")
    assert seen == ["boom"]
