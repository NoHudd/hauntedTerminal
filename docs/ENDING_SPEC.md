# Ending Sequence — Spec

Defeating the Daemon Overlord currently dumps the (good, per-class) epilogue and
instantly overwrites it. With the output-append fix the text now survives, but the
finale still deserves: pacing, a visual beat, a run recap, and a proper "play again"
that lets you pick a new class/difficulty.

## Context

- `src/command_handler.py: win_game()` holds three per-class endings (Guardian
  RESTORE / Weaver REWRITE / Shaman RECONCILE) and sets `_game_won` +
  `_in_game_over_mode`. It writes the epilogue + "The system is clean." directly.
- The post-game `n` currently restarts WITHOUT re-offering difficulty/class.
- No lifetime counters exist for enemies defeated / items found.

## Goals

1. **Backend emits, frontend performs.** `win_game()` stops printing; it emits one
   `GAME_WON` event carrying everything. The UI owns the cinematic. (Headless/basic
   frontends can just join the sections and print — same data.)
2. **Paced reveal** of the epilogue, skippable.
3. **Scene finale beat** — corruption visibly lifts. No new art.
4. **Run-stats recap** card at the end.
5. **New game = new choices** — post-victory and post-death `n` goes through the
   difficulty picker → class picker → name flow.

## Design

### GAME_WON event (src/events.py)

```python
GAME_WON = auto()
# Data: {
#   "ending_id": "restore" | "rewrite" | "reconcile",
#   "sections": [str, ...],      # epilogue split on blank-line boundaries
#   "stats": {                    # run recap, all ints/strs
#       "level": int, "cycles": int, "kills": int, "items_found": int,
#       "difficulty": str, "ending": str, "player_name": str, "player_class": str,
#   },
# }
```

`win_game()`: builds sections by splitting the existing ending text on `\n\n`,
gathers stats, emits `GAME_WON`, sets `_game_won` / `_in_game_over_mode` as today.
Engine-side printing is removed entirely; the HeadlessUI subscribes to `GAME_WON`
and appends the joined sections to its output_log, so tests/sim still see the text.

### Run-stats tracking (src/player.py + src/command_handler.py + src/save.py)

- `Player.__init__`: `self.run_stats = {"kills": 0, "items_found": 0}`.
- `command_handler._award_enemy_drops` (runs once per ENEMY_DEFEATED):
  `self.player.run_stats["kills"] += 1`.
- `take` command (on successful pickup): `ctx.player.run_stats["items_found"] += 1`.
- Save/load: serialize as `runStats` (camelCase, save JSON only); default `{}` on
  old saves (`data.get("runStats", ...)`).
- `difficulty` for the recap: `src.difficulty.current_mode()` at win time.

### UI finale (src/ui/textual_ui.py — `_on_game_won`)

Timer-chained beats (reduce_motion ⇒ everything at once, no timers):

1. t=0: scene finale starts (below); output panel clears; section 1 renders via
   the existing typewriter.
2. Each further section at +2.5 s.
3. After the last section (+2.5 s): the recap card —
   ```
   ── YOUR RUN ──────────────────────────
   TEST · Guardian · ending: RESTORE
   Level 4 · 337 cycles harvested
   23 enemies purged · 17 items recovered
   difficulty: medium
   ──────────────────────────────────────
   [n] new run · [q] quit
   ```
   (one Rich-markup block appended to the output panel).
4. Skip: any keypress during the chain cancels pending timers and renders all
   remaining sections + recap immediately (same convention as the intro typewriter).

### Scene finale beat (src/ui/panels/scene_view.py — `play_finale()`)

Explore/battle-agnostic: uses the current room's backdrop.
- Border title → `✨ SYSTEM CLEAN`, subtitle cleared.
- Brightening: re-render the backdrop ~6 steps over ~3 s, brightness 0.62 → 1.15
  (PIL `ImageEnhance.Brightness` on the cached backdrop; each step one render —
  reuses the bob/effect timer plumbing).
- Enemy sprite: already vanished via `defeat_enemy()`.
- reduce_motion: single render at full brightness.
- Steady state after the beat: bright backdrop stays until a new game starts.

### New game routes through the pickers (src/command_handler.py / game_engine)

The post-game input handler (`_in_game_over_mode`, key `n`) currently shortcuts to
a restart with the previous class/difficulty. Change: `n` triggers the SAME path as
main-menu "New Game" (`_start_new_game`) — difficulty picker → class picker → name.
Applies to both victory and death screens. (State machine already allows
GAME_OVER → MENU → WAITING_FOR_DIFFICULTY; route through it so pickers fire off the
normal UI_STATE_CHANGED events.)

## Testing

- `win_game()` emits GAME_WON with sections >= 3 and complete stats dict (headless).
- Counters: kill an enemy headlessly → kills == 1; take an item → items_found == 1.
- Save round-trip: run_stats survive save → load (camelCase key in JSON).
- Post-game `n` lands in `waiting_for_difficulty` state (headless, via state_manager).
- UI pacing/scene beat: manual playtest (win via a fresh run or a dev shortcut —
  suggest temporarily placing the overlord at low HP via difficulty easy).

## Out of scope

- New ending art (backdrop brightening only).
- Multiple endings per class / ending selection.
- Leaderboards, persistent meta-stats across runs.
