"""Final-review fixes for the keys chain: beginner-facing text must not point
at doors that are now invisible, or name secret rooms."""
import yaml

from engine.api import GameSession


def _out(s: GameSession, cmd: str) -> str:
    return "\n".join(str(x) for x in s.submit(cmd))


def test_help_and_man_only_name_directories_open_from_the_start() -> None:
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        text = _out(s, "help") + _out(s, "man pwd")
        for hidden in ("/usr/games", "/var/backups"):
            assert hidden not in text, f"{hidden} is not visible at the start"
    finally:
        s.close()


def test_home_guardian_points_at_the_flag_chain() -> None:
    with open("data/npcs/home_guardian.sys.yml") as f:
        lines = " ".join(yaml.safe_load(f)["dialogues"])
    assert "arcane archives" not in lines
    assert "/mnt" in lines


def test_using_a_key_does_not_name_an_undiscovered_secret() -> None:
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        s.player.tutorial_state["completed"] = True
        s.player.current_room = "mnt_forest"
        s.world.enemy_locations = {
            e: r for e, r in s.world.enemy_locations.items() if r != "mnt_forest"
        }
        s.player.add_to_inventory("opt_key", s.world.get_item("opt_key"))
        out = _out(s, "use opt_key")
        assert "opt_mage_tower" not in out and "/opt" not in out
        assert not s.world.is_discovered("opt_mage_tower")
    finally:
        s.close()
