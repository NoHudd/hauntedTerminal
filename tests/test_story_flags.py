"""The story tells one goal everywhere a beginner meets it: capture flags,
some flags hand you a key to a new directory, and 11 flags open /boot."""
import yaml

from engine.api import GameSession
from src.data_loader import load_tutorial_hints
from src.game_states import GameState


def _prologue() -> str:
    s = GameSession()
    try:
        # Walk the real path to the name prompt: difficulty, then class.
        s.engine.state_manager.set_state(GameState.WAITING_FOR_DIFFICULTY)
        s.engine.state_manager.set_state(GameState.WAITING_FOR_CLASS)
        s.ui.clear_console()
        s.engine.selected_class = "guardian"
        s.engine._show_tutorial_introduction()
        return "\n".join(s.ui.drain())
    finally:
        s.close()


def test_prologue_states_the_goal() -> None:
    text = _prologue()
    assert "flag" in text and "key" in text
    assert "11" in text and "/boot" in text


def test_skipping_the_tutorial_still_explains_the_goal() -> None:
    summary = load_tutorial_hints()["skip_summary"]
    for word in ("flag", "grep", "kill", "key", "11", "/boot", "hint"):
        assert word in summary, f"skip summary never mentions {word}"


def test_first_flag_lesson_links_flags_to_keys_and_boot() -> None:
    lesson = load_tutorial_hints()["step_cat"]
    assert "key" in lesson and "/boot" in lesson


def _yaml(path: str) -> dict:
    with open(path) as f:
        data: dict = yaml.safe_load(f)
    return data


def test_opt_key_is_not_described_as_class_restricted() -> None:
    assert "class" not in _yaml("data/items/keys.yaml")["opt_key"]["description"]


def test_the_knight_guards_boot_with_flags_not_a_key() -> None:
    room = _yaml("data/rooms/etc_hidden_configs.yml")["detailed_description"]
    knight = _yaml("data/npcs/firewall_knight.iptables.yml")
    text = room + knight["detailed_description"] + " ".join(knight["dialogue"]["without_key"])
    stale_lines = (
        "without the Key", "without the chmod Key", "carry the chmod Key", "No key, no access",
    )
    for stale in stale_lines:
        assert stale not in text


def test_docs_describe_the_keys_chain() -> None:
    readme = open("README.md").read()
    reference = open("REFERENCE.md").read()
    assert "stays sealed until you have permission" not in readme
    assert "master_key" not in reference
    assert "placed so that a run is always completable" not in reference
