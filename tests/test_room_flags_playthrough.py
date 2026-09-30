"""A new player's path: the tutorial captures /home's flag, / teaches motd."""
from collections.abc import Iterator

import pytest

from engine.api import GameSession
from src.save import save_manager


@pytest.fixture
def s(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setattr(save_manager, "save_dir", str(tmp_path))
    session = GameSession()
    session.new_game("t", "guardian")
    try:
        yield session
    finally:
        session.close()


def test_tutorial_then_first_plain_flag(s: GameSession) -> None:
    h = s.engine.cmd_handler
    s.submit("ls")
    s.submit("take segfault_shield")
    s.submit("equip segfault_shield")
    s.submit("take cracked_firewall")
    s.submit("equip cracked_firewall")
    while h.current_combat_session:
        s.submit(next(iter(h.current_combat_session.available_attacks)))
    s.submit("ls -a")
    s.submit("cat .bash_profile")
    assert s.world.flag_captured("home_grove")
    # /bin's random enemies would start a fight that swallows the next command.
    s.world.enemy_locations = {
        e: r for e, r in s.world.enemy_locations.items() if r != "bin_armory"
    }
    for cmd in ("ps", "pwd", "cd ..", "ls", "cd bin"):
        s.submit(cmd)
    assert s.player.tutorial_state.get("completed")
    s.submit("cd /")
    out = "\n".join(str(x) for x in s.submit("cat motd"))
    assert s.world.flag_captured("root")
    assert "Flags 2/5" in out
