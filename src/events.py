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
    """Types of events that can be emitted."""
    
    # Game State Events
    GAME_STARTED = auto()
    GAME_OVER = auto()
    GAME_SAVED = auto()
    GAME_LOADED = auto()
    
    # Player Events  
    PLAYER_CREATED = auto()
    PLAYER_STATS_CHANGED = auto()
    PLAYER_INVENTORY_CHANGED = auto()
    PLAYER_MOVED = auto()
    
    # UI Events
    COMMAND_ENTERED = auto()
    UI_ERROR = auto()
    UI_READY = auto()
    UI_STATE_CHANGED = auto()
    
    # World Events
    ROOM_ENTERED = auto()
    ROOM_CHANGED = auto()
    ITEM_TAKEN = auto()
    ITEM_DROPPED = auto()
    ITEM_SPAWNED = auto()
    ENEMY_DEFEATED = auto()
    ENEMY_SPAWNED = auto()
    ALL_ENEMIES_DEFEATED = auto()
    ROOM_UNLOCKED = auto()
    HIDDEN_ROOM_DISCOVERED = auto()
    NPC_INTERACTION_AVAILABLE = auto()
    WORLD_STATE_CHANGED = auto()
    
    # Combat Events
    COMBAT_STARTED = auto()
    COMBAT_ACTION_SELECTED = auto()
    COMBAT_ACTION_RESULT = auto()
    COMBAT_ENDED = auto()

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