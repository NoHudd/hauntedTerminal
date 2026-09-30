"""Every lore file is a story file: hidden until `ls -a`, listed in red like
.bash_profile, and reading it restores a memory (journal entry + autosave).

The manual in /bin used to print its text and do nothing else, so a player who
found it saw no save and no journal entry."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from rich.text import Text

import src.save as save_mod
from engine.api import GameSession
from src.commands.navigation import LsCommand
from src.item_effects import STORY_FLAG_TITLES
from src.save import SaveManager


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_mod, "save_manager", SaveManager(save_dir=str(tmp_path)))
    s = GameSession()
    s.new_game("Reader", "guardian")
    try:
        yield s
    finally:
        s.close()


def _lore(s: GameSession) -> dict[str, object]:
    """Story files: lore that restores a memory. Plain flag files (tagged
    "flag", like /'s motd) are lore too but carry no memory."""
    return {
        iid: it for iid, it in s.world.items.items()
        if it.type == "lore" and "flag" not in it.tags
    }


def test_every_lore_file_is_a_hidden_titled_memory(session: GameSession) -> None:
    for iid, item in _lore(session).items():
        assert item.hidden, f"{iid} should need ls -a"
        assert item.story_flag, f"{iid} restores no memory"
        assert item.story_flag in STORY_FLAG_TITLES, f"{iid}'s memory has no journal title"


def test_reading_the_manual_restores_a_memory_and_saves(
    session: GameSession, tmp_path: Path,
) -> None:
    session.world.add_item_to_room("ancient_manual_man", session.player.current_room)
    out = "\n".join(session.submit("cat ancient_manual_man"))

    assert "Memory restored: The Ancient Manual" in out
    assert session.player.get_story_flag("manual_recovered") is True
    assert list(tmp_path.glob("*.json")), "no autosave was written"
    assert "The Ancient Manual" in "\n".join(session.submit("journal"))


def test_story_files_list_in_red(session: GameSession) -> None:
    handler = session.engine.cmd_handler
    out = Text()
    LsCommand()._render_items(
        handler, out, ["readme_txt_corrupt", "segfault_shield"],
        hints=False, long_format=False, has_content=False,
    )
    styles = {out.plain[span.start:span.end]: str(span.style) for span in out.spans}
    assert "red" in styles[".readme_txt_corrupt"]  # hidden, so listed as a dotfile
    assert "red" not in styles["segfault_shield"]
