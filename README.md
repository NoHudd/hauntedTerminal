# Haunted Filesystem Experience (HFSE)

A sophisticated terminal user interface adventure game that teaches command-line skills through immersive RPG gameplay.

## Description

Haunted Filesystem is an advanced terminal-based adventure game where players explore a "haunted" filesystem while learning command-line commands. As a sysadmin spirit, your task is to navigate through the corrupted system, collect items, solve puzzles, and ultimately defeat the Daemon Overlord that has corrupted the filesystem.

The game features a full terminal user interface (TUI) with dedicated panels for inventory, stats, and real-time combat, while maintaining authentic command-line interaction patterns that make it both engaging and educational.

## Features

- **Full Terminal User Interface**: Rich TUI with dedicated panels and real-time updates
- **Authentic Command-Line Interface**: Uses real Unix commands (`cd`, `ls`, `cat`, etc.)
- **Event-Driven Combat System**: Real-time combat with script-style weapon usage (`./protocol_shield`)
- **Dynamic Class System**: Choose from Guardian, Weaver, or Shaman classes with unique abilities
- **Advanced Architecture**: Event-driven design with proper error handling and metrics
- **Immersive World**: Dynamic world powered by YAML configuration
- **Performance Monitoring**: Built-in metrics and dashboard system

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/NoHudd/haunted-filesystem.git
   cd haunted-filesystem
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Running the Game

Start the game by running:
```
python main.py
```

## Game Commands

### Navigation & Exploration
- `help` - Display available commands
- `ls` - List files (items), processes (NPCs), and corrupted entities (enemies)
- `cd [directory]` - Change to specified directory/room
- `cat [file]` - Read the contents of a file
- `map` - Show available locations

### Inventory & Items
- `inventory` / `inv` - Show collected items in the sidebar panel
- `take [item]` - Add an item to your inventory
- `drop [item]` - Remove an item from your inventory
- `use [item]` - Use consumables (potions, scrolls, etc.)
- `equip [weapon]` - Equip weapons for combat
- `examine [item]` - Examine an item in detail

### Combat & Interaction
- `talk [npc]` - Interact with NPCs
- `attack [enemy]` - Initiate combat with an enemy
- `./[weapon_name]` - Use equipped weapon during combat (e.g., `./protocol_shield`)

## Character Classes

Choose from three distinct classes, each with unique strengths:

- **Guardian**: High health (120 HP), defensive playstyle, excels in safe zones
- **Weaver**: High damage (15 DMG), aggressive playstyle, thrives in dangerous areas  
- **Shaman**: Balanced stats (100 HP), utility-focused, specializes in mystical zones

## Game Architecture

### Data-Driven Design
The game uses a modular, data-driven architecture powered by YAML configuration:

- `data/rooms/` - Room definitions with exits, items, NPCs, and enemies
- `data/items/` - Item properties, class restrictions, combat effects  
- `data/enemies/` - Enemy stats, drops, and boss mechanics
- `data/npcs/` - NPC dialogues and interactions
- `data/classes.yaml` - Character class definitions and abilities
- `data/attacks.yml` - Combat attacks and special abilities

### Technical Features
- **Event-Driven Architecture**: Decoupled game engine and UI communication
- **Textual Framework**: Modern Python TUI with reactive widgets
- **Error Handling**: Robust error recovery and standardized logging
- **Performance Monitoring**: Built-in metrics collection and dashboard
- **Modular Design**: Clean separation of concerns across all systems

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Dependencies

- **[Textual](https://github.com/Textualize/textual)** - Modern Python TUI framework
- **[Rich](https://github.com/Textualize/rich)** - Terminal formatting and markup
- **[PyYAML](https://pyyaml.org/)** - YAML data loading and parsing
- **[tqdm](https://github.com/tqdm/tqdm)** - Progress bars and loading indicators

## Acknowledgments

- Inspired by classic text adventures and educational games
- Built with modern Python TUI technologies for enhanced user experience
- Designed to make command-line learning engaging and interactive

## Game Overview

In *Haunted Filesystem Experience*, you play as a "sysadmin spirit" attempting to cleanse a corrupted system. An entity known as the Daemon Overlord has corrupted the filesystem, creating chaos and disorder. Your mission is to navigate through different directories, solve puzzles, and confront the Daemon Overlord's influence.

## Educational Goals

While playing this game, you'll naturally learn:

- Basic command-line navigation
- File manipulation
- System exploration
- Problem-solving skills

## Credits

Developed as a fun way to learn command-line skills in a narrative-driven experience.

Enjoy your adventure in the Haunted Filesystem! 
