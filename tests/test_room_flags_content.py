"""Room flags are content: each flag names a file placed in its room, carries
FLAG{...} text, and tells a beginner what to type."""
from engine.content import find_flag_problems, load_all
from engine.schema.models import RoomFlag

PHASE1 = {
    "home_grove": "bash_profile",
    "root": "motd",
    "bin_armory": "ancient_manual_man",
    "var_dungeon": "system_err_log",
    "usr_share_games": "cow_wisdom_log",
    "cowsay_secret": "moo_file",
    "ghost_hidden": "flag",
}


def test_phase1_rooms_declare_their_flag_files() -> None:
    content = load_all("data")
    for room_id, file_id in PHASE1.items():
        flag = content.rooms[room_id].flag
        assert flag is not None, room_id
        assert flag.file == file_id
        assert "FLAG{" in flag.text


def test_content_has_no_flag_problems() -> None:
    assert find_flag_problems(load_all("data")) == []


def test_a_flag_file_missing_from_its_room_is_reported() -> None:
    content = load_all("data")
    room = content.rooms["root"]
    content.rooms["root"] = room.model_copy(update={"flag": RoomFlag(
        file="bash_profile", text="FLAG{x}", nudge="n", command="cat x",
    )})
    problems = find_flag_problems(content)
    assert any("root" in p and "bash_profile" in p for p in problems)
