"""SoundBoard — plays a sound effect when the game emits certain events.

A pure observer: it reads event payloads and never touches game state. The
Textual UI owns one, so the headless driver and the tests run without sound.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable

from engine.events import Event, EventBus, EventType
from src.sound.player import Player

logger = logging.getLogger(__name__)

_EVENTS = (
    EventType.ROOM_ENTERED,
    EventType.COMBAT_STARTED,
    EventType.COMBAT_ACTION_RESULT,
    EventType.ENEMY_DEFEATED,
    EventType.GAME_OVER,
    EventType.GAME_WON,
)


#: Rank of each sound. Events in one burst (the killing blow fires hit,
#: defeat, a room redraw and victory in a single tick) would otherwise stomp
#: each other: on Windows the last sound cuts the rest, elsewhere the
#: process cap drops whatever comes last. Within BURST_SECONDS, a sound
#: ranked below one already played is skipped.
PRIORITY = {
    "step": 0,
    "hit": 1, "hurt": 1,
    "heal": 2, "alert": 2,
    "defeat": 3,
    "gameover": 4, "victory": 4,
}
#: Rank at which a sound skips the player's concurrency cap.
FORCE_PRIORITY = 4
BURST_SECONDS = 0.05


def sound_for(event: Event) -> str | None:
    """The sound an event should make, or None for silence."""
    t, data = event.type, event.data
    if t is EventType.ROOM_ENTERED:
        return "step"
    if t is EventType.COMBAT_STARTED:
        return "alert"
    if t is EventType.COMBAT_ACTION_RESULT:
        if (data.get("healing") or 0) > 0:
            return "heal"
        if (data.get("damage") or 0) > 0:
            return {"player": "hit", "enemy": "hurt"}.get(data.get("actor", ""))
        return None
    if t is EventType.ENEMY_DEFEATED:
        return "defeat"
    if t is EventType.GAME_OVER:
        return "gameover" if data.get("reason") == "defeat" else None
    if t is EventType.GAME_WON:
        return "victory"
    return None


class SoundBoard:
    def __init__(self, player: Player, enabled: Callable[[], bool],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._player = player
        self._enabled = enabled
        self._clock = clock
        self._bus: EventBus | None = None
        self._last_at = float("-inf")
        self._last_rank = -1

    def attach(self, bus: EventBus) -> None:
        self.detach()
        self._bus = bus
        for event_type in _EVENTS:
            bus.subscribe(event_type, self._on_event)

    def detach(self) -> None:
        if self._bus is None:
            return
        for event_type in _EVENTS:
            self._bus.unsubscribe(event_type, self._on_event)
        self._bus = None

    def _on_event(self, event: Event) -> None:
        try:
            if not self._enabled():
                return
            name = sound_for(event)
            if name is None:
                return
            rank = PRIORITY[name]
            now = self._clock()
            in_burst = now - self._last_at < BURST_SECONDS
            if in_burst and rank < self._last_rank:
                return
            self._player.play(name, force=rank >= FORCE_PRIORITY)
            self._last_at = now
            self._last_rank = max(rank, self._last_rank) if in_burst else rank
        except Exception as e:
            logger.debug("sound board skipped %s: %s", event.type, e)
