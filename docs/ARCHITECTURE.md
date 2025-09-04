# HFSE Architecture Guide

## Overview

The Haunted Filesystem Experience (HFSE) has been architected using modern software design principles including event-driven architecture, dependency injection, and comprehensive error handling.

## Core Principles

### 1. Separation of Concerns
- **Game Engine**: Manages core game logic and state
- **UI System**: Handles user interface and display
- **Command Handler**: Processes user commands
- **World System**: Manages game world state
- **Save System**: Handles persistence

### 2. Event-Driven Architecture
The system uses a centralized event bus for communication between components, eliminating tight coupling.

### 3. Protocol-Based Interfaces
Components communicate through well-defined protocols/interfaces, enabling testability and modularity.

### 4. Comprehensive Error Handling
All components implement proper error handling with specific exception types and logging.

## Component Architecture

```
┌─────────────────┐    Events    ┌─────────────────┐
│   Game Engine   │◄─────────────►│   UI System     │
└─────────────────┘              └─────────────────┘
         │                                │
         ▼                                ▼
┌─────────────────┐              ┌─────────────────┐
│ Command Handler │              │ Event Bus       │
└─────────────────┘              └─────────────────┘
         │                                │
         ▼                                ▼
┌─────────────────┐              ┌─────────────────┐
│  World System   │              │ Metrics System  │
└─────────────────┘              └─────────────────┘
         │                                
         ▼                                
┌─────────────────┐              
│  Save System    │              
└─────────────────┘              
```

## Event System

### Event Types
Events are categorized by their purpose:

- **Game Events**: `GAME_STARTED`, `GAME_OVER`, `GAME_SAVED`, `GAME_LOADED`
- **Player Events**: `PLAYER_CREATED`, `PLAYER_STATS_CHANGED`, `PLAYER_INVENTORY_CHANGED`, `PLAYER_MOVED`
- **UI Events**: `COMMAND_ENTERED`, `UI_ERROR`, `UI_READY`
- **World Events**: `ROOM_ENTERED`, `ITEM_TAKEN`, `ENEMY_DEFEATED`

### Event Flow
1. Component performs an action
2. Emits relevant event with data
3. Event bus distributes to all subscribers
4. Subscribers react to event
5. Metrics are recorded

### Example Usage
```python
from src.events import event_bus, EventType

# Emit an event
event_bus.emit_event(
    EventType.ITEM_TAKEN,
    {"item_id": "sword", "player": player},
    "CommandHandler"
)

# Subscribe to events
def on_item_taken(event):
    print(f"Player took: {event.data['item_id']}")

event_bus.subscribe(EventType.ITEM_TAKEN, on_item_taken)
```

## Error Handling Strategy

### Exception Hierarchy
```
Exception
├── GameEngineError
│   └── DataLoadError
├── UIError
│   ├── UIInitializationError
│   └── UIStateError
└── SaveError (implicit)
```

### Error Handling Patterns

#### 1. Fail Fast
Components validate input and fail immediately with descriptive errors.

#### 2. Graceful Degradation
Non-critical failures don't crash the application.

#### 3. Comprehensive Logging
All errors are logged with context for debugging.

#### 4. User-Friendly Messages
Technical errors are translated to user-understandable messages.

### Example
```python
try:
    self.load_game_data()
except DataLoadError as e:
    logger.error(f"Data loading failed: {e}")
    raise GameEngineError(f"Could not initialize game: {e}")
```

## Interface Protocols

### UIProtocol
Defines the contract for UI implementations:

```python
class UIProtocol(Protocol):
    def run(self) -> None: ...
    def shutdown(self) -> None: ...
    def update_output(self, content: str) -> None: ...
    def update_inventory(self, content: str) -> None: ...
    # ... other UI methods
```

### GameEngineProtocol
Defines what UI can access from the game engine:

```python
class GameEngineProtocol(Protocol):
    @property
    def player(self) -> Optional[Any]: ...
    @property
    def world(self) -> Optional[Any]: ...
    # ... other engine properties
```

## Performance Monitoring

### Metrics Collection
The system automatically collects performance metrics:

- Event processing times
- Error rates
- Events per second
- Slow operation detection

### Monitoring Tools

#### Metrics Dashboard
```bash
python utils/metrics_dashboard.py --live
```

#### Performance Summary
```bash
python utils/metrics_dashboard.py --summary
```

#### Export Metrics
```bash
python utils/metrics_dashboard.py --export metrics.json
```

### Performance Thresholds
- **Slow Event**: > 100ms
- **Warning Error Rate**: > 10%
- **Slow Callback**: > 50ms

## Testing Strategy

### Unit Tests
- **Event System**: `tests/test_events.py`
- **UI Interface**: `tests/test_ui_interface.py`  
- **Game Engine**: `tests/test_game_engine.py`

### Test Categories
1. **Interface Compliance**: Ensure protocols are properly implemented
2. **Error Handling**: Test exception flows and recovery
3. **Event System**: Verify event emission and handling
4. **Performance**: Check for performance regressions

### Running Tests
```bash
# All tests
python run_tests.py

# Specific test module
python run_tests.py test_events
```

## Development Patterns

### Adding New Components

1. **Define Interface**: Create protocol for component contract
2. **Implement Component**: Follow error handling patterns
3. **Add Events**: Emit relevant events for state changes
4. **Add Tests**: Create comprehensive test coverage
5. **Update Documentation**: Document new patterns

### Event-Driven Communication

#### DO:
- Use events for cross-component communication
- Emit events for significant state changes
- Handle events asynchronously when possible
- Include relevant data in event payload

#### DON'T:
- Use events for synchronous request-response
- Create circular event dependencies
- Emit events too frequently (performance impact)
- Include sensitive data in event payloads

### Error Handling Best Practices

#### DO:
- Use specific exception types
- Log errors with full context
- Provide user-friendly error messages
- Implement proper cleanup in finally blocks

#### DON'T:
- Catch and ignore exceptions
- Use generic exception types
- Log sensitive information
- Let errors propagate without context

## Configuration

### Game States
Game states are defined as enums in `src/game_states.py`:

```python
class GameState(Enum):
    MENU = "menu"
    PLAYING = "playing"
    GAME_OVER = "game_over"
    EXIT = "exit"
```

### Default Values
- Default room: `home_grove`
- Default save directory: `saves/`
- Max event history: 100 events
- Metrics collection: 1000 events

## Deployment Considerations

### Performance
- Event system adds minimal overhead (~0.1ms per event)
- Metrics collection uses bounded memory
- UI updates are throttled to prevent performance issues

### Scalability
- Event system can handle high event volumes
- Metrics can be exported for external analysis
- Components can be easily replaced or upgraded

### Reliability
- Comprehensive error handling prevents crashes
- Event system continues working if individual callbacks fail
- Save system includes data validation and backup

## Migration from Legacy Code

### Steps Taken
1. **Added Event System**: Centralized communication
2. **Defined Interfaces**: Protocol-based contracts
3. **Improved Error Handling**: Specific exceptions and logging
4. **Added Metrics**: Performance monitoring
5. **Created Tests**: Comprehensive test coverage

### Benefits Achieved
- **Maintainability**: Clear component boundaries
- **Testability**: Protocol-based interfaces
- **Reliability**: Comprehensive error handling
- **Performance**: Built-in monitoring
- **Extensibility**: Event-driven architecture

## Future Improvements

### Potential Enhancements
1. **Async Event Processing**: For better performance
2. **Event Persistence**: Store critical events
3. **Distributed Events**: Multi-process support
4. **Advanced Metrics**: Machine learning insights
5. **Visual Dashboard**: Web-based monitoring

### Extension Points
- New event types can be easily added
- UI implementations can be swapped
- Custom metrics collectors can be plugged in
- Additional error handling strategies can be implemented