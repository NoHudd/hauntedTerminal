"""kill/defeat flags name an enemy instead of a file; the validator keeps
them honest."""
from engine.content import find_flag_problems, load_all
from engine.schema.models import RoomFlag


def _problems(room: str, flag: RoomFlag) -> list[str]:
    content = load_all("data")
    content.rooms[room] = content.rooms[room].model_copy(update={"flag": flag})
    return find_flag_problems(content)


def test_kill_flag_needs_a_pid_process_and_rogue_enemy() -> None:
    problems = _problems("proc_secrets", RoomFlag(
        via="kill", text="FLAG{x}", nudge="n", command="c", enemy="glitched_process.tmp",
    ))
    assert any("pid" in p for p in problems)


def test_kill_enemy_must_not_already_live_in_the_room() -> None:
    problems = _problems("core", RoomFlag(
        via="kill", text="FLAG{x}", nudge="n", command="c",
        enemy="daemon_overlord.sys", pid=9, process="x",
    ))
    assert any("already" in p or "pool" in p for p in problems)


def test_defeat_flag_enemy_must_be_in_the_room() -> None:
    problems = _problems("proc_secrets", RoomFlag(
        via="defeat", text="FLAG{x}", nudge="n", command="c", enemy="daemon_overlord.sys",
    ))
    assert any("proc_secrets" in p and "enemies" in p for p in problems)


def test_cat_flag_still_needs_a_file() -> None:
    problems = _problems("root", RoomFlag(
        via="cat", text="FLAG{x}", nudge="n", command="c",
    ))
    assert any("file" in p for p in problems)
