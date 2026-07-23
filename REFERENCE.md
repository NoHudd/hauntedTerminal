# Haunted Terminal — Reference

Full command list, classes, mechanics, and tips. The game teaches most of this
as you play (`help` in-game is always up to date) — this is here if you want
to look something up.

## Commands

### Navigation
- `ls` — list items, NPCs, and exits in current directory
- `ls -a` — reveal hidden files and directories
- `cd [path]` — move to a different directory (`cd /var` or `cd var`)
- `pwd` — show current directory
- `map` — show available locations
- `find` — search for items, NPCs, or rooms

### Interaction
- `cat [filename]` — read file contents (lore fragments, logs, etc.)
- `take [item]` — pick up an item
- `drop [item]` — remove an item from inventory
- `use [item]` — use a consumable
- `equip [weapon]` — equip a weapon for combat
- `examine [item]` — inspect an item's properties
- `talk [npc]` — speak with NPCs for hints and lore

### Combat
Combat opens in Selection Mode automatically — press `1`-`9` to attack, `0` to
flee. Press `TAB` to type `use [item]` instead, `TAB` again to return to
Selection Mode.

### System
- `inventory` / `inv` — view your items
- `keys` — show key progression system
- `ps` — show running processes
- `shortcuts` — list item shortcuts and typing tips
- `help` — display available commands
- `save` — save your progress
- `quit` / `exit` — exit the game (offers to save)

## The Filesystem

- **`/dev/null` — The Void**: where you awakened. Void pull drains HP without Null-Void Cloak.
- **`/home/lost+found` — The Graveyard**: orphaned files and broken symlinks. Find your `.bash_profile`.
- **`/bin` — The Armory**: sacred command icons (cp, mv, rm). The Librarian guides you to lore.
- **`/var/log` — The Memory Banks**: crash logs and error files. Discover the Creator's Typo.
- **`/etc/iptables` — The Kernel Gate**: Firewall Knight blocks passage. Requires chmod_key.
- **`/boot/kernel` — The Core**: final confrontation with the Daemon Overlord.
- **`/proc/self` — The Mirror Sector**: Sudo Trial — fight your Shadow Process.
- **`/usr/share/games/cowsay/.secret/` — The Bovine Sanctuary**: easter egg location.

## Character Classes

### Guardian (Tank)
- **Base Stats**: 120 HP, 10 DMG
- **Starter Weapon**: Segmentation Fault Shield
- **Playstyle**: high survivability, defensive abilities
- **Attacks**: Strike, Power Strike, Shield Bash

### Weaver (Mage)
- **Base Stats**: 90 HP, 15 DMG
- **Starter Weapon**: Null Pointer
- **Playstyle**: high damage output, glass cannon
- **Attacks**: Arcane Bolt, Fireball, Frost Nova

### Shaman (Hybrid)
- **Base Stats**: 100 HP, 8 DMG
- **Starter Weapon**: Daemon Whisper
- **Playstyle**: balanced, healing capabilities
- **Attacks**: Nature Strike, Ancient Fury, Healing Strike

## Game Mechanics

### Harvesting Cycles (XP)
- Defeat enemies to gain harvesting cycles
- Base: 50 cycles per enemy, 150 for bosses
- Level up: +10 Max HP, +2 DMG
- Exponential scaling: each level requires 1.5x more cycles

### Item Persistence
- **Persistent items** survive death (weapons, armor, keys)
- **Ephemeral items** are lost on death (consumables, temporary buffs)
- Check item descriptions for persistence type

### Story Progression
- Read lore fragments to unlock story flags
- Story flags gate access to special areas (Mirror Sector, Bovine Sanctuary)
- Multiple endings based on class and choices

### Rarity System
Items spawn based on directory depth:
- **`/home`, `/var`**: common items dominate
- **`/bin`, `/etc`, `/usr`**: uncommon and rare items
- **`/dev`**: epic items spawn
- **`/root`**: legendary items only

## Tips

1. **Use `ls -a`** to reveal hidden files and secret paths
2. **Read everything** — lore fragments contain crucial story beats
3. **Talk to NPCs** — they provide hints about item locations and story progression
4. **Save often** — the filesystem is dangerous
5. **Explore thoroughly** — hidden rooms contain powerful items
6. **Choose items wisely** — ephemeral items don't persist through death

## What You'll Learn

- Command-line navigation: `cd`, `ls`, `ls -a`, `pwd`, `cat`, `find`
- File system structure: understanding the Unix directory hierarchy
- Hidden files: the significance of dot files (`.bash_profile`, `.moo`)
- System concepts: processes, daemons, `/dev/null`, `/proc`, init, permissions
- Problem-solving through exploration and reading

## Achievements & Challenges

- Complete the Sudo Trial and earn the sudo_privileges_badge
- Find all 6 lore fragments to understand the full story
- Discover the Great ASCII Bovine easter egg
- Defeat the Daemon Overlord and choose your ending
- Reach max level through harvesting cycles

## Development

### Debug Mode

Copy `config/settings.example.py` to `config/settings.py` and flip:

```python
DEV_MODE = True
DEBUG_MODE = True
SKIP_INTRO = True
```

Contributors also need the dev tooling (pytest, mypy, ruff):

```bash
pip install -r requirements-dev.txt
```

### Project Structure

```
main.py        # entry point → src.game_engine.main
src/           # game logic (runtime): engine, world, player, combat, commands/, ui/, scene/
engine/        # typed content schema + validation + headless test driver
data/          # all game content as YAML — rooms/ enemies/ npcs/ items/ + classes/attacks/abilities
assets/        # pixel-art sprites and backdrops (PNG)
sim/           # difficulty simulation harness
config/        # dev settings (settings.py gitignored)
tests/ · utils/
```
