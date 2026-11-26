"""SoundBoard — plays a sound effect when the game emits certain events.

A pure observer: it reads event payloads and never touches game state. The
Textual UI owns one, so the headless driver and the tests run without sound.
"""
from __future__ import annotations

import logging
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
    def __init__(self, player: Player, enabled: Callable[[], bool]) -> None:
        self._player = player
        self._enabled = enabled
        self._bus: EventBus | None = None

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
            if name is not None:
                self._player.play(name)
        except Exception as e:
            logger.debug("sound board skipped %s: %s", event.type, e)
