# Changelog

Versions follow `0.MINOR.PATCH` while the game is in playtesting: a new MINOR
for each release to `main`, a PATCH for a fix-only release. The version shows on
the title screen and on the first line of `debug.log`, with the git commit next
to it, so a screenshot or log names the build it came from.

## v0.2.0 — unreleased

### ⚠ Saves
Saves from v0.1 do not load. The flag hunt changed what a save holds; start a
new game.

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
- The class cards list each class's three moves, and the fight menu says which
  moves heal you or weaken the enemy. When your HP runs low, the fight tells
  you which key heals.

### Easier to type
- Forgiving item names, Tab completion, and "Did you mean…" on typos.
- Combat opens in Selection Mode: number keys attack, `0` flees.
- Esc cancels a half-typed line instead of quitting.

### Balance
- Difficulty re-tuned against a simulator of full runs. Target win rates are
  about 95% easy, 83% medium and 68% hard. The Weaver is still the weakest class.

### Fixes
- The Inventory panel now updates during a fight (used items used to stay
  listed until the fight ended).
- The Legacy Backup really revives you, once.
- The Shaman's class card showed 100 HP and 8 damage; it really has 120 and 10.
  Card numbers now come from the real stats.
- The game-over screen no longer scrolls or shows stray markup, and r/n/q work.
- Saves keep your armor, status effects and difficulty.
- Hidden files show their leading dot, and Tab completes them.
- The Windows launcher is more robust, and players no longer install developer
  tools.

## v0.1-playtest — 2026-07-10

The first playtest release: explore the haunted filesystem with real Unix
commands, fight in Pokémon-style battles, pick a class and a difficulty.
