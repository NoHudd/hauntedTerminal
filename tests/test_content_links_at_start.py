"""The world's content is linked when the engine starts: broken content stops
the game at start instead of loading an empty or half-connected world."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine.headless import HeadlessUI
from src.game_engine import DataLoadError, ImprovedGameEngine


def test_a_dangling_reference_stops_the_game_at_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = tmp_path / "data"
    shutil.copytree("data", data)
    room = data / "rooms" / "home_grove.yml"
    room.write_text(room.read_text() + "\nitems:\n  - no_such_item\n")
    monkeypatch.setattr(ImprovedGameEngine, "DATA_DIR", str(data))

    with pytest.raises(DataLoadError, match="no_such_item"):
        ImprovedGameEngine(ui=HeadlessUI())


def test_the_shipped_content_links(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = ImprovedGameEngine(ui=HeadlessUI())
    try:
        assert engine.world.rooms and engine.world.items
        assert engine.world.enemies and engine.world.npcs
    finally:
        engine._cleanup()
