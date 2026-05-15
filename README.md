# Haunted Filesystem Experience (HFSE)
## The Great Kernel Panic

A narrative-driven text adventure where you play as a Sysadmin Spirit navigating a corrupted filesystem in the aftermath of a catastrophic system failure. Learn command-line skills while uncovering the mystery of the Great Kernel Panic.

---

<!-- Intro Screenshot -->
![HFSE Intro](./Intro.png)
*The terminal interface of Haunted Filesystem Experience*

---

## 📖 Story Overview

**The Great Kernel Panic has shattered the system.**

You awaken in `/dev/null` - the Void - with no memory of who you were. You are a Sysadmin Spirit, a maintenance process that was terminated during the catastrophic system failure and somehow... came back.

The filesystem is corrupted. The Daemon Overlord - once known as `init` (PID 1, the first process) - has gone rogue after witnessing the Creator's fatal mistake. Corrupted daemons roam the directories. Orphaned files cry out from `/home/lost+found`. The system cannot reboot.

Your mission: Navigate the haunted directories, piece together what happened, and confront the Daemon Overlord in `/boot/kernel` - the Core. Only then can you restore order to the filesystem.

But first, you must remember who you are. Your `.bash_profile` drifts somewhere in the wreckage...

---

## ✨ Features

### Core Gameplay
- **Command-Line Interface**: Use real Unix-like commands (`cd`, `ls`, `cat`, `ls -a`) to explore
- **Turn-Based Combat**: Fight corrupted processes and daemon enemies
- **Class System**: Choose from 3 classes with unique abilities:
  - **Guardian** - High HP, defensive tank (120 HP, 10 DMG)
  - **Weaver** - High damage mage (90 HP, 15 DMG)
  - **Shaman** - Balanced hybrid with healing (100 HP, 8 DMG)

### Progression Systems
- **Harvesting Cycles (XP)**: Gain cycles from defeated enemies to level up
- **Level Progression**: +10 Max HP and +2 DMG per level with exponential scaling
- **Item Persistence**: Ephemeral items are lost on death, persistent items survive
- **Story Flags**: Track narrative progression through key story beats

### World & Content
- **19 Explorable Rooms**: From `/home/lost+found` to `/boot/kernel` - The Core
- **43 Unique Items**: Weapons, armor, consumables, crafting materials, trinkets, keys, and lore fragments
- **13 NPCs**: Including the Firewall Knight, Forge Master, and the mysterious Null Whisper
- **19 Enemies**: From corrupted processes to the Daemon Overlord himself
- **Environmental Effects**: Heat damage in `/tmp`, void pull in `/dev/null`
- **Dynamic Loot**: Item rarity based on directory depth (common in `/home`, legendary in `/root`)

### Story & Secrets
- **Lore Fragments**: Piece together the truth about the Great Kernel Panic
- **Sudo Trial**: Face your Shadow Process in `/proc/self` to earn superuser privileges
- **Easter Egg**: Discover the Great ASCII Bovine and claim the Milk of Motherboard
- **Multiple Endings**: Class-specific endings based on your choices

---

## 🎮 Getting Started

### Quick Start (Recommended)

**The easiest way to start playing!** Just run the appropriate start script for your system:

**On Mac/Linux:**
```bash
./start.sh
```

**On Windows:**
```cmd
start.bat
```

The start script will automatically:
- Check for Python installation
- Create a virtual environment
- Install all dependencies
- Launch the game with a cool startup sequence

**First time setup is completely automatic!**

---

### Manual Installation (Alternative)

If you prefer to set things up manually:

#### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

#### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/NoHudd/HFSE.git
   cd HFSE
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the game:
   ```bash
   python main.py
   ```

---

## 🎯 Game Commands

### Navigation
- `ls` - List items, NPCs, and exits in current directory
- `ls -a` - Reveal hidden files and directories
- `cd [path]` - Move to a different directory (`cd /var` or `cd var`)
- `pwd` - Show current directory
- `map` - Show available locations
- `find` - Search for items, NPCs, or rooms

### Interaction
- `cat [filename]` - Read file contents (lore fragments, logs, etc.)
- `take [item]` - Pick up an item
- `drop [item]` - Remove an item from inventory
- `use [item]` - Use a consumable
- `equip [weapon]` - Equip a weapon for combat
- `examine [item]` - Inspect an item's properties
- `talk [npc]` - Speak with NPCs for hints and lore

### Combat
- `attack [enemy]` - Initiate combat
- `[attack_name]` - Use class-specific abilities in combat
- `use [item]` - Use consumables during combat
- `flee` - Attempt to escape combat (in-combat only)

### System
- `inventory` / `inv` - View your items
- `keys` - Show key progression system
- `ps` - Show running processes
- `shortcuts` - List item shortcuts and typing tips
- `help` - Display available commands
- `save` - Save your progress
- `quit` / `exit` - Exit the game (offers to save)

---

## 🗺️ The Filesystem

### Key Locations

- **`/dev/null` - The Void**: Where you awakened. Void pull drains HP without Null-Void Cloak.
- **`/home/lost+found` - The Graveyard**: Orphaned files and broken symlinks. Find your `.bash_profile`.
- **`/bin` - The Armory**: Sacred command icons (cp, mv, rm). The Librarian guides you to lore.
- **`/tmp` - The Forge**: Extreme heat (2 HP/turn). Craft legendary weapons with the Forge Master.
- **`/var/log` - The Memory Banks**: Crash logs and error files. Discover the Creator's Typo.
- **`/etc/iptables` - The Kernel Gate**: Firewall Knight blocks passage. Requires chmod_key.
- **`/boot/kernel` - The Core**: Final confrontation with the Daemon Overlord.
- **`/proc/self` - The Mirror Sector**: Sudo Trial - fight your Shadow Process.
- **`/usr/share/games/cowsay/.secret/` - The Bovine Sanctuary**: Easter egg location.

---

## 🎓 Character Classes

### Guardian (Tank)
- **Base Stats**: 120 HP, 10 DMG
- **Starter Weapon**: Segmentation Fault Shield
- **Playstyle**: High survivability, defensive abilities
- **Attacks**: Strike, Power Strike, Shield Bash

### Weaver (Mage)
- **Base Stats**: 90 HP, 15 DMG
- **Starter Weapon**: Null Pointer
- **Playstyle**: High damage output, glass cannon
- **Attacks**: Arcane Bolt, Fireball, Frost Nova

### Shaman (Hybrid)
- **Base Stats**: 100 HP, 8 DMG
- **Starter Weapon**: Daemon Whisper
- **Playstyle**: Balanced, healing capabilities
- **Attacks**: Nature Strike, Ancient Fury, Healing Strike

---

## 🛠️ Customizing the Game

HFSE is fully data-driven through YAML files:

### Data Structure
```
data/
├── rooms/          # Room definitions, exits, NPCs, enemies
├── items/          # Weapons, armor, consumables, lore fragments
│   ├── weapons.yaml
│   ├── armor.yaml
│   ├── consumables.yaml
│   ├── crafting.yaml
│   ├── trinkets.yaml
│   └── lore_fragments.yaml
├── enemies/        # Enemy stats, loot, boss mechanics
├── npcs/           # NPC dialogues, merchant inventories
├── attacks.yml     # Class-specific combat abilities
└── classes.yaml    # Character class definitions
```

### Adding Content

**New Room**: Create `data/rooms/room_id.yml`
```yaml
name: The New Sector
description: A mysterious directory...
exits:
  - connected_room_1
  - connected_room_2
items: []
npcs: []
enemies:
  - enemy_id
```

**New Item**: Add to appropriate `data/items/*.yaml`
```yaml
item_id:
  name: "Item Name"
  description: "Item description"
  type: "weapon"
  damage: 15
  rarity: "rare"
  persistence: "persistent"
  allowed_classes:
    - guardian
```

---

## 🎲 Game Mechanics

### Harvesting Cycles (XP System)
- Defeat enemies to gain harvesting cycles
- Base: 50 cycles per enemy, 150 for bosses
- Level up: +10 Max HP, +2 DMG
- Exponential scaling: Each level requires 1.5x more cycles

### Item Persistence
- **Persistent items**: Survive death (weapons, armor, keys)
- **Ephemeral items**: Lost on death (consumables, temporary buffs)
- Check item descriptions for persistence type

### Story Progression
- Read lore fragments to unlock story flags
- Story flags gate access to special areas (Mirror Sector, Bovine Sanctuary)
- Multiple endings based on class and choices

### Rarity System
Items spawn based on directory depth:
- **`/home`, `/var`**: Common items dominate
- **`/bin`, `/etc`, `/usr`**: Uncommon and rare items
- **`/dev`**: Epic items spawn
- **`/root`**: Legendary items only

---

## 🔑 Tips & Hints

1. **Use `ls -a`** to reveal hidden files and secret paths
2. **Read everything**: Lore fragments contain crucial story beats
3. **Talk to NPCs**: They provide hints about item locations and story progression
4. **Craft strategically**: The Forge Master in `/tmp` can upgrade your gear
5. **Save often**: The filesystem is dangerous
6. **Explore thoroughly**: Hidden rooms contain powerful items
7. **Choose items wisely**: Ephemeral items don't persist through death

---

## 📚 Educational Goals

While playing HFSE, you'll naturally learn:

- **Command-line navigation**: `cd`, `ls`, `ls -a`, `pwd`, `cat`, `find`
- **File system structure**: Understanding Unix directory hierarchy
- **Hidden files**: The significance of dot files (`.bash_profile`, `.moo`)
- **System concepts**: Processes, daemons, /dev/null, /proc, init, permissions
- **Problem-solving**: Puzzle solving through exploration and reading

---

## 🏆 Achievements & Challenges

- Complete the Sudo Trial and earn the sudo_privileges_badge
- Find all 6 lore fragments to understand the full story
- Discover the Great ASCII Bovine easter egg
- Defeat the Daemon Overlord and choose your ending
- Reach max level through harvesting cycles
- Craft a legendary weapon at The Forge

---

## 🐛 Development

### Debug Mode

Copy `config/settings.example.py` to `config/settings.py` and enable debug features:

```python
DEV_MODE = True
DEBUG_MODE = True
SKIP_INTRO = True
```

### Project Structure

```
HFSE/
│
├── main.py                         # Entry point — starts the Textual app
├── start.sh / start.bat            # Auto-setup scripts (venv + deps + launch)
├── requirements.txt                # Python dependencies
│
├── src/                            # All game logic
│   ├── game_engine.py              # Orchestrator — wires player, world, UI, events together
│   │                               #   handles game states, new game / restart / load flows
│   ├── game_world.py               # World state — rooms, item/enemy locations, lock states,
│   │                               #   room discovery, loot placement
│   ├── game_states.py              # GameState enum (MENU, PLAYING, IN_COMBAT, GAME_OVER…)
│   ├── state_manager.py            # Enforces valid state transitions, emits UI_STATE_CHANGED
│   ├── player.py                   # Player stats, inventory, HP/damage, move_to(), to/from_dict()
│   ├── command_handler.py          # Parses player input → routes to action handlers
│   │                               #   (cd, ls, use, take, talk, attack, flee…)
│   │                               #   owns room_aliases dict (path → room_id)
│   ├── combat.py                   # Turn-based combat session, attack resolution,
│   │                               #   cooldowns, emits COMBAT_STARTED/FRAME_UPDATED/ENDED
│   ├── events.py                   # EventType enum + EventBus (pub/sub message bus)
│   ├── data_loader.py              # Loads all YAML files into dicts; caches results
│   ├── save.py                     # Save/load JSON to saves/ using player.to_dict()
│   ├── rarity.py                   # Single RARITIES dict (color, emoji, sort order per tier)
│   │
│   └── ui/
│       ├── textual_ui.py           # Textual TUI app — panels, input, event subscriptions,
│       │                           #   combat UI, inventory display, game-over screen
│       ├── ui_interface.py         # UIProtocol — interface contract between engine and UI
│       ├── ui.css                  # Textual CSS styles for all panels and states
│       ├── view_builder.py         # Converts raw backend objects → ViewModels (pure dicts)
│       │                           #   owns ROOM_ID_TO_PATH display map
│       └── view_models.py          # Frozen dataclasses: StatsView, InventoryView,
│                                   #   RoomView, CombatView, AttackView, EnemyView
│
├── data/                           # All game content — edit YAML to change the game
│   ├── classes.yaml                # Class definitions: stats, attacks list, display block,
│   │                               #   loot_preference tags, starter weapon
│   ├── attacks.yml                 # Every attack: damage bonus, accuracy, cooldown, effects
│   ├── abilities.yaml              # Passive/active ability definitions
│   │
│   ├── rooms/                      # One .yml per room
│   │   ├── home_grove.yml          # Starting area (/home)
│   │   ├── var_dungeon.yml         # /var — Memory Banks
│   │   ├── bin_armory.yml          # /bin — The Armory
│   │   ├── usr_lib_arcane.yml      # /usr/lib — Arcane Library
│   │   ├── mnt_forest.yml          # /mnt — Mount Forest (hub to optional areas)
│   │   ├── tmp_hidden_chamber.yml  # /tmp — The Forge (hidden)
│   │   ├── etc_hidden_configs.yml  # /etc — Hidden Configs
│   │   ├── dev_null_void.yml       # /dev/null — The Void
│   │   ├── proc_secrets.yml        # /proc — Process Secrets (hidden)
│   │   ├── ghost_hidden.yml        # Hidden ghost area
│   │   ├── mirror_sector.yml       # /proc/self — Sudo Trial arena
│   │   ├── opt_mage_tower.yml      # /opt — Mage Tower (Weaver class-restricted)
│   │   ├── srv_warrior_tomb.yml    # /srv — Warrior Tomb (Guardian class-restricted)
│   │   ├── usr_share_games.yml     # Easter egg path
│   │   ├── cowsay_secret.yml       # Great ASCII Bovine sanctuary
│   │   ├── archive.yml             # /archive — lore room
│   │   ├── deprecated_dir.yml      # /deprecated — legacy content
│   │   ├── root.yml                # /root
│   │   └── core.yml                # /boot/kernel — Final boss room
│   │
│   ├── items/                      # Items split by category
│   │   ├── weapons.yaml            # Swords, staves, shields — damage, allowed_classes
│   │   ├── armor.yaml              # Armor pieces — defense, class restrictions
│   │   ├── consumables.yaml        # Health packets, buffs — combat_effects block
│   │   ├── keys.yaml               # Keys — unlocks: [room_id] list
│   │   ├── crafting.yaml           # Crafting materials for Forge Master recipes
│   │   ├── trinkets.yaml           # Passive effect items
│   │   └── lore_fragments.yaml     # Readable files that reveal story
│   │
│   ├── enemies/                    # One .yml per enemy
│   │   ├── daemon_overlord.sys.yml # Final boss
│   │   ├── corruption_lord.exe.yml # Sub-boss
│   │   ├── shadow_process.yml      # Sudo Trial enemy (mirror of player)
│   │   └── ...                     # 15 total enemies
│   │
│   └── npcs/                       # One .yml per NPC
│       ├── echo.usr.yml            # ECHO — tutorial guide
│       ├── firewall_knight.iptables.yml
│       ├── forge_master.tmp.yml    # Crafting NPC
│       ├── null_whisper.void.yml   # Lore NPC
│       ├── librarian.bin.yml
│       ├── great_ascii_bovine.cow.yml  # Easter egg NPC
│       └── ...                     # 15 total NPCs
│
├── config/
│   ├── settings.py                 # Active config (gitignored)
│   ├── settings.example.py         # Template — copy to settings.py
│   └── dev_config.py               # DEV_MODE, DEBUG_MODE, SKIP_INTRO flags
│
├── docs/
│   └── TODO.md                     # Master task list (bugs, architecture, features)
│
├── storyHFSE/                      # Narrative design documents
│   ├── world.md                    # World lore and zone descriptions
│   ├── archetypes_entities.md      # NPC/enemy character bibles
│   ├── item_registry.md            # Canonical item list and story roles
│   └── env_logs.md                 # In-world log files and lore text
│
├── utils/
│   ├── debug_tools.py              # debug_log() helper used throughout codebase
│   ├── particle_animation.py       # Startup animation
│   └── typewriter.py               # Typewriter text effect
│
└── saves/                          # Auto-created — JSON save files per run
```

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- Inspired by classic text adventures, Zork, and Unix philosophy
- **[Rich](https://github.com/Textualize/rich)** - Terminal formatting and UI
- **[Textual](https://github.com/Textualize/textual)** - TUI framework
- **[PyYAML](https://pyyaml.org/)** - Data loading
- **cowsay** - For inspiring the easter egg

---

## 🎮 Credits

**Game Design & Development**: NoHudd
**Narrative Design**: The Great Kernel Panic storyline
**Special Thanks**: To all sysadmins who've faced kernel panics

---

## 🚀 Roadmap

- [x] Core gameplay loop with command-line interface
- [x] Turn-based combat system
- [x] Harvesting Cycles (XP) progression
- [x] Item persistence and rarity system
- [x] Story flags and narrative progression
- [x] 13 NPCs with dialogues and lore
- [x] 3 character classes with unique abilities
- [x] Environmental effects and zone mechanics
- [ ] Phase 5: Easter egg implementation (.moo → bovine → milk)
- [ ] Phase 6: Multiple class-specific endings
- [ ] Phase 7: Final testing and polish
- [ ] Crafting system with Forge Master recipes
- [ ] Achievements and statistics tracking

---

**Welcome to the corrupted filesystem, Sysadmin Spirit.**
**The Great Kernel Panic awaits. Will you restore order... or choose a different path?**

```
 ________________________________________
/                                        \
| The disk is clicking. Can you hear    |
| it? It sounds like teeth. 010101.     |
\                                        /
 ----------------------------------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
```

*Type `./start.sh` (Mac/Linux) or `start.bat` (Windows) to begin your journey.*
