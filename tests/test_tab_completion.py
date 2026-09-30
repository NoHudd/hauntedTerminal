"""Tab finishes a name like a shell, but only when there is ghost text to
accept and no fight on; otherwise it moves focus as before, which is what
combat Selection Mode and the dev Tab-then-L log shortcut rely on. F12 opens
the logs even mid-typing."""
from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.suggester import SuggestFromList
from textual.widgets import Button, Input

from src.ui.command_input import CommandInput
from src.ui.screens.log_viewer import LogViewerScreen
from src.ui.textual_ui import TextualGameUI


class _Harness(App[None]):
    def __init__(self, in_combat: bool = False) -> None:
        super().__init__()
        self.in_combat = in_combat

    def compose(self) -> ComposeResult:
        field = CommandInput(
            id="cmd", suggester=SuggestFromList(["take health_packet"], case_sensitive=False)
        )
        field.can_complete = lambda: not self.in_combat
        yield field
        yield Button("elsewhere", id="other")


def _tab_after_typing(typed: str, in_combat: bool = False) -> tuple[str, bool]:
    """Type into the command box, press Tab; return (value, box still focused)."""
    app = _Harness(in_combat)
    result: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test() as pilot:
            field = app.query_one("#cmd", CommandInput)
            field.focus()
            if typed:
                await pilot.press(*typed)
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            result["value"] = field.value
            result["focused"] = field.has_focus

    asyncio.run(scenario())
    return str(result["value"]), bool(result["focused"])


def test_tab_accepts_the_ghost_suggestion() -> None:
    assert _tab_after_typing("take he") == ("take health_packet", True)


def test_tab_with_nothing_to_complete_leaves_the_box() -> None:
    value, focused = _tab_after_typing("")
    assert value == "" and not focused


def test_tab_in_combat_toggles_selection_mode_instead() -> None:
    value, focused = _tab_after_typing("take he", in_combat=True)
    assert value == "take he" and not focused


def test_tab_then_l_on_an_empty_prompt_opens_the_logs() -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#input-field", Input).focus()
            await pilot.press("tab", "l")
            await pilot.pause()
            assert any(isinstance(s, LogViewerScreen) for s in app.screen_stack)

    asyncio.run(scenario())


def test_f12_opens_the_logs_mid_typing() -> None:
    app = TextualGameUI()

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            field = app.query_one("#input-field", Input)
            field.focus()
            await pilot.press("t", "a")
            await pilot.press("f12")
            await pilot.pause()
            assert any(isinstance(s, LogViewerScreen) for s in app.screen_stack)
            assert field.value == "ta"

    asyncio.run(scenario())


def _suggest(typed: str, after: tuple[str, ...] = ()) -> str | None:
    from engine.api import GameSession
    from src.ui.command_suggester import CommandSuggester

    s = GameSession()
    s.new_game("t", "guardian")
    s.player.tutorial_state["completed"] = True
    try:
        for cmd in after:
            s.submit(cmd)
        suggester = CommandSuggester(
            get_player=lambda: s.player, get_world=lambda: s.world
        )
        return asyncio.run(suggester.get_suggestion(typed))
    finally:
        s.close()


def test_completion_does_not_reveal_hidden_files() -> None:
    """Like `ls`, completion keeps hidden files out of sight..."""
    assert "bash_profile" not in (_suggest("cat b") or "")


def test_a_leading_dot_does_not_reveal_hidden_files_before_ls_a() -> None:
    """`cat .` + Tab must not be a way round `ls -a`."""
    assert "bash_profile" not in (_suggest("cat .") or "")


def test_after_ls_a_a_leading_dot_completes_hidden_files() -> None:
    """Once listed, a dotfile completes from its dot, as in a real shell."""
    assert _suggest("cat .", after=("ls -a",)) == "cat .bash_profile"


def test_cat_reads_the_dotted_name() -> None:
    from engine.api import GameSession

    s = GameSession()
    s.new_game("t", "guardian")
    try:
        out = "\n".join(str(x) for x in s.submit("cat .bash_profile"))
    finally:
        s.close()
    assert "Sysadmin Spirit" in out
