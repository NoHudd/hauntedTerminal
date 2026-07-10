# Log Panel Improvements — Spec

**Date:** 2026-07-09
**Status:** Approved design, not yet implemented.
**Scope:** Three log improvements from the playtest notes: declutter noisy debug logs (#6),
view from session start (#8), filter by category + level (#5). Colors (#7) already exist.

## Context

- `debug_log(message, category="system")` (utils/debug_tools.py) writes
  `[time] [CATEGORY] [file:func:line] message`. It is gated only when
  `category in DEBUG_CATEGORIES and disabled`. **`"system"` is NOT in `DEBUG_CATEGORIES`, so
  default-category logs are ALWAYS emitted** under `DEBUG_MODE`. `DEBUG_CATEGORIES` = command,
  item, combat, room, player, world (each toggled by a `DEBUG_*` flag, off by default).
- `LogViewerScreen` (src/ui/screens/log_viewer.py) already color-codes by level + category and
  has a binary warnings filter (`f`). It reads the current-session file (`debug.log`, cleared
  each run by `main.py`).

---

## Part A — Declutter (#6)

**Problem:** the loudest lines log at the un-gated `system` category, so they can't be turned
off. Worst offenders (verified): `combat.py:44` `"Available attacks…"` (every combat turn),
and `game_world.py` accessors that **dump the entire `item_locations` dict every call**
(`get_items_in_room` 1016-1018, plus `get_room`, `get_enemies_in_room`, `get_npcs_in_room`).

**Fix:** recategorize the high-frequency accessor/turn logs to their real (gated-off-by-default)
category, and replace dict-dumps with counts.
- `combat.py:44` → `debug_log(..., category="combat")`.
- `game_world.py` `get_items_in_room` / `get_enemies_in_room` / `get_npcs_in_room` / `get_room`:
  - **Delete the full-dict dump** (`Full item_locations: {self.item_locations}`, line 1018) —
    never log a whole collection; log `len(...)` if anything.
  - Recategorize their remaining per-call logs to `category="world"`.
- Sweep the other per-call `[SYSTEM]` accessor logs in `game_world.py` (e.g. `Retrieved room
  data`, `Getting items in room`, `Getting NPCs in room`) → `category="world"` (or delete if
  pure noise). Do NOT recategorize one-shot lifecycle logs (init/save/restore) — they're rare.

**Result:** `DEBUG_MODE` alone is quiet; enable `DEBUG_COMBAT` / `DEBUG_WORLD` to see that detail.

**Testable (headless):** after the change, calling `world.get_items_in_room(rid)` produces no
`Full item_locations` line, and `get_attacks_for_class` logs under the `combat` category (so it
is suppressed when `DEBUG_COMBAT` is off).

---

## Part B — View from session start (#8)

`on_mount` currently loads only `lines[-100:]`, and `RichLog(max_lines=500)` caps retention, so
early-session lines are unreachable. Since `debug.log` holds only the current run:
- `on_mount`: load the **entire** file (drop the `[-100:]` slice), applying the active filter.
- `RichLog(max_lines=5000)` (was 500) so the full session is scrollable; `g`/`G` (already bound)
  jump to top/bottom. With Part A cutting volume, a normal session fits well under this.

---

## Part C — Filter by category + level (#5)

Replace the binary `_filter_active` with two cycling filters, both applied, shown in the title.

- State: `_level_filter: int` (0 = all, 1 = warnings+errors, 2 = errors-only) and
  `_category_filter: str | None` (None = all; else one of combat/command/item/room/player/
  world/system).
- Bindings: **`f`** cycles level (all → warn+err → err-only → all); **`c`** cycles category
  (all → combat → command → item → room → player → world → system → all).
- Extract a **pure predicate** `line_passes(line, level_filter, category_filter) -> bool`
  (module-level function) so both `on_mount`/`_refresh_log`/`_full_refresh_log` use it and it is
  unit-testable:
  - level: 1 keeps lines containing `- WARNING -` or `- ERROR -`; 2 keeps only `- ERROR -`; 0 keeps all.
  - category: None keeps all; else keep lines containing `[<CATEGORY>]` (upper-case tag).
- On any filter change, call `_full_refresh_log()` (re-render) and update the `RichLog`
  `border_title` to `Logs — level: {name} · category: {name}` so the active filters are visible.

**Testable:** `line_passes` unit tests — an ERROR line passes level 2; an INFO line fails
level 1; a `[COMBAT]` line passes `category_filter="combat"` and fails `"world"`; None/0 pass all.

---

## Testing summary

- Part A: headless — no dict-dump line; attack log is combat-category (gated).
- Part C: unit-test `line_passes` (pure).
- Parts B and C's TUI wiring (bindings, title, RichLog size) are live-only — user verifies:
  open the log viewer, scroll to the top of a session, press `f`/`c` and watch it filter.

## Non-goals

- No change to `debug_log`'s format or gating mechanism (only categories on call sites).
- No new log persistence / export.
- No change to the colorizing (#7 already done).

## Constraints

- Zero gameplay change. `sim/`+`src/` outside mypy/ruff. Gate: `python -m pytest` +
  `engine.validate` + `import main`. User does own commits.
