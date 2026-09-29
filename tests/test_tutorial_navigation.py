"""Tutorial second half: ps, pwd, up out of /home, and the highlighted Directories."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from rich.text import Text

from engine.api import GameSession
from src.events import EventType
from src.ui.textual_ui import TextualGameUI


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Tess", "guardian")
    ts = s.player.tutorial_state
    ts.update({"first_ls": True, "took_weapon": True, "equipped_weapon": True,
               "combat_action_taken": True})
    try:
        yield s
    finally:
        s.close()


def _text(lines: list[str]) -> str:
    return "\n".join(str(line) for line in lines)


def test_the_walk_from_ps_to_completion(session: GameSession) -> None:
    ts = session.player.tutorial_state
    assert session.engine.cmd_handler.tutorial.current_step() == "step5_postcombat"

    assert "[bold]pwd[/bold]" in _text(session.submit("ps"))
    assert ts["ps_used"]

    out = _text(session.submit("pwd"))
    assert "You're in [bold]/home[/bold]" in out and "cd ..[/bold]" in out
    assert ts["pwd_used"] and not ts["went_up"]

    out = _text(session.submit("cd .."))
    assert "You're in [bold]/[/bold] now" in out
    assert ts["went_up"]

    out = _text(session.submit("ls"))
    assert "Directories:" in out
    assert "for example [bold]cd bin[/bold]" in out
    assert ts["navigation_ls"]

    session.submit("cd bin")
    assert ts["completed"]


def test_ls_before_ps_keeps_asking_for_ps(session: GameSession) -> None:
    out = _text(session.submit("ls"))
    assert "Type: [bold]ps" not in out  # ls just lists; no new step
    assert not session.player.tutorial_state["ps_used"]
    assert "[bold]ps[/bold]" in _text(session.submit("xyzzy"))


def test_ls_in_a_dead_end_repeats_the_way_up(session: GameSession) -> None:
    session.submit("ps")
    session.submit("pwd")
    out = _text(session.submit("ls"))  # still in /home: no Directories
    assert "Go up one level" in out
    assert not session.player.tutorial_state["navigation_ls"]


def test_pwd_somewhere_with_directories_skips_the_way_up(session: GameSession) -> None:
    session.submit("cd /")
    session.submit("ps")
    out = _text(session.submit("pwd"))
    assert "You're in [bold]/[/bold] now" in out
    assert session.player.tutorial_state["went_up"]


def test_directories_flash_then_stay_lit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.ui.textual_ui.SKIP_INTRO", True)
    app = TextualGameUI()
    app._settings_manager.settings["reduce_motion"] = False
    app.__class__._FLASH_SECONDS = 0.02

    listing = Text("Directories:\n  bin/ - The Armory\n\nFiles:\n  readme\n")

    def lit(content: object) -> str:
        assert isinstance(content, Text)
        return "".join(
            content.plain[s.start:s.end] for s in content.spans if "on yellow" in str(s.style)
        )

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


def test_step6b_hint_asks_the_ui_to_highlight_directories(session: GameSession) -> None:
    seen: list[dict] = []
    session.bus.subscribe(EventType.TUTORIAL_HINT, lambda e: seen.append(e.data))
    session.submit("ps")
    session.submit("pwd")
    session.submit("cd ..")
    session.submit("ls")
    assert seen[-1]["hint_id"] == "step6b"
    assert seen[-1]["highlight"] == "Directories"
    assert seen[-1]["step"] == 9 and seen[-1]["total"] == 9
