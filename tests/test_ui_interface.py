#!/usr/bin/env python3
"""
Unit tests for the UI interface protocol and exceptions.
"""

import unittest
from unittest.mock import Mock, MagicMock
from src.ui.ui_interface import UIProtocol, UIError, UIInitializationError, UIStateError


class MockUI:
    """Mock UI implementation for testing."""
    
    def __init__(self):
        self.output_content = ""
        self.inventory_content = ""
        self.stats_content = ""
        self.player_name = ""
        self.is_ready = False
    
    def run(self) -> None:
        """Mock run method."""
        pass
    
    def shutdown(self) -> None:
        """Mock shutdown method."""
        pass
    
    def update_output(self, content: str) -> None:
        """Mock update output method."""
        self.output_content = content
    
    def update_inventory(self, content: str) -> None:
        """Mock update inventory method."""
        self.inventory_content = content
    
    def update_stats(self, content: str) -> None:
        """Mock update stats method."""
        self.stats_content = content
    
    def update_exits(self, exits: list) -> None:
        """Mock update exits method."""
        pass
    
    def update_player_name(self, name: str) -> None:
        """Mock update player name method."""
        self.player_name = name
    
    def clear_console(self) -> None:
        """Mock clear console method."""
        self.output_content = ""
    
    def display_game_over(self) -> None:
        """Mock display game over method."""
        pass
    
    def update_game_state_panels(self, player, world) -> None:
        """Mock update game state panels method."""
        pass
    
    def save_current_game(self) -> None:
        """Mock save current game method."""
        pass


class TestUIInterface(unittest.TestCase):
    """Test cases for UI interface and exceptions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_ui = MockUI()
    
    def test_mock_ui_implements_protocol(self):
        """Test that MockUI properly implements UIProtocol."""
        # This test ensures our mock UI has all required methods
        ui = self.mock_ui
        
        # Test all required methods exist and are callable
        self.assertTrue(hasattr(ui, 'run'))
        self.assertTrue(callable(ui.run))
        
        self.assertTrue(hasattr(ui, 'shutdown'))
        self.assertTrue(callable(ui.shutdown))
        
        self.assertTrue(hasattr(ui, 'update_output'))
        self.assertTrue(callable(ui.update_output))
        
        self.assertTrue(hasattr(ui, 'update_inventory'))
        self.assertTrue(callable(ui.update_inventory))
        
        self.assertTrue(hasattr(ui, 'update_stats'))
        self.assertTrue(callable(ui.update_stats))
        
        self.assertTrue(hasattr(ui, 'update_exits'))
        self.assertTrue(callable(ui.update_exits))
        
        self.assertTrue(hasattr(ui, 'update_player_name'))
        self.assertTrue(callable(ui.update_player_name))
        
        self.assertTrue(hasattr(ui, 'clear_console'))
        self.assertTrue(callable(ui.clear_console))
        
        self.assertTrue(hasattr(ui, 'display_game_over'))
        self.assertTrue(callable(ui.display_game_over))
        
        self.assertTrue(hasattr(ui, 'update_game_state_panels'))
        self.assertTrue(callable(ui.update_game_state_panels))
        
        self.assertTrue(hasattr(ui, 'save_current_game'))
        self.assertTrue(callable(ui.save_current_game))
    
    def test_ui_methods_work(self):
        """Test that UI methods work as expected."""
        ui = self.mock_ui
        
        # Test update methods
        ui.update_output("Test output")
        self.assertEqual(ui.output_content, "Test output")
        
        ui.update_inventory("Test inventory")
        self.assertEqual(ui.inventory_content, "Test inventory")
        
        ui.update_stats("Test stats")
        self.assertEqual(ui.stats_content, "Test stats")
        
        ui.update_player_name("TestPlayer")
        self.assertEqual(ui.player_name, "TestPlayer")
        
        # Test clear console
        ui.clear_console()
        self.assertEqual(ui.output_content, "")
    
    def test_ui_error_hierarchy(self):
        """Test UI exception hierarchy."""
        # Test that UI exceptions inherit properly
        self.assertTrue(issubclass(UIError, Exception))
        self.assertTrue(issubclass(UIInitializationError, UIError))
        self.assertTrue(issubclass(UIStateError, UIError))
    
    def test_ui_exceptions_can_be_raised(self):
        """Test that UI exceptions can be raised and caught."""
        # Test UIError
        with self.assertRaises(UIError):
            raise UIError("Generic UI error")
        
        # Test UIInitializationError
        with self.assertRaises(UIInitializationError):
            raise UIInitializationError("UI failed to initialize")
        
        # Test UIStateError
        with self.assertRaises(UIStateError):
            raise UIStateError("UI is in invalid state")
    
    def test_ui_exception_messages(self):
        """Test that UI exceptions preserve error messages."""
        error_message = "Test error message"
        
        try:
            raise UIError(error_message)
        except UIError as e:
            self.assertEqual(str(e), error_message)
        
        try:
            raise UIInitializationError(error_message)
        except UIInitializationError as e:
            self.assertEqual(str(e), error_message)
        
        try:
            raise UIStateError(error_message)
        except UIStateError as e:
            self.assertEqual(str(e), error_message)
    
    def test_ui_exceptions_can_be_caught_as_base_type(self):
        """Test that specific UI exceptions can be caught as UIError."""
        # UIInitializationError should be catchable as UIError
        with self.assertRaises(UIError):
            raise UIInitializationError("Init error")
        
        # UIStateError should be catchable as UIError  
        with self.assertRaises(UIError):
            raise UIStateError("State error")


class TestUIProtocolUsage(unittest.TestCase):
    """Test cases for using UIProtocol in practice."""
    
    def test_function_accepts_ui_protocol(self):
        """Test that functions can accept UI protocol implementations."""
        def process_ui(ui: UIProtocol) -> str:
            """Function that expects a UI protocol implementation."""
            ui.update_output("Processing...")
            ui.update_player_name("TestPlayer")
            return "Done"
        
        # Should work with our mock UI
        mock_ui = MockUI()
        result = process_ui(mock_ui)
        
        self.assertEqual(result, "Done")
        self.assertEqual(mock_ui.output_content, "Processing...")
        self.assertEqual(mock_ui.player_name, "TestPlayer")
    
    def test_ui_error_handling_in_function(self):
        """Test error handling when UI operations fail."""
        def ui_operation_that_fails(ui: UIProtocol):
            """Function that might encounter UI errors."""
            try:
                # Simulate UI not ready
                if not hasattr(ui, 'is_ready') or not ui.is_ready:
                    raise UIStateError("UI is not ready")
                ui.update_output("Success")
            except UIStateError as e:
                raise UIError(f"UI operation failed: {e}")
        
        mock_ui = MockUI()
        
        # Should raise UIError when UI is not ready
        with self.assertRaises(UIError) as context:
            ui_operation_that_fails(mock_ui)
        
        self.assertIn("UI operation failed", str(context.exception))
        self.assertIn("UI is not ready", str(context.exception))


if __name__ == '__main__':
    unittest.main()