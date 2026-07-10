# Log Panel Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Declutter noisy debug logs (#6), load the full session in the viewer (#8), and cycle filters by level + category (#5).

**Architecture:** #6 recategorizes high-frequency `[SYSTEM]` logs to gated categories + deletes dict-dumps (game_world, combat). #8/#5 edit `LogViewerScreen` (full-file load, bigger `RichLog`, a pure `line_passes` predicate, `f`/`c` cycling bindings, title showing filters).

**Tech Stack:** Python 3.11, Textual, pytest.

## Global Constraints

- **Zero gameplay change.** Only debug-log categories + the log-viewer modal change.
- `debug_log(msg, category="system")` gates only when `category in DEBUG_CATEGORIES and disabled`.
  `system` is ungated (always on); `world`/`combat` are gated off by default.
- `sim/`+`src/` outside mypy/ruff. Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
- User does own commits (propose only). Spec: `docs/LOG_PANEL_SPEC.md`.

## File Structure

| File | Change |
|---|---|
| `src/game_world.py` | accessor logs → `category="world"`; delete the full-dict dump |
| `src/combat.py:44` | `"Available attacks…"` → `category="combat"` |
| `src/ui/screens/log_viewer.py` | full-session load; `max_lines` 500→5000; `line_passes`; `f`/`c` cycles; title |
| `tests/test_log_declutter.py` (new) | accessor logs use `world` + no dict dump |
| `tests/test_log_filter.py` (new) | `line_passes` predicate |

---

## Task 1: Declutter (#6)

**Files:** `src/game_world.py`, `src/combat.py`, `tests/test_log_declutter.py`

- [ ] **Step 1: Failing test** (`tests/test_log_declutter.py`)

```python
"""High-frequency accessor logs must be gated (category='world') and never dump collections."""
from __future__ import annotations


def test_get_items_in_room_logs_are_gated_and_have_no_dict_dump(monkeypatch):
    import src.game_world as gw

    records = []
    monkeypatch.setattr(gw, "debug_log", lambda msg, category="system": records.append((str(msg), category)))

    from engine.content.loader import load_rooms, load_enemies, load_items
    rooms = {str(r): rr for r, rr in load_rooms("data").items()}
    enemies = {str(e): ee for e, ee in load_enemies("data").items()}
    items = {str(i): ii for i, ii in load_items("data").items()}
    world = gw.GameWorld(rooms, items, enemies, {})

    records.clear()
    world.get_items_in_room("home_grove")

    # no whole-collection dumps
    assert not any("item_locations:" in m and "{" in m for m, _ in records), \
        "get_items_in_room must not dump the full item_locations dict"
    # its informational lines are gated under the 'world' category
    info = [(m, c) for m, c in records if not m.startswith("WARNING")]
    assert info and all(c == "world" for _, c in info), \
        f"accessor logs should be category='world', got {info}"
```

- [ ] **Step 2: Run — expect FAIL**

`source venv/bin/activate && python -m pytest tests/test_log_declutter.py -v`
Expected: FAIL (logs use default `system`; dict dump present).

- [ ] **Step 3: Recategorize game_world accessors + delete the dict dump**

In `src/game_world.py`, for the accessor methods `get_items_in_room`, `get_enemies_in_room`,
`get_npcs_in_room`, `get_room`, `get_room_state`:
- **Delete** the line `debug_log(f"[Instance {self.instance_id}] Full item_locations: {self.item_locations}")`.
- Add `, category="world"` to each remaining **informational** `debug_log(...)` in those methods
  (e.g. `Getting items in room`, `Total items in item_locations`, `Items from locations for…`,
  `Found N enemies…`, `Retrieved room data for…`). Example:
  `debug_log(f"Getting items in room {room_id}", category="world")`.
- **Leave `WARNING:` lines unchanged** (default `system` category) so problems always surface.

- [ ] **Step 4: Recategorize the combat attack-fetch (src/combat.py:44)**

```python
        debug_log(f"Available attacks for {player_class} class: {attacks}", category="combat")
```

- [ ] **Step 5: Run test + full gate**

```bash
python -m pytest tests/test_log_declutter.py -v
python -m pytest
python -m engine.validate data
python -c "import main; print('IMPORT OK')"
```
Expected: pass; suite green; validate OK; import OK.

- [ ] **Step 6: Commit (propose)**

```bash
git add src/game_world.py src/combat.py tests/test_log_declutter.py
git commit -m "chore(logs): gate high-frequency debug logs by category; drop full-dict dumps (#6)"
```

---

## Task 2: Full-session view (#8)

**Files:** `src/ui/screens/log_viewer.py`

- [ ] **Step 1: Load the whole session + bigger buffer**

`compose`: `yield RichLog(highlight=True, markup=True, id="log-display", max_lines=5000)` (was 500).

`on_mount`: replace the `recent_lines = lines[-100:] …` block so it iterates **all** lines:
```python
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        stripped = line.rstrip()
                        if not line_passes(stripped, self._level_filter, self._category_filter):
                            continue
                        log_widget.write(self._colorize_log_line(stripped))
                    f.seek(0, 2)
                    self._log_position = f.tell()
```
(`line_passes` + the `_level_filter`/`_category_filter` fields come from Task 3. If Task 3 is
done first, this is coherent; otherwise temporarily keep the old `_filter_active` check and
just drop the `[-100:]` slice, then reconcile in Task 3.)

- [ ] **Step 2: Verify (live — user)**

Live-only: open the log viewer, press `g` → confirm you can scroll to the very first line of the
session. (Headless has no TUI; Task 1/3 carry the automated coverage.)

*(No separate commit — fold into the Task 3 commit since both edit log_viewer.py.)*

---

## Task 3: Filter by level + category (#5)

**Files:** `src/ui/screens/log_viewer.py`, `tests/test_log_filter.py`

- [ ] **Step 1: Failing test for the pure predicate** (`tests/test_log_filter.py`)

```python
from src.ui.screens.log_viewer import line_passes

ERR = "2026-07-09 10:00:00 - src.x - ERROR - boom"
WARN = "2026-07-09 10:00:00 - src.x - WARNING - hmm"
INFO = "2026-07-09 10:00:00 - src.x - INFO - fine"
COMBAT = "[2026-07-09 10:00:00.000] [COMBAT] [combat.py:f:1] hit"


def test_level_filter():
    assert line_passes(INFO, 0, None)                 # all
    assert not line_passes(INFO, 1, None)             # warn+err drops info
    assert line_passes(WARN, 1, None) and line_passes(ERR, 1, None)
    assert line_passes(ERR, 2, None) and not line_passes(WARN, 2, None)  # err-only


def test_category_filter():
    assert line_passes(COMBAT, 0, "combat")
    assert not line_passes(COMBAT, 0, "world")
    assert line_passes(COMBAT, 0, None)               # None = all categories
```

- [ ] **Step 2: Run — expect FAIL** (`line_passes` undefined)

`python -m pytest tests/test_log_filter.py -v` → FAIL (ImportError).

- [ ] **Step 3: Add the pure predicate (module level in log_viewer.py)**

```python
LOG_CATEGORIES = ["combat", "command", "item", "room", "player", "world", "system"]


def line_passes(line: str, level_filter: int, category_filter: str | None) -> bool:
    """level_filter: 0=all, 1=warnings+errors, 2=errors-only.
    category_filter: None=all, else keep lines tagged [CATEGORY]."""
    if level_filter == 2 and "- ERROR -" not in line:
        return False
    if level_filter == 1 and "- ERROR -" not in line and "- WARNING -" not in line:
        return False
    if category_filter and f"[{category_filter.upper()}]" not in line:
        return False
    return True
```

- [ ] **Step 4: Swap the binary filter for the two cycles**

In `LogViewerScreen`:
- `__init__`: replace `self._filter_active = False` with
  `self._level_filter = 0` and `self._category_filter = None`.
- BINDINGS: replace `("f", "toggle_filter", "Filter Warnings")` with
  `("f", "cycle_level", "Level Filter")` and add `("c", "cycle_category", "Category Filter")`.
- Replace `action_toggle_filter` with:
  ```python
  _LEVEL_NAMES = ["all", "warn+err", "err-only"]

  def action_cycle_level(self) -> None:
      self._level_filter = (self._level_filter + 1) % 3
      self._full_refresh_log()

  def action_cycle_category(self) -> None:
      cats = [None] + LOG_CATEGORIES
      i = cats.index(self._category_filter)
      self._category_filter = cats[(i + 1) % len(cats)]
      self._full_refresh_log()
  ```
- In `_refresh_log` and `_full_refresh_log`, replace the
  `if self._filter_active and … : continue` guard with:
  `if not line_passes(stripped, self._level_filter, self._category_filter): continue`.
- At the end of `_full_refresh_log`, set the title:
  ```python
      lvl = self._LEVEL_NAMES[self._level_filter]
      cat = self._category_filter or "all"
      log_widget.border_title = f"Logs — level: {lvl} · category: {cat}"
  ```

- [ ] **Step 5: Run tests + full gate**

```bash
python -m pytest tests/test_log_filter.py -v
python -m pytest
python -c "import main; print('IMPORT OK')"
```
Expected: pass; suite green; `IMPORT OK`.

- [ ] **Step 6: Verify (live — user)** open the viewer; `f` cycles level, `c` cycles category, title updates.

- [ ] **Step 7: Commit (propose)**

```bash
git add src/ui/screens/log_viewer.py tests/test_log_filter.py
git commit -m "feat(logs): full-session view + level/category filter cycles (#5, #8)"
```

---

## Self-Review

**Spec coverage:** #6 (T1), #8 (T2), #5 (T3). Colors (#7) unchanged. All covered.

**Placeholder scan:** none — code shown. T2 notes the Task-ordering dependency on `line_passes`
explicitly (do T3's predicate first, or keep the old guard then reconcile).

**Consistency:** `line_passes(line, level_filter, category_filter)` identical in test, predicate,
and both refresh call sites. `_level_filter`/`_category_filter` field names consistent.
