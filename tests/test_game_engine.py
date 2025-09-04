#!/usr/bin/env python3
"""
Unit tests for the improved game engine.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
import os
import tempfile
import shutil
from src.game_engine import ImprovedGameEngine as GameEngine, GameEngineError, DataLoadError
from tests.test_ui_interface import MockUI


class TestGameEngine(unittest.TestCase):
    """Test cases for the GameEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.mock_ui = MockUI()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @patch('src.game_engine.logging')
    @patch('src.game_engine.os.makedirs')
    def test_directory_setup_success(self, mock_makedirs, mock_logging):
        """Test successful directory setup."""
        mock_makedirs.return_value = None
        
        with patch.object(GameEngine, '__load_game_data'):
            engine = GameEngine(ui=self.mock_ui)
            
        # Should call makedirs for all required directories
        expected_calls = [
            unittest.mock.call('saves', exist_ok=True),
            unittest.mock.call('data/rooms', exist_ok=True),
            unittest.mock.call('data/items', exist_ok=True),
            unittest.mock.call('data/enemies', exist_ok=True),
            unittest.mock.call('data/npcs', exist_ok=True)
        ]
        
        mock_makedirs.assert_has_calls(expected_calls, any_order=True)
    
    @patch('src.game_engine.logging')
    @patch('src.game_engine.os.makedirs')
    def test_directory_setup_failure(self, mock_makedirs, mock_logging):
        """Test directory setup failure handling."""
        mock_makedirs.side_effect = OSError("Permission denied")
        
        with self.assertRaises(GameEngineError) as context:
            with patch.object(GameEngine, '__load_game_data'):
                engine = GameEngine(ui=self.mock_ui)
        
        self.assertIn("Could not create required directories", str(context.exception))
    
    @patch('src.game_engine.os.path.exists')
    @patch('src.game_engine.os.listdir')
    @patch('src.game_engine.yaml.safe_load')
    def test_data_loading_success(self, mock_yaml_load, mock_listdir, mock_exists):
        """Test successful data loading."""
        # Mock file system
        mock_exists.return_value = True
        mock_listdir.return_value = ['test_room.yml']
        mock_yaml_load.return_value = {
            'name': 'Test Room',
            'description': 'A test room'
        }
        
        with patch('builtins.open', mock_open(read_data="test yaml data")):
            with patch.object(GameEngine, '_setup_directories'):
                with patch.object(GameEngine, '_setup_event_subscriptions'):
                    engine = GameEngine(ui=self.mock_ui)
        
        # Should have created world with loaded data
        self.assertIsNotNone(engine.world)
    
    @patch('src.game_engine.os.path.exists')
    @patch('src.game_engine.os.listdir')
    def test_data_loading_file_not_found(self, mock_listdir, mock_exists):
        """Test data loading when files are missing."""
        mock_exists.return_value = False
        mock_listdir.return_value = []
        
        with patch.object(GameEngine, '_setup_directories'):
            with patch.object(GameEngine, '_setup_event_subscriptions'):
                engine = GameEngine(ui=self.mock_ui)
        
        # Should handle missing directories gracefully
        self.assertIsNotNone(engine.world)
    
    @patch('src.game_engine.yaml.safe_load')
    def test_data_loading_yaml_error(self, mock_yaml_load):
        """Test data loading when YAML parsing fails."""
        mock_yaml_load.side_effect = Exception("Invalid YAML")
        
        with patch('src.game_engine.os.path.exists', return_value=True):
            with patch('src.game_engine.os.listdir', return_value=['bad.yml']):
                with patch('builtins.open', mock_open()):
                    with patch.object(GameEngine, '_setup_directories'):
                        with patch.object(GameEngine, '_setup_event_subscriptions'):
                            with self.assertRaises(DataLoadError) as context:
                                engine = GameEngine(ui=self.mock_ui)
        
        self.assertIn("Failed to load game data", str(context.exception))
    
    def test_game_engine_error_hierarchy(self):
        """Test game engine exception hierarchy."""
        self.assertTrue(issubclass(GameEngineError, Exception))
        self.assertTrue(issubclass(DataLoadError, GameEngineError))
    
    def test_engine_with_custom_ui(self):
        """Test engine initialization with custom UI."""
        custom_ui = MockUI()
        
        with patch.object(GameEngine, '_setup_directories'):
            with patch.object(GameEngine, '_setup_event_subscriptions'):
                with patch.object(GameEngine, '_load_game_data'):
                    engine = GameEngine(ui=custom_ui)
        
        self.assertEqual(engine.ui, custom_ui)
    
    def test_engine_with_default_ui(self):
        """Test engine initialization with default UI."""
        with patch('src.game_engine.TextualGameUI') as mock_textual_ui:
            mock_textual_ui.return_value = self.mock_ui
            
            with patch.object(GameEngine, '_setup_directories'):
                with patch.object(GameEngine, '_setup_event_subscriptions'):
                    with patch.object(GameEngine, '_load_game_data'):
                        engine = GameEngine()
        
        mock_textual_ui.assert_called_once()
    
    @patch('src.game_engine.event_bus')
    def test_event_subscriptions(self, mock_event_bus):
        """Test that engine subscribes to required events."""
        with patch.object(GameEngine, '_setup_directories'):
            with patch.object(GameEngine, '_load_game_data'):
                engine = GameEngine(ui=self.mock_ui)
        
        # Should subscribe to key events
        mock_event_bus.subscribe.assert_called()
        
        # Check for specific event subscriptions
        call_args = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
        
        from src.events import EventType
        expected_events = [
            EventType.COMMAND_ENTERED,
            EventType.UI_READY,
            EventType.UI_ERROR,
            EventType.GAME_SAVED
        ]
        
        for event_type in expected_events:
            self.assertIn(event_type, call_args)
    
    def test_initial_state(self):
        """Test engine initial state."""
        with patch.object(GameEngine, '_setup_directories'):
            with patch.object(GameEngine, '_setup_event_subscriptions'):
                with patch.object(GameEngine, '_load_game_data'):
                    engine = GameEngine(ui=self.mock_ui)
        
        # Check initial state
        self.assertIsNone(engine.player)
        self.assertIsNone(engine.cmd_handler)
        self.assertEqual(engine.current_room, "home_grove")
        self.assertEqual(engine.game_state.value, "menu")
        self.assertEqual(engine.save_dir, "saves")


class TestGameEngineEventHandlers(unittest.TestCase):
    """Test cases for game engine event handlers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_ui = MockUI()
        with patch.object(GameEngine, '_setup_directories'):
            with patch.object(GameEngine, '_setup_event_subscriptions'):
                with patch.object(GameEngine, '_load_game_data'):
                    self.engine = GameEngine(ui=self.mock_ui)
    
    def test_on_ui_ready_handler(self):
        """Test UI ready event handler."""
        from src.events import Event, EventType
        from src.game_states import GameState
        
        event = Event(EventType.UI_READY, {}, "test")
        
        self.engine._on_ui_ready(event)
        
        self.assertEqual(self.engine.game_state, GameState.MENU)
    
    @patch('src.game_engine.logger')
    def test_on_ui_error_handler(self, mock_logger):
        """Test UI error event handler."""
        from src.events import Event, EventType
        
        event = Event(EventType.UI_ERROR, {"error": "Test error"}, "test")
        
        self.engine._on_ui_error(event)
        
        mock_logger.error.assert_called_with("UI Error: Test error")
    
    @patch('src.game_engine.save_manager')
    def test_on_save_requested_handler_success(self, mock_save_manager):
        """Test save requested event handler with success."""
        from src.events import Event, EventType
        
        # Set up mock player and world
        self.engine.player = Mock()
        self.engine.world = Mock()
        self.engine.world.get_state.return_value = {"test": "state"}
        mock_save_manager.save_game.return_value = True
        
        event = Event(EventType.GAME_SAVED, {}, "test")
        
        with patch('src.game_engine.logger') as mock_logger:
            self.engine._on_save_requested(event)
        
        mock_save_manager.save_game.assert_called_once()
        mock_logger.info.assert_called_with("Game saved successfully")
    
    @patch('src.game_engine.save_manager')
    def test_on_save_requested_handler_no_data(self, mock_save_manager):
        """Test save requested event handler with no player/world data."""
        from src.events import Event, EventType
        
        # No player or world set
        self.engine.player = None
        self.engine.world = None
        
        event = Event(EventType.GAME_SAVED, {}, "test")
        
        with patch('src.game_engine.logger') as mock_logger:
            self.engine._on_save_requested(event)
        
        mock_save_manager.save_game.assert_not_called()
        mock_logger.warning.assert_called_with("Cannot save: no player or world data")


if __name__ == '__main__':
    unittest.main()