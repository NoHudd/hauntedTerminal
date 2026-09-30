"""End-of-run text: the paced victory finale, its recap card, and the game-over card."""
from __future__ import annotations

from typing import Any, Protocol

SECTION_SECONDS = 2.5


class _Output(Protocol):
    def update_output(self, content: str) -> None: ...
    def append_output(self, content: Any) -> None: ...
    def set_timer(self, delay: float, callback: Any) -> Any: ...


class FinaleReveal:
    """Reveals the ending one section per beat; any key dumps the rest at once."""

    def __init__(self, out: _Output) -> None:
        self._out = out
        self._queue: list[str] = []
        self._timers: list[Any] = []

    @property
    def revealing(self) -> bool:
        return bool(self._timers)

    def start(self, data: dict[str, Any], reduce_motion: bool) -> None:
        parts = list(data.get("sections", [])) + [build_recap(data.get("stats", {}))]
        self._queue = parts
        self._timers = []

        first = self._queue.pop(0)
        if reduce_motion:
            self._out.update_output(first)
            for part in self._queue:
                self._out.append_output(part)
            self._queue = []
            return
        self._out.update_output(first)
        for i, part in enumerate(self._queue, 1):
            self._timers.append(
                self._out.set_timer(SECTION_SECONDS * i, lambda p=part: self._step(p))
            )

    def _step(self, part: str) -> None:
        if part in self._queue:
            self._queue.remove(part)
        self._out.append_output(part)
        if not self._queue:
            self._timers = []

    def skip(self) -> None:
        """Any key during the reveal: dump everything remaining at once."""
        if not self._timers:
            return
        for t in self._timers:
            t.stop()
        self._timers = []
        for part in self._queue:
            self._out.append_output(part)
        self._queue = []


FULL_CLEAR_EPILOGUE = (
    "[bold green]Every directory answers again.[/bold green] You did not just "
    "stop the Overlord — you walked every path it corrupted and took back every "
    "flag it hid. The filesystem remembers who restored it."
)


def rank_for(flags: int, flags_total: int, secrets: int, secrets_total: int) -> str:
    """A win holds at least 12 of 13 main flags (11 open /boot, the Overlord
    drops the 12th), so the ladder starts at Sysadmin."""
    if not flags_total:
        return "—"
    if flags >= flags_total and secrets >= secrets_total:
        return "root"
    if flags >= flags_total:
        return "Sysadmin Supreme"
    return "Sysadmin"


def build_recap(stats: dict[str, Any]) -> str:
    flags, flags_total = stats.get("flags", 0), stats.get("flags_total", 0)
    secrets, secrets_total = stats.get("secrets", 0), stats.get("secrets_total", 0)
    rank = rank_for(flags, flags_total, secrets, secrets_total)
    if secrets_total and secrets >= secrets_total and rank != "root":
        rank += " · Keeper of Secrets"
    return (
        "── YOUR RUN ──────────────────────────\n"
        f"[bold]{stats.get('player_name', '?')}[/bold] · "
        f"{str(stats.get('player_class', '?')).title()} · "
        f"ending: [cyan]{str(stats.get('ending', '?')).upper()}[/cyan]\n"
        f"Level {stats.get('level', 1)} · {stats.get('cycles', 0)} cycles harvested\n"
        f"{stats.get('kills', 0)} enemies purged · {stats.get('items_found', 0)} items recovered\n"
        f"⚑ Flags {flags}/{flags_total} · Secrets {secrets}/{secrets_total} · "
        f"rank: [bold]{rank}[/bold]\n"
        f"difficulty: {stats.get('difficulty', '?')}\n"
        "──────────────────────────────────────\n"
        "[green]n[/green] new run · [red]q[/red] quit"
    )
