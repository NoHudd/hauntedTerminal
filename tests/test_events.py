#!/usr/bin/env python3
"""
Unit tests for the event system.
"""

import unittest
from unittest.mock import Mock, patch
from src.events import EventBus, Event, EventType


class TestEventSystem(unittest.TestCase):
    """Test cases for the event system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_bus = EventBus()
        self.callback_called = False
        self.callback_data = None
    
    def test_event_creation(self):
        """Test creating an Event object."""
        event = Event(
            type=EventType.PLAYER_STATS_CHANGED,
            data={"player": "test_player"},
            source="test"
        )
        
        self.assertEqual(event.type, EventType.PLAYER_STATS_CHANGED)
        self.assertEqual(event.data["player"], "test_player")
        self.assertEqual(event.source, "test")
    
    def test_subscribe_and_emit(self):
        """Test subscribing to and emitting events."""
        def test_callback(event):
            self.callback_called = True
            self.callback_data = event.data
        
        # Subscribe to event
        self.event_bus.subscribe(EventType.PLAYER_STATS_CHANGED, test_callback)
        
        # Emit event
        event = Event(
            type=EventType.PLAYER_STATS_CHANGED,
            data={"health": 100},
            source="test"
        )
        self.event_bus.emit(event)
        
        # Check callback was called
        self.assertTrue(self.callback_called)
        self.assertEqual(self.callback_data["health"], 100)
    
    def test_emit_event_convenience_method(self):
        """Test the convenience emit_event method."""
        def test_callback(event):
            self.callback_called = True
            self.callback_data = event.data
        
        self.event_bus.subscribe(EventType.ITEM_TAKEN, test_callback)
        
        # Use convenience method
        self.event_bus.emit_event(
            EventType.ITEM_TAKEN,
            {"item_id": "test_item"},
            "test_source"
        )
        
        self.assertTrue(self.callback_called)
        self.assertEqual(self.callback_data["item_id"], "test_item")
    
    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        def test_callback(event):
            self.callback_called = True
        
        # Subscribe then unsubscribe
        self.event_bus.subscribe(EventType.GAME_STARTED, test_callback)
        self.event_bus.unsubscribe(EventType.GAME_STARTED, test_callback)
        
        # Emit event
        self.event_bus.emit_event(EventType.GAME_STARTED, {}, "test")
        
        # Callback should not have been called
        self.assertFalse(self.callback_called)
    
    def test_multiple_subscribers(self):
        """Test multiple callbacks for the same event."""
        callback_count = 0
        
        def callback1(event):
            nonlocal callback_count
            callback_count += 1
        
        def callback2(event):
            nonlocal callback_count
            callback_count += 1
        
        # Subscribe both callbacks
        self.event_bus.subscribe(EventType.ROOM_ENTERED, callback1)
        self.event_bus.subscribe(EventType.ROOM_ENTERED, callback2)
        
        # Emit event
        self.event_bus.emit_event(EventType.ROOM_ENTERED, {}, "test")
        
        # Both callbacks should have been called
        self.assertEqual(callback_count, 2)
    
    def test_event_history(self):
        """Test event history functionality."""
        # Emit some events
        self.event_bus.emit_event(EventType.GAME_STARTED, {}, "test")
        self.event_bus.emit_event(EventType.PLAYER_CREATED, {}, "test")
        
        history = self.event_bus.get_event_history()
        
        # Check history contains events
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].type, EventType.GAME_STARTED)
        self.assertEqual(history[1].type, EventType.PLAYER_CREATED)
    
    def test_callback_error_handling(self):
        """Test that callback errors don't break the event system."""
        def failing_callback(event):
            raise Exception("Test error")
        
        def working_callback(event):
            self.callback_called = True
        
        # Subscribe both callbacks
        self.event_bus.subscribe(EventType.GAME_OVER, failing_callback)
        self.event_bus.subscribe(EventType.GAME_OVER, working_callback)
        
        # Emit event - should not raise exception
        with patch('src.events.logger') as mock_logger:
            self.event_bus.emit_event(EventType.GAME_OVER, {}, "test")
            
            # Working callback should still be called
            self.assertTrue(self.callback_called)
            # Error should be logged
            mock_logger.error.assert_called_once()
    
    def test_history_limit(self):
        """Test that event history has a maximum size."""
        # Set a small history limit for testing
        self.event_bus._max_history = 3
        
        # Emit more events than the limit
        for i in range(5):
            self.event_bus.emit_event(EventType.PLAYER_STATS_CHANGED, {"count": i}, "test")
        
        history = self.event_bus.get_event_history()
        
        # History should be limited to max size
        self.assertEqual(len(history), 3)
        # Should contain the most recent events
        self.assertEqual(history[0].data["count"], 2)
        self.assertEqual(history[2].data["count"], 4)


if __name__ == '__main__':
    unittest.main()