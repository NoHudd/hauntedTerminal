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
    # Emitted by: game_engine.py, command_handler.py
    # Subscribed by: game_engine.py, textual_ui.py
    # Data: {"message": str, "action": str (optional)}

    GAME_WON = auto()
    # Emitted by: command_handler.py (win_game)
    # Subscribed by: textual_ui.py (finale), engine/headless/ui.py (text passthrough)
    # Data: {"ending_id": str, "sections": list[str], "stats": dict}

    GAME_SAVED = auto()
    # Emitted by: save.py, textual_ui.py
    # Subscribed by: game_engine.py
    # Data: {"trigger": str, "filename": str (optional)}

    GAME_RESTART_REQUESTED = auto()
    # Emitted by: textual_ui.py
    # Subscribed by: game_engine.py
    # Data: {}

    # ========================================
    # Player Events
    # ========================================

    PLAYER_CREATED = auto()
    # Emitted by: game_engine.py
    # Subscribed by: textual_ui.py
    # Data: StatsView dict

    PLAYER_STATS_CHANGED = auto()
    # Emitted by: game_engine.py, command_handler.py
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

    UI_ERROR = auto()
    # Emitted by: textual_ui.py
    # Subscribed by: game_engine.py
    # Data: {"error": str}

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
    # Emitted by: game_engine.py, command_handler.py
    # Subscribed by: command_handler.py, textual_ui.py
    # Data: {"room": RoomView dict, "player_name": str}

    ROOM_CHANGED = auto()
    # Emitted by: command_handler.py
    # Subscribed by: command_handler.py
    # Data: {"player_name": str, "from_room": str, "to_room": str}

    DELAYED_ROOM_REFRESH = auto()
    # Emitted by: commands/items.py (cat, after a story-beat read) so the "✦ Memory
    # restored / ✓ saved" message stays on screen before the room re-lists.
    # Subscribed by: textual_ui.py (schedules an `ls` via set_timer). Headless ignores it.
    # Data: {"room_id": str}

    ENEMY_DEFEATED = auto()
    # Emitted by: combat.py
    # Subscribed by: command_handler.py
    # Data: {"enemy_id": str, "room": str, "player_name": str}

    ALL_ENEMIES_DEFEATED = auto()
    # Emitted by: game_world.py
    # Subscribed by: command_handler.py
    # Data: {"room": str}

    # ========================================
    # Combat Events
    # ========================================

    COMBAT_STARTED = auto()
    # Emitted by: combat.py
    # Subscribed by: game_engine.py, textual_ui.py
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
    # Emitted by: combat.py
    # Subscribed by: command_handler.py, game_engine.py, textual_ui.py
    # Data: {"victory": bool, "defeat": bool, "fled": bool, "enemy_id": str, "enemies_defeated": int}

    TUTORIAL_SELECTION_MODE_USED = auto()
    # Emitted by: textual_ui.py (on_input_blurred, when TAB is pressed during tutorial combat)
    # Subscribed by: command_handler.py
    # Data: {}

@dataclass
class Event:
    """Represents an event with data."""
    type: EventType
    data: Dict[str, Any]
    source: str = "unknown"

class EventBus:
    """Central event bus for decoupled communication."""
    
    def __init__(self):
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
        
        # Notify listeners
        listeners = self._listeners.get(event.type, [])
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
                callback_errors += 1
                logger.error(f"Error in event callback for {event.type}: {e}")
        
        # Record metrics if available
        total_time = time.time() - start_time
        try:
            # Avoid circular import by importing here
            from utils.metrics import metrics_collector
            metrics_collector.record_event(
                event.type,
                f"EventBus.emit({event.source})",
                total_time,
                callback_errors == 0,
                f"{callback_errors} callback errors" if callback_errors > 0 else None
            )
        except ImportError:
            # Metrics not available, continue without recording
            pass
    
    def emit_event(self, event_type: EventType, data: Dict[str, Any] = None, source: str = "unknown") -> None:
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

# Global event bus instance
event_bus = EventBus()