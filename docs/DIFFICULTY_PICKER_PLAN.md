# Difficulty Picker at Game Start — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Pick difficulty at the start of a new game (before class selection); remove the mid-game Settings difficulty control (difficulty locked for the run).

**Architecture:** New `WAITING_FOR_DIFFICULTY` state + a Rich-panel picker screen mirroring class selection. `_handle_difficulty_input` sets `difficulty.set_mode` then flows into class selection. Settings screen loses its difficulty radio.

**Tech Stack:** Python 3.11, Textual, Rich, pytest.

## Global Constraints

- **No change to difficulty *values*** (tune unaffected) — only *when/how* it's chosen.
- Engine sets the run mode via `difficulty.set_mode` (backend); not persisted to settings.json.
- `sim/`+`src/` outside mypy/ruff. Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
- User does own commits (propose only). Spec: `docs/DIFFICULTY_PICKER_SPEC.md`.

## File Structure

| File | Change |
|---|---|
| `src/game_states.py` | + `WAITING_FOR_DIFFICULTY` |
| `src/state_manager.py` | + transitions for the new state |
| `src/game_engine.py` | picker screen + input handler + dispatch + `_start_new_game` insert |
| `src/ui/screens/settings_screen.py` | remove the difficulty radio |
| `tests/test_difficulty_picker.py` (new) | picker sets mode + advances |

---

## Task 1: Difficulty picker (before class selection)

- [ ] **Step 1: Failing test** (`tests/test_difficulty_picker.py`)

```python
"""Picking difficulty at start sets the run's mode and advances to class selection."""
from __future__ import annotations

import pytest

from engine.headless import HeadlessUI
from src import difficulty
from src.game_engine import ImprovedGameEngine
from src.game_states import GameState
from src.state_manager import state_manager


@pytest.mark.parametrize("choice,expected", [("1", "easy"), ("2", "medium"), ("3", "hard")])
def test_difficulty_pick_sets_mode_and_advances(choice, expected):
    eng = ImprovedGameEngine(ui=HeadlessUI())
    eng._handle_difficulty_input(choice)
    assert difficulty.current_mode() == expected
    assert state_manager.current_state == GameState.WAITING_FOR_CLASS


def test_invalid_difficulty_choice_reprompts():
    eng = ImprovedGameEngine(ui=HeadlessUI())
    before = difficulty.current_mode()
    eng._handle_difficulty_input("9")   # invalid
    assert difficulty.current_mode() == before  # unchanged
    assert state_manager.current_state == GameState.WAITING_FOR_DIFFICULTY
```

- [ ] **Step 2: Run — expect FAIL** (`_handle_difficulty_input` undefined)

`source venv/bin/activate && python -m pytest tests/test_difficulty_picker.py -v` → FAIL.

- [ ] **Step 3: Add the state** (`src/game_states.py`)

After `WAITING_FOR_CLASS = "waiting_for_class"`:
```python
    WAITING_FOR_DIFFICULTY = "waiting_for_difficulty"
```

- [ ] **Step 4: Add transitions** (`src/state_manager.py::_valid_transitions`)

```python
        GameState.MENU: [GameState.WAITING_FOR_DIFFICULTY, GameState.WAITING_FOR_NAME, GameState.LOADING, GameState.EXIT],
        GameState.WAITING_FOR_DIFFICULTY: [GameState.WAITING_FOR_CLASS, GameState.MENU],
```
(add the `WAITING_FOR_DIFFICULTY` line; extend the existing `MENU:` list to include it.)

- [ ] **Step 5: Point `_start_new_game` at the picker** (`src/game_engine.py`)

In `_start_new_game`, change `self._show_class_selection()` → `self._show_difficulty_selection()`.

- [ ] **Step 6: Add the picker screen + input handler** (`src/game_engine.py`, near `_show_class_selection`)

```python
    _DIFFICULTY_INFO = {
        "easy":   ("🌱", "green", "Gentler enemies, faster leveling. For learning the ropes."),
        "medium": ("⚖",  "cyan",  "The intended, balanced challenge."),
        "hard":   ("🔥", "red",   "Tougher enemies and longer fights; you level slower."),
    }

    def _show_difficulty_selection(self):
        """Difficulty picker — Rich panels, mirrors class selection."""
        try:
            from src import difficulty
            from rich.panel import Panel
            from rich.console import Group
            from rich.text import Text
            from rich.align import Align
            from rich.rule import Rule

            renderables = [
                Text(""),
                Align.center(Text("⚙  CHOOSE YOUR DIFFICULTY  ⚙", style="bold cyan")),
                Rule(style="cyan"),
                Text(""),
            ]
            for i, mode in enumerate(difficulty.MODES, 1):
                icon, color, desc = self._DIFFICULTY_INFO.get(mode, ("•", "white", ""))
                body = Text(desc, style="italic")
                renderables.append(Panel(
                    body,
                    title=f"[bold {color}][{i}]  {icon}  {mode.upper()}[/bold {color}]",
                    title_align="left",
                    border_style=color,
                    padding=(1, 2),
                    expand=True,
                ))
                renderables.append(Text(""))
            renderables.append(
                Text(f"Enter your choice (1–{len(difficulty.MODES)}):", style="bold white")
            )

            group = Group(*renderables)
            if hasattr(self.ui, "update_output_renderable"):
                self.ui.update_output_renderable(group)
            else:
                from rich.console import Console
                con = Console(record=True, width=100)
                con.print(group)
                self.ui.update_output(con.export_text(styles=True))

            state_manager.set_state(GameState.WAITING_FOR_DIFFICULTY)
        except Exception as e:
            logger.error(f"Error showing difficulty selection: {e}")
            self.ui.update_output(f"Error showing difficulty selection: {e}")
            state_manager.set_state(GameState.MENU)

    def _handle_difficulty_input(self, choice: str):
        """Set the run's difficulty from the picker, then go to class selection."""
        from src import difficulty
        mode_map = {str(i): m for i, m in enumerate(difficulty.MODES, 1)}
        mode = mode_map.get(str(choice).strip())
        if not mode:
            valid = ", ".join(mode_map.keys())
            self.ui.update_output(f"[bold red]Invalid choice. Please enter {valid}.[/bold red]\n")
            self._show_difficulty_selection()
            return
        difficulty.set_mode(mode)
        self.ui.update_output(f"[bold green]Difficulty set to {mode.upper()}.[/bold green]\n")
        self._show_class_selection()
```

- [ ] **Step 7: Route input for the new state** (`src/game_engine.py::_on_command_entered`, ~236-241)

After the `WAITING_FOR_CLASS` branch, add:
```python
            elif game_state == GameState.WAITING_FOR_DIFFICULTY:
                self._handle_difficulty_input(command)
```

- [ ] **Step 8: Run test + full gate**

```bash
python -m pytest tests/test_difficulty_picker.py -v
python -m pytest
python -m engine.validate data
python -c "import main; print('IMPORT OK')"
```
Expected: pass; suite green; validate OK; `IMPORT OK`.

- [ ] **Step 9: Commit (propose)**

```bash
git add src/game_states.py src/state_manager.py src/game_engine.py tests/test_difficulty_picker.py
git commit -m "feat(ui): pick difficulty at game start (before class selection) (#11)"
```

---

## Task 2: Remove the mid-game Settings difficulty control

**Files:** `src/ui/screens/settings_screen.py`

- [ ] **Step 1: Remove the difficulty section from `compose`**

Delete:
```python
            yield Label("🎯 Difficulty", classes="settings-label")
            yield Static("[dim]Scales enemy strength & leveling[/dim]")
            yield RadioSet(
                RadioButton("Easy",   value=(current_difficulty == "easy")),
                RadioButton("Medium", value=(current_difficulty == "medium")),
                RadioButton("Hard",   value=(current_difficulty == "hard")),
                id="difficulty-radio",
            )
```

- [ ] **Step 2: Remove the change handler branch**

In `on_radio_set_changed`, delete:
```python
        elif event.radio_set.id == "difficulty-radio":
            self._manager.set_difficulty(DIFFICULTY_KEYS[event.index])
```

- [ ] **Step 3: Remove now-unused refs**

Delete `DIFFICULTY_KEYS = ["easy", "medium", "hard"]` (top of file) and the
`current_difficulty = s.get("difficulty", "medium")` line. (Leave `settings_manager.set_difficulty`
and `settings["difficulty"]` — still applied on mount as a harmless default.)

- [ ] **Step 4: Verify + full gate**

```bash
python -c "import src.ui.screens.settings_screen; print('OK')"
python -m pytest
python -c "import main; print('IMPORT OK')"
grep -n "difficulty" src/ui/screens/settings_screen.py || echo "NO difficulty refs in settings screen"
```
Expected: imports clean; suite green; `IMPORT OK`; no difficulty refs remain.

- [ ] **Step 5: Commit (propose)**

```bash
git add src/ui/screens/settings_screen.py
git commit -m "feat(ui): lock difficulty for the run — remove Settings difficulty control (#11)"
```

---

## Self-Review

**Spec coverage:** Part A (state S3, transitions S4, insert S5, screen+handler S6, dispatch S7) +
Part B (Settings removal T2). Test S1. All covered.

**Placeholder scan:** none — full code shown; screens are the only live-verify part.

**Consistency:** `_handle_difficulty_input` maps `difficulty.MODES` order (1=easy,2=medium,3=hard),
matching the test; sets `difficulty.set_mode` then `_show_class_selection`; state names consistent.
