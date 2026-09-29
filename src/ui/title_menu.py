"""Title screen: logo, typewritten opening story, and the arrow-key main menu."""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

from rich.text import Text
from textual.widgets import Input

from engine.events import EventType
from utils.typewriter import TypewriterPresets, request_skip as request_typewriter_skip

if TYPE_CHECKING:
    from src.ui.textual_ui import TextualGameUI

logger = logging.getLogger(__name__)


class TitleMenu:
    """Owns the intro/menu state; renders into the app's output panel."""

    def __init__(self, app: TextualGameUI) -> None:
        self._app = app
        self.index = 0
        self.state = "idle"  # "typing" | "menu_ready" | "idle"
        self._title: Optional[Text] = None
        self._skip_hint: Optional[Text] = None
        self._story_text = ""
        self._full_story = ""

    def show(self, skip_typewriter: bool = False) -> None:
        """Display the title screen, full-panel, with arrow-key main menu."""
        title_ascii = '''
██╗  ██╗ █████╗ ██╗   ██╗███╗   ██╗████████╗███████╗██████╗
██║  ██║██╔══██╗██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
███████║███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██║  ██║
██╔══██║██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██║  ██║
██║  ██║██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██████╔╝
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═════╝

████████╗███████╗██████╗ ███╗   ███╗██╗███╗   ██╗ █████╗ ██╗
╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗██║
   ██║   █████╗  ██████╔╝██╔████╔██║██║██╔██╗ ██║███████║██║
   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║██╔══██║██║
   ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██║  ██║███████╗
   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝

A Terminal Adventure by NoHudd'''

        opening_story = '''

[bold cyan]>>> INITIALIZING SYSTEM MEMORY... <<<[/bold cyan]
Fragments of directories flicker. File clusters scream in silence.
The great corruption has spread through the machine, leaving broken symlinks and
phantom processes where life once pulsed.

Once, sysadmins kept balance between order and entropy.
But now… your body is gone. Your essence remains—
a [green]Sysadmin Spirit[/green], bound to the filesystem.

At the system's heart lurks the [red]Daemon Overlord[/red],
a malignant process feeding on entropy,
rewriting directories into its dominion of chaos.

Your mission: traverse the haunted filesystem,
purge corrupted sectors, reclaim lost commands,
and [bold]restore the root.[/bold]

Fail, and the machine is consumed.
Succeed, and the filesystem breathes again.

'''

        # Switch to full-panel intro mode
        self._app.add_class("intro-mode")
        self.index = 0
        self._title = Text(title_ascii, style="bold green", justify="center")
        self._skip_hint = Text(
            "\n[press any key to skip intro]\n",
            style="dim italic", justify="center",
        )
        self._full_story = opening_story

        if skip_typewriter:
            self._story_text = opening_story
            self.state = "menu_ready"
            self.render()
            return

        self._story_text = ""
        self.state = "typing"
        self.render()

        def run_typewriter():
            try:
                def cb(text: str):
                    self._story_text = text
                    self._app.call_from_thread(self.render)
                TypewriterPresets.INTRO.type_text_sync(opening_story, cb)
            except Exception as e:
                logger.error(f"Typewriter effect failed for title screen: {e}")
            finally:
                self._story_text = opening_story
                self.state = "menu_ready"
                self._app.call_from_thread(self.render)

        threading.Thread(target=run_typewriter, daemon=True).start()

    def render(self) -> None:
        """Compose and display the intro screen for the current menu state."""
        out = Text()
        if self._title is not None:
            out.append_text(self._title)
        if self._skip_hint is not None:
            out.append_text(self._skip_hint)

        if self._story_text:
            story = Text.from_markup(self._story_text)
            story.justify = "center"
            out.append_text(story)

        if self.state == "menu_ready":
            out.append("\n")
            labels = ["NEW GAME", "LOAD GAME", "EXIT"]
            for i, label in enumerate(labels):
                if i == self.index:
                    line = Text(f"  ▶  {label}  ◀  \n", style="reverse bold green", justify="center")
                else:
                    line = Text(f"     {label}     \n", style="dim cyan", justify="center")
                out.append_text(line)
            out.append_text(Text(
                "\n↑/↓ to select   ↵ to confirm   esc to quit\n",
                style="dim italic", justify="center",
            ))

        self._app.update_output(out)

    def select(self) -> None:
        """Confirm the highlighted main-menu option."""
        if self.state != "menu_ready":
            return
        choice = ["1", "2", "3"][self.index]
        self._app.remove_class("intro-mode")
        self.state = "idle"
        try:
            input_widget = self._app.query_one("#input-field", Input)
            input_widget.focus()
        except Exception:
            pass
        self._app.bus.emit_event(
            EventType.COMMAND_ENTERED,
            {"command": choice},
            "TextualGameUI"
        )

    def handle_key(self, key: str) -> bool:
        """Main-menu keys: arrows move, enter confirms, anything skips the typewriter.
        Returns True when the key was consumed."""
        if self.state == "typing":
            request_typewriter_skip()
            return True
        if self.state == "menu_ready":
            if key == "up":
                self.index = (self.index - 1) % 3
                self.render()
                return True
            if key == "down":
                self.index = (self.index + 1) % 3
                self.render()
                return True
            if key in ("enter", "return"):
                self.select()
                return True
        return False
