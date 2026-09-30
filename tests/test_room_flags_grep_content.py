"""Phase 2 rooms hide their flag in a log you must grep."""
from engine.content import find_flag_problems, load_all

GREP_ROOMS = {
    "mnt_forest": "lost_user_log",
    "usr_lib_arcane": "catalog_db",
    "dev_null_void": "kern_log",
    "srv_warrior_tomb": "access_log",
    "archive": "backup_tar_log",
}


def test_grep_rooms_declare_log_flags() -> None:
    content = load_all("data")
    for room_id, file_id in GREP_ROOMS.items():
        flag = content.rooms[room_id].flag
        assert flag is not None and flag.via == "grep", room_id
        assert flag.file == file_id
        assert content.items[file_id].log is not None
    assert find_flag_problems(content) == []


def test_first_grep_room_teaches_and_npc_rooms_clue() -> None:
    content = load_all("data")
    assert "grep" in content.rooms["mnt_forest"].flag.teach
    for room_id in ("mnt_forest", "usr_lib_arcane", "dev_null_void"):
        assert content.rooms[room_id].flag.clue, room_id


def test_npc_less_grep_rooms_have_a_note() -> None:
    content = load_all("data")
    assert "access_readme" in content.rooms["srv_warrior_tomb"].items
    assert "backup_readme" in content.rooms["archive"].items
