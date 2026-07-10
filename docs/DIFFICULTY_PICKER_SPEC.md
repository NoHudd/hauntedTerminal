# Difficulty Picker at Game Start — Spec

**Date:** 2026-07-09
**Status:** Approved design, not yet implemented.
**Scope:** Add a difficulty picker to the start of a new game; **lock difficulty for the run**
(remove the mid-game Settings control). From playtest note #11 (revised: no anytime changes).

## Context

- Backend exists: `src/difficulty.py` — `MODES = (easy, medium, hard)`, `set_mode(mode)`,
  `current_mode()`, multipliers from `data/difficulty.yaml` (scale enemy HP/damage + XP).
- Currently difficulty is only set via the **Settings screen** (ctrl+p) radio → `settings_manager.set_difficulty`.
- New-game flow (game_engine): `_start_new_game()` → `_show_class_selection()` (state
  `WAITING_FOR_CLASS`) → `_handle_class_input()` → `_show_tutorial_introduction()` → name → `create_player`.
- Input dispatch (`_on_command_entered`, ~236-241) routes by `GameState`.

## Part A — Difficulty picker at start (before class selection)

New flow: `menu → New Game → PICK DIFFICULTY → class select → name → play`.

1. **New state** — add `GameState.WAITING_FOR_DIFFICULTY = "waiting_for_difficulty"` to
   `src/game_states.py`; add transitions in `src/state_manager.py::_valid_transitions`:
   `MENU → [WAITING_FOR_DIFFICULTY, …]` and `WAITING_FOR_DIFFICULTY → [WAITING_FOR_CLASS]`.
   (The manager warns-but-proceeds on unlisted transitions, but list them cleanly.)

2. **`_start_new_game`** — call `self._show_difficulty_selection()` instead of
   `self._show_class_selection()`.

3. **`_show_difficulty_selection()`** (new, in game_engine) — mirror `_show_class_selection`'s
   Rich-panel rendering: one panel per mode with a name + one-line description, numbered 1-3.
   Set `state_manager.set_state(GameState.WAITING_FOR_DIFFICULTY)`. Descriptions:
   - **Easy** — "Gentler enemies, faster leveling. For learning the ropes."
   - **Medium** — "The intended, balanced challenge."
   - **Hard** — "Tougher enemies and longer fights; level slower."

4. **Dispatch** — in `_on_command_entered`, add
   `elif game_state == GameState.WAITING_FOR_DIFFICULTY: self._handle_difficulty_input(command)`.

5. **`_handle_difficulty_input(choice)`** (new) — map `"1"/"2"/"3"` → `easy/medium/hard`
   (order = `difficulty.MODES`). On valid choice: `from src import difficulty;
   difficulty.set_mode(mode)`, then `self._show_class_selection()`. On invalid: reprint the
   picker with an error (mirror `_handle_class_input`'s invalid path).

   Note: the engine sets the run's mode via `difficulty.set_mode` (backend module) — it does not
   touch the UI's `settings_manager`. Difficulty is per-run; not persisted to `settings.json`
   (the player picks each new game). Loaded games keep the last-applied mode (existing behavior).

## Part B — Remove the mid-game change path

Difficulty is fixed once chosen, so remove it from Settings entirely (`src/ui/screens/settings_screen.py`):
- Delete `DIFFICULTY_KEYS`, the `current_difficulty` lookup, the Difficulty **section label +
  `RadioSet`/`RadioButton`s (`id="difficulty-radio"`)**, and the `on_radio_set_changed` branch
  `elif event.radio_set.id == "difficulty-radio": …`.
- Leave `settings_manager.set_difficulty` / `settings["difficulty"]` in place (still applied on
  mount as a harmless default; the picker overrides per game). No other Settings control changes.

## Testing

- **Headless (unit):** construct `ImprovedGameEngine(ui=HeadlessUI())`; call
  `engine._handle_difficulty_input("3")` → assert `difficulty.current_mode() == "hard"` and that
  it advances to class selection (`state == WAITING_FOR_CLASS`). Also `"1"` → easy, `"2"` → medium.
- **Live (user):** start a new game → the difficulty screen appears first, picking flows into
  class selection; ctrl+p Settings no longer shows a difficulty option.

## Non-goals

- No per-save difficulty (a loaded game uses the last-applied mode).
- No change to `difficulty.py` multipliers or the tune.
- No mid-game difficulty change (deliberately removed).

## Constraints

- Zero change to the difficulty *values* (tune unaffected). `sim/`+`src/` outside mypy/ruff.
- Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
- User does own commits.
