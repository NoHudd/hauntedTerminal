# HFSE TUI/UX Redesign — Design

**Date:** 2026-07-05
**Status:** Stage A + B implemented (commit `464841c` + follow-ups); Stage C (reactive 4b) pending live TUI verification. See "Implementation status" at end.

## Context

HFSE is a terminal RPG (Textual TUI) whose real purpose is to teach Unix
command-line skills to people who don't know them, while being fun. A review of
the live TUI (class-select, exploration, and full combat flow) surfaced that the
game only hand-holds during *combat* — during *exploration*, where a novice is
most lost, there's no "what can I even type?" affordance. A new player sees
`daemon_whisper - An echo of a terminated process` with no idea they can `take`
it or `cd /var` to leave.

The visible symptoms all trace back to that missing designed experience:
- **Dead space:** the main output area is ~70–85% empty black in exploration and
  combat; the game reads as a thin strip atop a void.
- **Combat clutter:** control instructions appear 3–4 times at once — the combat
  log (re-dumped on *every* enemy transition), the Stats panel "CONTROLS" block,
  the footer hotkeys, and an interrupting center modal.
- **Visual breakage:** emoji glyphs collide with adjacent text (`🛡MIKE`,
  `⚔Weapon`, `🗺Zones`, `💀Variable Daemon`); the name-tag icon doesn't match the
  class (Shaman shows a 🛡 shield); the header stays "Loading…" at class-select.
- **Weak info hierarchy:** empty sidebar placeholders during class-select; the
  Combat panel shows "No enemies nearby" clutter when idle.

**What's already good** (keep): the room breadcrumb strip + exits, color-coded
class cards, colored HP bars (red/yellow/green), the contextual footer hotkeys,
the two-column layout bones, and the existing fading milestone tutorial
(`tutorial_state`: `first_ls`→step2, `took_weapon`→step3, equip→step4,
navigation→complete).

**Intended outcome:** a Unix-novice can sit down, always know what they can do,
learn the core verbs (`ls`, `cd`, `cat`, `take`, `use`, `equip`, `attack`)
naturally, and never hit a "what now?" void — while a player who wants pure
immersion can switch the guidance off.

## Decisions (locked)

- **Guidance model:** BOTH an enhanced onboarding tutorial AND subtle always-on
  affordances (not one or the other).
- **Affordance form:** inline, dim command hints in the room output itself
  (no new panel) — teaches *thing + command* in context.
- **User control:** a Settings toggle labeled **"In-game hints"** (`hints`
  boolean in `SettingsManager`), **on by default**. Off = today's clean,
  immersive output.
- **Combat SELECTION MODE modal:** show **first-time only**, then never again.
- Immersion-vs-guidance tension is resolved by user choice, not by picking a side.

## Design

### 1. Inline affordances ("In-game hints", default on)

When hints are on, exploration output pairs each interactable with the exact
command, dimmed so it never competes with the story:

```
The Graveyard        exits: /var · /mnt · /

FILES
  bash_profile        A configuration file — may restore memories
                        → cat bash_profile
  daemon_whisper      An echo of a terminated process (+7 DMG)
                        → take daemon_whisper

WHERE YOU CAN GO
  → cd /var   The Memory Banks     → cd /mnt   The Forest     → cd /   Root
```

- Hints off → the current clean list (no `→` lines).
- Combat already surfaces its verbs via the footer hotkeys; hints there stay as
  the footer only (see §3), not re-injected into the log.
- Implementation: room rendering (`ViewBuilder.build_room_view` +
  `command_handler.display_location` / `LsCommand`) reads the `hints` setting and
  appends dim hint lines. Single shared renderer so the format is consistent.

### 2. Kill the dead space

- Output panel grows to fill its column (currently constrained); sidebar panels
  size to content instead of leaving large fixed gaps between Stats and Combat.
- With hints on, inline hints naturally use more of the vertical space; with them
  off, the layout still fills rather than floating a strip at the top.
- Combat log fills the same way — no central void during a fight.
- CSS-driven (`src/ui/ui.css`) plus panel sizing; verified live per change.

### 3. Combat clutter → one source of truth

- **Controls live in exactly one place: the contextual footer hotkeys** (already
  present: `1 Ancient Fury · 2 Healing Strike · 3 Nature Strike`).
- **Stop re-dumping** the "COMBAT CONTROLS" + "QUICK ATTACKS" block into the log
  on every enemy transition. Show attack options once at combat start (and only
  when hints are on); subsequent turns/enemies show only outcomes.
- **Remove** the redundant "CONTROLS" block from the Stats panel.
- **SELECTION MODE modal:** first-time-only. Track a `seen_selection_mode` flag
  in `SettingsManager` (user-level, so it survives new games — not per-save
  `tutorial_state`); after the first time it never shows again. TAB still toggles
  selection mode silently.

### 4. Visual polish

- **Glyph spacing:** one shared helper guarantees a space after every emoji
  (`🛡 MIKE`, `⚔ Weapon`, `💀 Variable Daemon`). Apply across panels + strips.
- **Class-correct icon:** map class → glyph (guardian 🛡, weaver ✨, shaman 🌿)
  and use it for the name tag in the Stats panel, not a hardcoded shield.
- **Header state:** show a neutral/title label at class-select instead of the
  stale "Loading…".
- Trim inter-panel vertical padding for a tighter, intentional look.

### 5. Info hierarchy

- **Combat panel** collapses/hides when not in combat (removes idle
  "No enemies nearby" clutter and reclaims space).
- **Sidebar at class-select:** hide the placeholder panels ("Inventory will
  appear here", etc.) until a game actually starts, or show a class preview.

### 6. Tutorial enhancement

- Keep the fading milestone tutorial; align its wording/voice with the inline
  affordance format so the two don't feel like different systems.
- Ensure the first session walks the full core loop: `ls` → `cat` → `take` →
  `equip` → `cd` → `attack`. After completion, inline hints (if on) carry the
  load so nobody is stranded later.

### 7. Reactive MVVM (Phase 4b) tie-in

Where these changes already touch rendering — room view with affordances, combat
panel visibility, stats/name icon — do the deferred 4b work *there*: make
`ViewBuilder.build_*` take immutable snapshots instead of reaching into live
`world`/`player`/`combat_system` (`view_builder.py:65,133-164,296`), move
`ROOM_ID_TO_PATH` (`view_builder.py:26-46`) out of the view layer, and bind
ViewModels to widgets via Textual `reactive`. This is done incrementally and
**verified live in the TUI by the user**, never as a blind rewrite.

## Staging

Each stage is verified live in the running TUI before moving on.

- **Stage A — Polish + dead space + combat clutter.** Lowest risk, biggest
  visible win: glyph spacing, class icon, header state, panel sizing/dead space,
  collapse idle combat panel, de-duplicate combat controls, modal first-time-only.
- **Stage B — Inline affordances + "In-game hints" setting.** Shared hint
  renderer, `hints` setting (default on) + Settings Switch, wire into room
  rendering.
- **Stage C — Tutorial pass + reactive refactor** where §7 lands.

## Testing / verification

- Headless: extend `tests/test_commands.py` so `ls`/room rendering asserts hint
  lines appear when `hints` on and are absent when off; assert combat start emits
  controls once (not per transition).
- Settings: `hints` persists through `SettingsManager` save/load (unit test).
- Live (user-driven): each stage checked in `python main.py` across class-select,
  exploration (hints on/off), and a full combat — confirming dead space is gone,
  no glyph collisions, controls appear once, modal shows only the first time.

## Non-goals

- No teardown of the working layout, event bus, or combat logic.

## Implementation status

Verified against the code (2026-07-05):

**Stage A — Polish + dead space + combat clutter — SHIPPED** (commit `464841c`,
plus VS16 mop-up):
- Combat de-dup: controls no longer re-dumped per enemy transition
  (`combat_panel.py`, `game_output.py`).
- Glyph fixes: main panels (`view_builder`/`view_models`) carry no colliding
  emoji; the 19 remaining `U+FE0F` variation selectors across 7 source files
  were stripped so terminals render single-width (no overlap).
- Stats panel controls block removed; panel cleanup in `stats_panel.py`.

**Stage B — Inline affordances + "In-game hints" setting — SHIPPED**
(commit `464841c`):
- `hints` boolean in `SettingsManager` + Settings toggle.
- Inline exploration hints wired through `commands/navigation.py`.
- `tests/test_commands.py` extended.

**Stage C — Tutorial pass + reactive 4b — PARTIAL / PENDING:**
- Done: `ROOM_ID_TO_PATH` moved out of the view layer to `src/room_paths.py`.
- Remaining (needs live TUI, do not do blind): `ViewBuilder.build_*` still take
  live `world`/`player`/`combat_system` rather than immutable snapshots; no
  Textual `reactive` widget binding; `UIProtocol` not yet synced to the real
  contract.
- No camelCase of save/render internals beyond what Phase 4a already did (the
  field-vs-id ambiguity remains out of scope).
- Payload/world serialization unchanged.
