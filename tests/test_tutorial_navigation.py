"""Tutorial second half: ps, pwd, up out of /home, and the highlighted Directories."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from rich.text import Text

from engine.api import GameSession
from src.ui.textual_ui import TextualGameUI


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tess", "guardian")
    ts = s.player.tutorial_state
    ts.update({"first_ls": True, "took_weapon": True, "equipped_weapon": True,
               "combat_action_taken": True,
               # The ls -a / cat checkpoint leg is covered by
               # test_tutorial_checkpoint.py; here it is already done.
               "ls_a_used": True, "lore_read": True})
    try:
        yield s
    finally:
        s.close()


def _last_hint(s: GameSession) -> dict:
    return s.ui.hints[-1]


def test_the_walk_from_ps_to_completion(session: GameSession) -> None:
    ts = session.player.tutorial_state
    assert session.engine.cmd_handler.tutorial.current_step() == "step_cat"

    session.submit("ps")
    assert ts["ps_used"] and _last_hint(session)["hint_id"] == "step_ps"

    session.submit("pwd")  # /home has nothing below it
    assert ts["pwd_used"] and not ts["went_up"]
    assert _last_hint(session)["hint_id"] == "step_up"

    session.submit("cd ..")
    assert ts["went_up"] and _last_hint(session)["hint_id"] == "step6"

    session.submit("ls")
    hint = _last_hint(session)
    assert ts["navigation_ls"] and hint["hint_id"] == "step6b"
    assert hint["highlight"] == "Directories"
    assert (hint["step"], hint["total"]) == (11, 11)
    assert "bin" in hint["text"]  # the example is a directory actually listed at /

    session.submit("cd bin")
    assert ts["completed"]


def test_ls_before_ps_keeps_asking_for_ps(session: GameSession) -> None:
    session.ui.hints.clear()
    session.submit("ls")
    assert session.ui.hints == []  # ls just lists; no new step
    session.submit("xyzzy")
    assert _last_hint(session)["hint_id"] == "step_cat"


def test_ls_in_a_dead_end_repeats_the_way_up(session: GameSession) -> None:
    session.submit("ps")
    session.submit("pwd")
    session.submit("ls")  # still in /home: no Directories
    assert _last_hint(session)["hint_id"] == "step_up"
    assert not session.player.tutorial_state["navigation_ls"]


def test_pwd_somewhere_with_directories_skips_the_way_up(session: GameSession) -> None:
    session.submit("cd /")
    session.submit("ps")
    session.submit("pwd")
    assert _last_hint(session)["hint_id"] == "step6"
    assert session.player.tutorial_state["went_up"]


def test_directories_flash_then_stay_lit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)
    app = TextualGameUI()
    app._settings_manager.settings["reduce_motion"] = False
    app.__class__._FLASH_SECONDS = 0.02

    listing = Text("Directories:\n  bin/ - The Armory\n\nFiles:\n  readme\n")

    def lit(content: object) -> str:
        # The listing carries no styles of its own, so any span is the highlight.
        assert isinstance(content, Text)
        return "".join(content.plain[s.start:s.end] for s in content.spans)

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            app.output_content = listing
            seen = []
            app._flash_section("Directories")
            for _ in range(10):
                seen.append(bool(lit(app.output_content)))
                await pilot.pause(0.03)
            assert True in seen and False in seen  # it pulsed
            assert lit(app.output_content) == "Directories:\n  bin/ - The Armory"
            assert "Files" not in lit(app.output_content)

    try:
        asyncio.run(scenario())
    finally:
        app.__class__._FLASH_SECONDS = 0.35
