#!/usr/bin/env python3
"""
Event System for Game Engine and UI Communication

Provides a decoupled way for game engine and UI to communicate
without direct dependencies.
"""

from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from enum import Enum, auto
import logging
import time

logger = logging.getLogger(__name__)

class EventType(Enum):
    """
    Types of events that can be emitted in the game.

    All events carry serialized view data (dicts) rather than raw backend objects.
    This ensures clean separation between backend logic and UI presentation.
    """

    # ========================================
    # Game State Events
    # ========================================

    GAME_STARTED = auto()
    # Emitted by: game_engine.py
    # Subscribed by: textual_ui.py
    # Data: basic game start info

    GAME_OVER = auto()
    # Emitted by: game_engine.py (death in combat, F5 restart)
    # Subscribed by: textual_ui.py
    # Data: {"reason": "defeat" | "restart", "message": str (optional)}
    # The UI shows the GAME OVER card only for reason == "defeat". Nothing in the
    # game listens to it: the game-over screen's choices call the engine directly.

    TUTORIAL_HINT = auto()
    # Emitted by: tutorial_coach.py (show_hint)
    # Subscribed by: textual_ui.py (Echo panel), engine/headless/ui.py (text passthrough)
    # Data: {"hint_id": str, "text": str, "step": int | None, "total": int, "final": bool}

    GAME_WON = auto()
    # Emitted by: game_flow.py (win_game)
    # Subscribed by: textual_ui.py (finale), engine/headless/ui.py (text passthrough)
    # Data: {"ending_id": str, "sections": list[str], "stats": dict}

    GAME_RESTART_REQUESTED = auto()
    # Emitted by: textual_ui.py
    # Subscribed by: game_engine.py
    # Data: {}

    QUIT_CONFIRM_REQUESTED = auto()
    # Emitted by: commands/system.py (quit, when there is progress to lose)
    # Subscribed by: textual_ui.py (shows the chooser modal)
    # Data: {}
    #
    # The domain still accepts typed y/n/c, so a frontend that ignores this
    # event (the headless driver) keeps working exactly as before.

    GAME_QUIT = auto()
    # Emitted by: game_flow.py (perform_quit), game_engine.py (menu exit)
    # Subscribed by: textual_ui.py (App.exit), engine/headless/ui.py (records it)
    # Data: {}
    #
    # The domain asks to stop; the frontend decides how. Calling sys.exit() from
    # inside a Textual event handler skips the driver's terminal restore, which
    # is how a clean quit ends up leaving the shell in a mangled state.

    # ========================================
    # Player Events
    # ========================================

    PLAYER_CREATED = auto()
    # Emitted by: game_engine.py
    # Subscribed by: textual_ui.py
    # Data: StatsView dict

    PLAYER_STATS_CHANGED = auto()
    # Emitted by: game_engine.py, item_effects.py, commands/items.py
    # Subscribed by: textual_ui.py
    # Data: StatsView dict

    PLAYER_INVENTORY_CHANGED = auto()
    # Emitted by: game_engine.py, command_handler.py
    # Subscribed by: textual_ui.py
    # Data: InventoryView dict

    # ========================================
    # UI Events
    # ========================================

    COMMAND_ENTERED = auto()
    # Emitted by: textual_ui.py
    # Subscribed by: game_engine.py
    # Data: {"command": str, "game_state": GameState}

    UI_READY = auto()
    # Emitted by: textual_ui.py
    # Subscribed by: game_engine.py
    # Data: {}

    UI_STATE_CHANGED = auto()
    # Emitted by: state_manager.py
    # Subscribed by: textual_ui.py
    # Data: {"new_state": GameState, "old_state": GameState}

    # ========================================
    # World Events
    # ========================================

    ROOM_ENTERED = auto()
    # Emitted by: CommandHandler.announce_room (cd, flee, new game, load, ls -a
    #             reveal, post-victory redraw)
    # Subscribed by: textual_ui.py. A notification only: arrival rules run from
    #             CommandHandler.arrive(), called directly.
    # Data: {"room": RoomView dict, "player_name": str}

    ENEMY_DEFEATED = auto()
    # Emitted by: combat.py, before it calls CommandHandler.on_kill directly
    # Subscribed by: textual_ui.py (observer; loot and removal run from on_kill)
    # Data: {"enemy_id": str, "player_name": str}

    # ========================================
    # Combat Events
    # ========================================

    COMBAT_STARTED = auto()
    # Emitted by: combat.py
    # Subscribed by: textual_ui.py. The engine enters combat via the session's
    #             on_start callback, not this event.
    # Data: CombatView dict (includes enemy info, player health, available attacks)

    COMBAT_ACTION_SELECTED = auto()
    # Emitted by: command_handler.py
    # Subscribed by: combat.py
    # Data: {"choice": str}

    COMBAT_ACTION_RESULT = auto()
    # Emitted by: combat.py
    # Subscribed by: textual_ui.py
    # Data: {"actor": str, "message": str, "damage": int (optional), "healing": int (optional)}

    COMBAT_FRAME_UPDATED = auto()
    # Emitted by: combat.py (every turn, after player and enemy actions)
    # Subscribed by: textual_ui.py
    # Data: CombatView dict — updated health values and cooldowns for current frame

    COMBAT_ENDED = auto()
    # Emitted by: combat.py, before it calls CommandHandler.end_combat directly
    # Subscribed by: textual_ui.py, tutorial_coach.py (observers only; the game's
    #             reaction runs from end_combat in a fixed order)
    # Data: {"victory": bool, "defeat": bool, "fled": bool, "enemy_id": str, "enemies_defeated": int}

@dataclass
class Event:
    """Represents an event with data."""
    type: EventType
    data: Dict[str, Any]
    source: str = "unknown"

class EventBus:
    """Central event bus for decoupled communication."""

    #: Default for new buses. The test suite turns this on (tests/conftest.py)
    #: so a listener that raises fails the test instead of only being logged.
    strict_by_default: bool = False

    def __init__(self, strict: bool | None = None) -> None:
        self.strict = self.strict_by_default if strict is None else strict
        self._listeners: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._event_history: List[Event] = []
        self._max_history = 100
    
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe to an event type with a callback."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
        logger.debug(f"Subscribed callback to {event_type}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(callback)
                logger.debug(f"Unsubscribed callback from {event_type}")
            except ValueError:
                logger.warning(f"Callback not found for {event_type}")
    
    def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        start_time = time.time()
        logger.debug(f"Emitting event: {event.type} from {event.source} to {len(self._listeners.get(event.type, []))} listeners")
        
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Notify listeners. Snapshot the list — a handler that unsubscribes
        # itself (or another handler) mid-dispatch mutates the live list, and
        # iterating that list directly then skips whatever callback shifted
        # into the removed slot (classic mutate-while-iterating). Real impact:
        # CommandHandler._on_combat_ended self-unsubscribes on every combat,
        # so any handler registered next to it in the COMBAT_ENDED listener
        # list could silently never run.
        listeners = list(self._listeners.get(event.type, []))
        callback_errors = 0
        
        for callback in listeners:
            callback_start = time.time()
            try:
                callback(event)
                callback_time = time.time() - callback_start
                
                # Log slow callbacks
                if callback_time > 0.05:  # 50ms threshold
                    logger.warning(f"Slow callback for {event.type}: {callback_time:.3f}s")
                    
            except Exception as e:
                if self.strict:
                    raise
                callback_errors += 1
                logger.error(f"Error in event callback for {event.type}: {e}")
        
        total_time = time.time() - start_time
        if total_time > 0.1:
            logger.warning(
                f"{event.type} took {total_time:.3f}s across {len(listeners)} listeners"
            )
        if callback_errors:
            logger.warning(f"{event.type}: {callback_errors} callback error(s)")
    
    def emit_event(self, event_type: EventType, data: Dict[str, Any] | None = None, source: str = "unknown") -> None:
        """Convenience method to emit an event."""
        event = Event(type=event_type, data=data or {}, source=source)
        logger.debug(f"Emitting event: {event_type} from {source} with data: {data}")
        self.emit(event)
    
    def get_event_history(self) -> List[Event]:
        """Get the event history."""
        return self._event_history.copy()
    
    def clear_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()
