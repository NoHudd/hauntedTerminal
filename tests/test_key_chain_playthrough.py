"""/usr appears only after the /mnt flag; its flag then reveals /srv."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "weaver")
    session.player.tutorial_state["completed"] = True
    for room in ("mnt_forest", "usr_lib_arcane"):
        session.world.enemy_locations = {
            e: r for e, r in session.world.enemy_locations.items() if r != room
        }
    try:
        yield session
    finally:
        session.close()


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_the_chain_unfolds(s: GameSession) -> None:
    s.submit("cd /")
    assert "usr/" not in _out(s, "ls")
    assert "No such file or directory" in _out(s, "cd /usr")
    s.submit("cd /mnt")
    assert s.player.current_room == "mnt_forest"
    _out(s, "grep FLAG lost_user_log")
    s.submit("cd /")
    assert "usr/" in _out(s, "ls")
    s.submit("cd /usr")
    assert s.player.current_room == "usr_lib_arcane"
    out = _out(s, "grep FLAG catalog_db")
    assert s.player.has_item("opt_key") and "/srv" in out
    s.submit("cd /")
    assert "srv/" in _out(s, "ls")
