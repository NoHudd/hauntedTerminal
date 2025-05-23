# Haunted Filesystem Experience (HFSE)

A text-based adventure game that helps users learn command-line skills in an RPG-like environment.

## Description

Haunted Filesystem is a terminal-based adventure game where players explore a "haunted" filesystem while learning command-line commands. As a sysadmin spirit, your task is to navigate through the corrupted system, collect items, solve puzzles, and ultimately defeat the Daemon Overlord that has corrupted the filesystem.

The game uses real command-line-like commands such as `cd`, `ls`, and `cat` to navigate and interact with the game world, making it both fun and educational.

## Features

- Text-based adventure with rich terminal visuals
- Command-line-like interface (`cd`, `ls`, `cat`, etc.)
- Turn-based combat system
- Inventory management
- Puzzles and exploration
- Dynamic world powered by YAML configuration

## Getting Started

### Prerequisites

- Python 3.7 or higher
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

- `help` - Display available commands
- `ls` - List files and directories
- `cd [directory]` - Change to specified directory
- `cat [file]` - Read the contents of a file
- `map` - Show available locations
- `inventory` / `inv` - Show collected items
- `take [item]` - Add an item to your inventory
- `drop [item]` - Remove an item from your inventory
- `use [item]` - Use an item from your inventory
- `examine [item]` - Examine an item in detail
- `talk [npc]` - Talk to an NPC
- `attack [enemy]` - Attack an enemy
- `look` - Look around the current location

## Customizing the Game

The game is designed to be easily customizable through YAML files:

- `data/rooms/` - Define rooms/locations
- `data/items/` - Define items and their properties
- `data/enemies/` - Define enemies and combat statistics
- `data/npcs/` - Define non-player characters and their dialogues

Each entity is defined in its own YAML file, making it easy to add, modify, or remove content without changing the core game code.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by classic text adventures and educational games
- Uses [Rich](https://github.com/Textualize/rich) for terminal formatting
- Uses [PyYAML](https://pyyaml.org/) for data loading

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
