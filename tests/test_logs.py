"""Generated logs: long, look-alike, deterministic, one flag line; and the
validator's rules for grep flags."""
from engine.content import find_flag_problems, load_all
from engine.schema.models import Item, LogSpec, RoomFlag
from src.logs import log_lines


def _item(lines: int = 120) -> Item:
    return Item(
        id="test_log", name="test_log", type="lore",
        log=LogSpec(
            lines=lines,
            templates=["[{ts}] boot: step {n}", "[{ts}] boot: ok"],
            flag_line="[{ts}] boot: note FLAG{found_it}",
        ),
    )


def test_log_has_the_requested_length_and_one_flag_line() -> None:
    lines = log_lines(_item(120))
    assert len(lines) == 120
    assert sum("FLAG{found_it}" in line for line in lines) == 1
    assert "FLAG{found_it}" in lines[80]


def test_log_is_deterministic_and_fills_placeholders() -> None:
    assert log_lines(_item()) == log_lines(_item())
    assert not any("{ts}" in line or "{n}" in line for line in log_lines(_item()))


def _with_root_flag(content, flag: RoomFlag):
    content.rooms["root"] = content.rooms["root"].model_copy(update={"flag": flag})
    return find_flag_problems(content)


def test_grep_flag_needs_a_log_file() -> None:
    problems = _with_root_flag(load_all("data"), RoomFlag(
        file="motd", text="FLAG{cat_reads_files}", nudge="n", command="c", via="grep",
    ))
    assert any("root" in p and "log" in p for p in problems)


def test_unknown_via_is_reported() -> None:
    problems = _with_root_flag(load_all("data"), RoomFlag(
        file="motd", text="FLAG{cat_reads_files}", nudge="n", command="c", via="find",
    ))
    assert any("via" in p for p in problems)
