"""Sound playback through each OS's built-in player — no audio dependency.

Mac uses ``afplay``, Windows the stdlib ``winsound``, Linux the first of
``pw-play`` / ``paplay`` / ``aplay`` on the PATH. Anything missing or failing
means silence: sound is a garnish and must never break, block or slow the game.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SOUNDS_DIR = Path(__file__).resolve().parents[2] / "assets" / "sounds"

#: Master switch. The test suite turns it off so no test makes noise.
ENABLED = True

#: Most child players alive at once; sounds past this are dropped.
MAX_CONCURRENT = 4

_LINUX_PLAYERS: tuple[list[str], ...] = (["pw-play"], ["paplay"], ["aplay", "-q"])


class Player(Protocol):
    def play(self, name: str) -> None: ...


def _path(name: str) -> str:
    return str(SOUNDS_DIR / f"{name}.wav")


class SilentPlayer:
    """No audio available (or wanted)."""

    def play(self, name: str) -> None:
        pass


def _spawn(argv: list[str]) -> Any:
    return subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class CommandPlayer:
    """Plays a file by spawning a command-line player, never waiting on it."""

    def __init__(self, argv: list[str],
                 spawn: Callable[[list[str]], Any] = _spawn) -> None:
        self._argv = argv
        self._spawn = spawn
        self._running: list[Any] = []

    def play(self, name: str) -> None:
        try:
            # poll() reaps finished children, so none linger as zombies.
            self._running = [p for p in self._running if p.poll() is None]
            if len(self._running) >= MAX_CONCURRENT:
                return
            self._running.append(self._spawn([*self._argv, _path(name)]))
        except Exception as e:
            logger.debug("sound %s failed: %s", name, e)


class WinsoundPlayer:
    """Windows: async PlaySound. One sound at a time; a new one cuts the old."""

    def __init__(self) -> None:
        import winsound
        self._winsound: Any = winsound

    def play(self, name: str) -> None:
        try:
            w = self._winsound
            w.PlaySound(_path(name), w.SND_FILENAME | w.SND_ASYNC | w.SND_NODEFAULT)
        except Exception as e:
            logger.debug("sound %s failed: %s", name, e)


def make_player(platform: str = sys.platform,
                which: Callable[[str], str | None] = shutil.which) -> Player:
    """Pick the playback backend for this machine; silent when none works."""
    if not ENABLED:
        return SilentPlayer()
    try:
        if platform == "darwin":
            if which("afplay"):
                return CommandPlayer(["afplay"])
        elif platform == "win32":
            return WinsoundPlayer()
        else:
            for argv in _LINUX_PLAYERS:
                if which(argv[0]):
                    return CommandPlayer(argv)
    except Exception as e:
        logger.debug("no sound backend: %s", e)
    return SilentPlayer()
