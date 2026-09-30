"""Every room now has a flag: rogues in the enemy-free rooms, boss drops."""
from engine.content import find_flag_problems, load_all

ROGUES = {"proc_secrets": 1337, "deprecated_dir": 2048, "etc_hidden_configs": 4242}
BOSSES = {"core": "daemon_overlord.sys", "opt_mage_tower": "corruption_lord.exe",
          "mirror_sector": "shadow_process"}


def test_every_room_has_a_flag() -> None:
    content = load_all("data")
    assert [r for r, room in content.rooms.items() if room.flag is None] == []
    assert find_flag_problems(content) == []


def test_rogues_and_bosses_are_wired() -> None:
    content = load_all("data")
    for room, pid in ROGUES.items():
        flag = content.rooms[room].flag
        assert flag.via == "kill" and flag.pid == pid
        rogue = content.enemies[flag.enemy]
        assert rogue.pool_excluded and rogue.health <= 25 and rogue.experience <= 10
    for room, boss in BOSSES.items():
        assert content.rooms[room].flag.via == "defeat"
        assert content.rooms[room].flag.enemy == boss
