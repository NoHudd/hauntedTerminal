# Haunted Terminal — Reference

Full command list, classes, mechanics, and tips. The game teaches most of this
as you play (`help` in-game is always up to date, and `man <command>` explains
the real Unix ones) — this is here if you want to look something up.

## Commands

### Real Unix commands

These behave like their shell counterparts. `man <command>` describes what each
one does in an actual terminal.

- `ls` — list this directory: its subdirectories, files, processes and hostiles
- `ls -a` — also show `.`, `..` and hidden entries, revealing hidden directories
- `ls -l` — long format, with a permission column (`dr--------` means sealed)
- `cd [path]` — change directory. Absolute (`cd /var`), relative (`cd games`),
  `cd ..` for the parent, `cd` alone for home
- `pwd` — print the directory you are in
- `cat [file]` — read a file
- `grep [word] [file]` — print only the lines of a file that contain a word
- `kill [PID]` — end a process (find its PID with `ps`)
- `tree` — show the filesystem you have discovered so far
- `find [path] -name [pattern]` — search for a file
- `ps` — list running processes
- `whoami` — your name, class and level
- `echo [text]`, `clear`, `man [command]`

### Commands of this world

- `take [item]` / `drop [item]` — pick up or put down an item
- `use [item]` — use a consumable
- `equip [weapon]` — ready a weapon or a piece of armor
- `examine [item]` — inspect an item's properties
- `talk [npc]` — speak with a process for hints and lore
- `attack [enemy]` — start a fight
- `inventory` / `inv` — view your items
- `journal` — story memories you have restored
- `keys` — the keys you hold and the directories they open
- `hint` — a nudge toward this room's flag; ask again for the exact command
- `shortcuts` — item shortcuts and typing tips
- `save` — save your progress to this run's slot
- `menu` — back to the title menu (save first, or leave without saving)
- `quit` / `exit` — exit the game (offers to save). Ctrl+Q, Ctrl+C and ESC do
  the same thing; mid-fight they offer keep fighting / main menu / quit, without saving

### Combat

Combat opens in Selection Mode automatically — press `1`-`9` to attack, `0` to
flee. Press `TAB` to type `use [item]` instead, `TAB` again to return to
Selection Mode.

## The Filesystem

The rooms form a real directory tree. You may `cd` to any path you have
permission to reach — you are not limited to neighbours. Permission is needed on
every directory along the way, so a locked `/usr` also hides `/usr/games`.

```
/                       Root
├── bin/                The Armory — sacred command icons (cp, mv, rm)
├── boot/               The Core — the Daemon Overlord waits here   [11 flags]
├── dev/                The Void — where deleted data accumulates   [sudo badge]
├── etc/                The Kernel Gate — the Firewall Knight        [chmod_key]
├── home/               The Graveyard — where you wake up
├── mnt/                Mount Forest — mounted drives
├── opt/                Mage Tower — the Weaver's trial     [opt_key, hidden]
├── proc/               Process Secrets
│   └── self/           The Mirror Sector — the Sudo Trial            [hidden]
├── root/               Hidden Directory — ancient knowledge      [system_badge]
├── srv/                Warrior Tomb — the Guardian's trial           [opt_key]
├── usr/                The Arcane Library                            [lib_key]
│   └── games/          The Game Gallery
│       └── cowsay/     The Bovine Sanctuary — easter egg             [hidden]
└── var/                The Memory Banks — crash logs, the Creator's Typo
    ├── backups/        The Archive                                   [hidden]
    └── tmp/            Deprecated Directory
```

Hidden directories do not appear until you find them. `ls -a` in the parent is
the usual way; `ps` in Mount Forest also reveals one. A locked
directory does not appear at all until you hold its key.

## Character Classes

### Guardian (Tank)
- **Base Stats**: 120 HP, 10 DMG
- **Starter Weapon**: Segmentation Fault Shield
- **Playstyle**: high survivability, defensive abilities
- **Attacks**: Strike (+5), Power Strike (+19, 2t cooldown), Shield Bash (+10, 3t)

### Weaver (Mage)
- **Base Stats**: 90 HP, 15 DMG
- **Starter Weapon**: Null Pointer
- **Playstyle**: high damage output, glass cannon
- **Attacks**: Arcane Bolt (+6), Fireball (+18, 2t), Frost Nova (+12, 3t)

### Shaman (Hybrid)
- **Base Stats**: 120 HP, 10 DMG
- **Starter Weapon**: Daemon Whisper
- **Playstyle**: balanced, healing capabilities
- **Attacks**: Nature Strike (+6), Ancient Fury (+17, 2t), Healing Strike (+8, 3t)

Attack damage is your total damage plus the attack's bonus. Each attack also has
an accuracy roll, so a miss is possible.

## Game Mechanics

### Harvesting Cycles (XP)
- Defeat enemies to gain harvesting cycles
- Each enemy awards its own value, from 15 for the weakest to 150 for the
  Daemon Overlord; bosses award triple
- Level up: +10 Max HP, +2 DMG
- Each level costs 1.5x the previous one (100, 150, 225, …). There is no cap
- Your difficulty setting scales the award

### Flags
- Every directory hides a flag (`FLAG{...}`): 13 in the main tree, 5 more in
  secret directories
- Capture one by reading its file with `cat`, searching a long file with
  `grep FLAG [file]`, or ending a rogue process with `kill [PID]`
- `tree` marks the rooms whose flag you hold with ⚑; `journal` counts them
- Hold 11 main flags and `/boot` opens. Capturing a flag saves a checkpoint
- Stuck in a room? `hint` nudges you, and asking again gives the exact command

### Keys
- Keys are earned, never found lying around: the `/mnt` flag hands you
  `lib_key` (opens `/usr`), the `/var` flag `chmod_key` (opens `/etc`), and the
  `/usr` flag `opt_key` (opens `/srv` and a secret)
- The `sudo_privileges_badge`, earned by beating your Shadow Process in
  `/proc/self`, opens `/dev`; the `system_badge` from the Daemon Overlord opens
  `/root`
- A locked directory stays hidden until you hold its key; walk in with the key
  and it opens
- The chain always reaches 11 flags, so every run can be won

### Item Persistence
- **Persistent items** survive death (weapons, armor, keys)
- **Ephemeral items** are lost on death (consumables, temporary buffs)
- Check item descriptions for persistence type

### Story Progression
- Read lore fragments with `cat` to unlock story flags
- Reading one auto-saves your progress
- Your ending is determined by your class

### Rarity
Items spawn by rarity, weighted by your class and by the directory they are in.
Deeper and more dangerous directories skew toward better loot; `/home` and `/var`
lean common, `/dev` favours epic, and `/` can produce legendaries.

## Tips

1. **Use `ls -a`** to reveal hidden directories
2. **Read everything** — lore fragments contain crucial story beats
3. **Talk to NPCs** — they provide hints about item locations and progression
4. **Save often** — the filesystem is dangerous
5. **`man` anything** you do not recognise
6. **Choose items wisely** — ephemeral items don't persist through death

## What You'll Learn

- Navigation: `cd` with absolute and relative paths, `..`, `.`, `pwd`, `ls`
- Listing: `ls -a` for hidden entries, `ls -l` for permissions
- Filesystem structure: what `/bin`, `/etc`, `/var`, `/usr`, `/proc`, `/dev`,
  `/boot`, `/tmp` and `/root` are actually for
- Hidden files: the significance of dot files (`.bash_profile`, `.moo`)
- Permissions: why you need access to a directory *and* everything above it
- Processes: PIDs, PPIDs, `init` as PID 1, daemons and orphans
- Reading documentation with `man`

## Achievements & Challenges

- Complete the Sudo Trial in `/proc/self` and earn the sudo_privileges_badge
- Find all 6 lore fragments to understand the full story
- Discover the Great ASCII Bovine easter egg
- Defeat the Daemon Overlord in `/boot`
- Reach the Archive and the Hidden Directory

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
make check          # ruff + mypy + pytest + content validation
```

### Project Structure

```
main.py        # entry point → src.game_engine.main
src/           # the running game: engine, world, player, combat, commands/, ui/, scene/
engine/        # typed content schema + validation + headless test driver
data/          # all game content as YAML — rooms/ enemies/ npcs/ items/ + classes/attacks/abilities
assets/        # pixel-art sprites and backdrops (PNG)
sim/           # difficulty simulation harness
config/        # dev settings (settings.py gitignored)
tests/ · utils/
```

Adding content is a matter of dropping a YAML file into the matching `data/`
directory and running `python -m engine.validate data`, which fails loudly on a
dangling reference, a duplicate path, or a room whose parent directory does not
exist.
