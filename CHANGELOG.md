# Changelog

Versions follow `0.MINOR.PATCH` while the game is in playtesting: a new MINOR
for each release to `main`, a PATCH for a fix-only release. The version shows on
the title screen and on the first line of `debug.log` (with the git commit next
to it when run from a git checkout), so a screenshot or log names the build it
came from.

## v0.2.0 — 2026-09-30

### ⚠ Saves
Saves from v0.1 do not load. The flag hunt changed what a save holds; start a
new game.

### New: main menu and save slots
- The title menu has **SETTINGS** (palette, text speed, reduce motion, hints),
  now arrow-driven: ↑/↓ picks a row, ←/→ changes it. Ctrl+P opens the same screen in-game.
- Every run has its own save slot (up to 9). **LOAD GAME** lists them with the
  class, difficulty, level and where you are; Enter continues, `d` deletes.
  Beaten runs are marked ✓. When all 9 are taken, NEW GAME asks which run to replace.
- Saves from the old single pool become one slot per hero; the original files
  are kept in `saves/legacy/`.
- Leave a run for the main menu: `menu`, or **Save & main menu** / **Main menu
  without saving** on the quit chooser (Ctrl+Q, Ctrl+C, `quit`). The game-over screen is now r (restore this
  run) / m (main menu) / q (quit).
- Fixed: Ctrl+Q or `quit` during a fight said "command not found"; it now asks
  whether to keep fighting, go to the menu or quit.

### New: capture the flag
- Every directory hides a flag: 13 in the main tree, 5 more in secret
  directories. Read one with `cat`, search a huge log with `grep`, or find a
  rogue process with `ps` and end it with `kill`.
- `/boot` (the final boss) opens once you hold 11 flags. `tree` and `journal`
  count them, and capturing one saves a checkpoint.
- Stuck in a room? `hint` nudges you, and asking again gives the exact command.
  Echo teaches each new technique the first time you need it, and NPCs drop clues.
- New commands: `grep` (with `-i` and `-n`) and `kill`.
- The run recap shows your flags and a rank; capturing everything unlocks an
  extra epilogue.

### New: keys are earned
- Keys are no longer scattered at random. The `/mnt`, `/var` and `/usr` flags
  hand you the keys to `/usr`, `/etc` and `/srv`; bosses drop the rest. Every run
  can be won.
- A locked directory stays hidden until you hold its key, so the map unfolds as
  you learn. `keys` lists what you hold.
- `/opt` and `/srv` are open to every class, with a damage bonus for the class
  whose trial it is.

### Tutorial and story
- The opening and the tutorial explain the goal: capture flags, earn keys,
  open `/boot`. Skipping the tutorial still tells you.
- The tutorial now teaches `ls -a`, `cat`, `ps` and `pwd`, gives you starter
  armor before the first fight, and pins Echo's current instruction above the
  input. Reading a memory file restores a memory and saves a checkpoint.
- NPC dialogue changes with what you have done.
- Picking up an item shows what it is, right under "Added … to your inventory".
- A Character panel under Stats shows your class's model and the weapon and
  armor you have on, with their numbers; an empty slot says how to fill it.
- The class cards list each class's three moves, and the fight menu says which
  moves heal you or weaken the enemy. When your HP runs low (and in-game hints
  are on), the fight tells you which key heals.

### Easier to type
- Forgiving item names, Tab completion, and "Did you mean…" on typos.
- Combat opens in Selection Mode: number keys attack, `0` flees.
- Esc cancels a half-typed line instead of quitting.
- Tab after `cd` completes the directories you can see (it completed nothing
  before), and never a hidden or still-locked one.
- Typing `equip`, `take`, `cd` and other exploring commands in a fight says
  they work once the fight is over, instead of "command not found".

### Look and feel
- The version is on the title screen and on the first line of `debug.log`.
- Seven rooms have their own backdrop art: the Archive, the Deprecated
  Directory, `/root`, `/opt`, `/proc`, `/srv` and `/usr`.
- One icon per item type in `ls`, `take`, `examine` and the inventory.
- Cleared rooms get a ✓ in `ls`, the exits list and `tree` (`map` still works).
- NPC sprites fill their box like everyone else's instead of shrinking.
- F12 opens the logs; debug logging stays out of the terminal, and each launch
  starts a fresh log.

### Loot and saves
- Gear can't drop as a second copy of something you already took.
- Epic and legendary gear starts locked away instead of lying in `/`.
- Loading an old save removes a stray copy of a key a flag now hands out.
- The autosave pool is capped, so the saves folder no longer grows forever.

### Balance
- Capturing a flag restores you to full HP. Most deaths came from wear across
  several fights, so runs are now much easier: the run simulator wins nearly
  every run in every mode, and the earlier targets (about 95% easy, 83% medium,
  68% hard) no longer apply. Harder modes still mean tougher, longer fights.
- The Weaver is still the weakest class.

### Fixes
- The Inventory panel now updates during a fight (used items used to stay
  listed until the fight ended).
- The Legacy Backup really revives you, once, then tells you it's spent and how
  many are left. Trying to `use` one in a fight explains that it works on its own.
- The Inventory panel shows how much each healing item heals, and every attack
  in the fight menu has an icon for its type (⚔ physical, ✨ magical, 🌿 nature).
- `find /dev -name null` no longer names `/dev` before its door is revealed.
- The Shaman's class card showed 100 HP and 8 damage; it really has 120 and 10.
  Card numbers now come from the real stats.
- The game-over screen no longer scrolls or shows stray markup, r/n/q work, and
  it appears only when you actually die.
- Saves keep your armor, status effects and difficulty, and defeated bosses no
  longer come back to life (with fresh drops) when you load.
- Hidden files show their leading dot, and Tab completes them.
- The tutorial fight no longer ambushes players who skipped the tutorial, and
  fleeing it no longer breaks the tutorial.
- `talk` no longer crashes, and stray markup no longer shows up as text.
- New installs start in player mode (some testers got the developer settings).
- The Windows launcher is more robust, and players no longer install developer
  tools or packages that fail to build on new Python versions.

## v0.1-playtest — 2026-07-10

The first playtest release: explore the haunted filesystem with real Unix
commands, fight in Pokémon-style battles, pick a class and a difficulty.
