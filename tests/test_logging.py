"""Debug logging goes to the log file only, and each launch starts a fresh one.

debug_log used to echo every line to the terminal as well. Lines printed while
the world loaded sat behind the game screen and reappeared in the terminal when
the player quit; the log panel (L) already shows them from the file.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import main
import utils.debug_tools as debug_tools


def test_debug_log_writes_the_file_not_the_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    log = tmp_path / "debug.log"
    monkeypatch.setattr(debug_tools, "DEBUG_MODE", True)
    monkeypatch.setattr(debug_tools, "DEBUG_LOG_FILE", str(log))

    debug_tools.debug_log("world loaded", "system")

    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert "world loaded" in log.read_text()


def test_each_launch_starts_an_empty_log_and_keeps_the_last_one(tmp_path: Path) -> None:
    log, previous = tmp_path / "debug.log", tmp_path / "combat.log"
    log.write_text("last session\n")

    main.rotate_logs(str(log), str(previous))

    assert log.read_text() == ""
    assert previous.read_text() == "last session\n"


def test_first_launch_creates_both_files(tmp_path: Path) -> None:
    log, previous = tmp_path / "debug.log", tmp_path / "combat.log"

    main.rotate_logs(str(log), str(previous))

    assert log.read_text() == ""
    assert previous.exists()


def test_logs_rotate_before_the_game_modules_load() -> None:
    """Some modules log while importing (the combat system's attack table);
    rotating after the imports erased those lines from the new session."""
    source = Path(main.__file__).read_text()
    assert source.index("rotate_logs(") < source.index("from src.")
