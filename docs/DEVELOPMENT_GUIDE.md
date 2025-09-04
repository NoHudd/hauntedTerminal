# HFSE Development Guide

## Getting Started

### Prerequisites
- Python 3.7 or higher
- pip package manager
- Git for version control

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd HFSE-updated

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the game
python main.py
```

### Project Structure
```
HFSE-updated/
├── src/
│   ├── game_engine.py          # Main game engine
│   ├── events.py               # Event system
│   ├── metrics.py              # Performance monitoring
│   ├── game_states.py          # Game state definitions
│   ├── ui/
│   │   ├── ui_interface.py     # UI protocol definitions
│   │   ├── textual_ui.py       # Improved Textual UI
│   │   └── ui.py               # Original UI (compatibility)
│   ├── command_handler.py      # Command processing
│   ├── save.py                 # Save/load system
│   └── ...                     # Other game modules
├── tests/                      # Unit tests
├── utils/                      # Development utilities
├── docs/                       # Documentation
└── data/                       # Game content (YAML files)
```

## Development Workflow

### 1. Code Style
- Follow PEP 8 guidelines
- Use type hints for function parameters and return values
- Write descriptive docstrings for all public functions
- Keep functions focused on single responsibility

### 2. Testing
```bash
# Run all tests
python run_tests.py

# Run specific test file
python run_tests.py test_events

# Add new tests
# Create test files in tests/ directory following test_*.py pattern
```

### 3. Event-Driven Development

#### Adding New Events
1. Define event type in `src/events.py`:
```python
class EventType(Enum):
    # Existing events...
    NEW_FEATURE_ACTIVATED = auto()
```

2. Emit events from appropriate components:
```python
event_bus.emit_event(
    EventType.NEW_FEATURE_ACTIVATED,
    {"feature_id": feature_id, "player": self.player},
    "FeatureManager"
)
```

3. Subscribe to events where needed:
```python
event_bus.subscribe(EventType.NEW_FEATURE_ACTIVATED, self._on_feature_activated)
```

### 4. Error Handling Best Practices

#### Define Custom Exceptions
```python
class FeatureError(Exception):
    """Base exception for feature-related errors."""
    pass

class FeatureNotFoundError(FeatureError):
    """Raised when a feature is not found."""
    pass
```

#### Implement Proper Error Handling
```python
def activate_feature(self, feature_id: str):
    """Activate a game feature."""
    try:
        feature = self._get_feature(feature_id)
        feature.activate()
        logger.info(f"Feature {feature_id} activated")
        
        # Emit success event
        event_bus.emit_event(EventType.NEW_FEATURE_ACTIVATED, {...}, "FeatureManager")
        
    except FeatureNotFoundError as e:
        logger.error(f"Feature not found: {e}")
        raise FeatureError(f"Cannot activate feature {feature_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error activating feature {feature_id}: {e}")
        raise FeatureError(f"Feature activation failed: {e}")
```

### 5. UI Development

#### Implementing UI Protocol
```python
class CustomUI:
    """Custom UI implementation."""
    
    def __init__(self):
        self.is_ready = False
    
    def run(self) -> None:
        """Start the UI."""
        try:
            self._initialize()
            self.is_ready = True
            self._main_loop()
        except Exception as e:
            raise UIInitializationError(f"Failed to start UI: {e}")
    
    def shutdown(self) -> None:
        """Clean shutdown."""
        self.is_ready = False
        self._cleanup()
    
    def update_output(self, content: str) -> None:
        """Update output display."""
        if not self.is_ready:
            raise UIStateError("UI is not ready")
        self._display_output(content)
    
    # Implement other protocol methods...
```

#### Integrating with Game Engine
```python
# Use dependency injection
custom_ui = CustomUI()
engine = GameEngine(ui=custom_ui)
engine.run()
```

## Adding New Features

### Step-by-Step Process

1. **Plan the Feature**
   - Define requirements
   - Identify affected components
   - Plan event flows
   - Consider error scenarios

2. **Design the Interface**
   - Create protocol if needed
   - Define exception types
   - Plan event types

3. **Implement Core Logic**
   - Write main functionality
   - Add proper error handling
   - Emit relevant events
   - Add logging

4. **Add Tests**
   - Unit tests for core logic
   - Error handling tests
   - Event emission tests
   - Integration tests if needed

5. **Update Documentation**
   - Add to relevant docs
   - Update architecture diagrams
   - Add examples

6. **Test Integration**
   - Manual testing
   - Performance testing
   - Check metrics

### Example: Adding a New Game Mechanic

```python
# 1. Define events
class EventType(Enum):
    SPELL_CAST = auto()
    SPELL_LEARNED = auto()

# 2. Define exceptions
class SpellError(Exception):
    pass

class InsufficientManaError(SpellError):
    pass

# 3. Implement feature
class SpellSystem:
    def __init__(self, player, world):
        self.player = player
        self.world = world
        
    def cast_spell(self, spell_id: str):
        try:
            spell = self._get_spell(spell_id)
            
            if not self._has_mana(spell.cost):
                raise InsufficientManaError(f"Not enough mana for {spell_id}")
            
            self._consume_mana(spell.cost)
            effect = spell.cast(self.player, self.world)
            
            # Emit event
            event_bus.emit_event(
                EventType.SPELL_CAST,
                {"spell_id": spell_id, "player": self.player, "effect": effect},
                "SpellSystem"
            )
            
            return effect
            
        except SpellError:
            raise  # Re-raise spell errors
        except Exception as e:
            logger.error(f"Unexpected error casting {spell_id}: {e}")
            raise SpellError(f"Failed to cast {spell_id}")

# 4. Add to command handler
def cast_spell(self, spell_id):
    try:
        effect = self.spell_system.cast_spell(spell_id)
        self.ui.update_output(f"Cast {spell_id}! {effect}")
    except InsufficientManaError:
        self.ui.update_output("You don't have enough mana.")
    except SpellError as e:
        self.ui.update_output(f"Spell failed: {e}")
```

## Performance Guidelines

### Event System Performance
- Keep event handlers lightweight
- Avoid blocking operations in event handlers
- Use async handlers for heavy operations
- Monitor event processing times

### UI Performance  
- Batch UI updates when possible
- Avoid frequent redraws
- Use lazy loading for large datasets
- Monitor frame rates and response times

### Memory Management
- Clean up event subscriptions
- Limit event history size
- Use weak references where appropriate
- Monitor memory usage patterns

## Debugging and Troubleshooting

### Logging Configuration
```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)
```

### Debug Tools

#### Event History
```python
# Check recent events
from src.events import event_bus
history = event_bus.get_event_history()
for event in history[-10:]:
    print(f"{event.type}: {event.data}")
```

#### Metrics Dashboard
```bash
# Live dashboard
python utils/metrics_dashboard.py --live

# Export for analysis
python utils/metrics_dashboard.py --export debug_metrics.json
```

#### Performance Profiling
```python
from src.metrics import EventTimer, EventType

# Time critical operations
with EventTimer(EventType.ROOM_ENTERED, "DebugProfiler"):
    expensive_operation()
```

### Common Issues

#### Event System Problems
- **Circular Dependencies**: Check event subscription chains
- **Memory Leaks**: Ensure proper unsubscription
- **Slow Performance**: Check callback execution times

#### UI Issues
- **State Errors**: Verify UI initialization order
- **Display Problems**: Check content formatting
- **Input Handling**: Verify command processing flow

#### Save/Load Problems
- **Corruption**: Check JSON validation
- **Version Compatibility**: Verify save format versions
- **File Permissions**: Check directory access

## Testing Strategy

### Unit Testing
- Test individual components in isolation
- Mock external dependencies
- Test error conditions
- Verify event emissions

### Integration Testing
- Test component interactions
- Verify event flows
- Test UI integration
- Check save/load workflows

### Performance Testing
- Monitor event processing times
- Check memory usage patterns
- Test with large datasets
- Verify UI responsiveness

### Example Test
```python
import unittest
from unittest.mock import Mock, patch
from src.events import event_bus, EventType

class TestSpellSystem(unittest.TestCase):
    def setUp(self):
        self.player = Mock()
        self.world = Mock()
        self.spell_system = SpellSystem(self.player, self.world)
        
    def test_cast_spell_success(self):
        # Setup
        spell = Mock()
        spell.cost = 10
        spell.cast.return_value = "Fireball effect"
        
        self.player.mana = 20
        self.spell_system._get_spell = Mock(return_value=spell)
        
        # Execute
        with patch.object(event_bus, 'emit_event') as mock_emit:
            result = self.spell_system.cast_spell("fireball")
        
        # Verify
        self.assertEqual(result, "Fireball effect")
        mock_emit.assert_called_once_with(
            EventType.SPELL_CAST,
            {"spell_id": "fireball", "player": self.player, "effect": "Fireball effect"},
            "SpellSystem"
        )
```

## Contributing

### Code Review Checklist
- [ ] Code follows project style guidelines
- [ ] Proper error handling implemented
- [ ] Events emitted for state changes
- [ ] Tests added for new functionality
- [ ] Documentation updated
- [ ] Performance impact considered
- [ ] Backwards compatibility maintained

### Pull Request Process
1. Create feature branch from main
2. Implement changes with tests
3. Update documentation
4. Test thoroughly
5. Submit pull request with description
6. Address review feedback
7. Merge after approval

### Commit Message Format
```
type(scope): brief description

Longer description if needed

- List of changes
- Another change

Closes #issue-number
```

Types: feat, fix, docs, test, refactor, perf, chore

## Deployment

### Production Checklist
- [ ] All tests pass
- [ ] Performance metrics acceptable
- [ ] Error handling comprehensive
- [ ] Logging configured appropriately
- [ ] Documentation up to date
- [ ] Backwards compatibility verified

### Release Process
1. Update version numbers
2. Update CHANGELOG.md
3. Create release branch
4. Final testing
5. Tag release
6. Deploy to production
7. Monitor metrics

### Monitoring in Production
- Monitor event processing times
- Track error rates
- Watch memory usage
- Check user experience metrics
- Review logs regularly
