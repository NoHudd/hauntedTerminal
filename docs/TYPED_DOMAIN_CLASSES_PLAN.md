# Typed Domain: CharacterClass — Implementation Plan (Strangler Step B, pilot)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make `src/` consume the typed `engine` `CharacterClass` model for class data instead of raw dicts, collapse three class loaders into one, without changing gameplay.

**Architecture:** `src/data_loader.load_class_data()` delegates to `engine.content.loader.load_classes` and returns `dict[str, CharacterClass]`. This flip is atomic — every consumer reading `class_info.get(...)` breaks the instant the loader returns models — so the loader change and all read-site edits land in **one** green task/commit.

**Tech Stack:** Python 3.11, Pydantic v2 (engine schema), pytest.

## Global Constraints

- **Zero gameplay change.** Same class stats, class-selection screen, combat.
- Outer class dict keeps dict semantics (`pc in classes`, `classes[pc]`, `.get`, `.items`,
  `.keys`); only the **values** become `CharacterClass` models.
- No import cycle: `data_loader → engine.content.loader → engine.schema`; none import back into `src.data_loader`.
- `sim/` and `src/` stay outside mypy/ruff; no `engine/` change in this increment.
- Gate: `source venv/bin/activate`; `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
  Bare `pytest` fails (`No module named 'src'`) — use `python -m pytest`.
- User does own commits (propose commands; never run `git commit`). One commit.
- Spec: `docs/TYPED_DOMAIN_CLASSES_SPEC.md`. Model: `engine/schema/models.py` `CharacterClass` / `ClassDisplay`.

## File Structure

| File | Change |
|---|---|
| `src/data_loader.py:11` `load_class_data` | Return `dict[str, CharacterClass]` via engine loader (keep cache) |
| `src/player.py:85-101` | `.get(...)` → attribute access |
| `src/combat.py:42` `get_attacks_for_class` | model `.attacks` + `["strike"]` fallback |
| `src/game_world.py:50,112,221-231,255,282` | call `load_class_data`; delete own loader; attribute reads |
| `src/game_engine.py:180,690-703,759-761` | one loader; display attribute reads |
| `tests/test_classes.py` (new) | typed-loader + headless class-selection render |

---

## Task 1: Type CharacterClass end to end (atomic)

**Files:** all of the above.

**Interfaces:**
- Produces: `src.data_loader.load_class_data() -> dict[str, CharacterClass]` (cached).
- Consumes: `engine.content.loader.load_classes(data_dir) -> dict[ClassId, CharacterClass]`.

- [ ] **Step 1: Write the failing test** (`tests/test_classes.py`)

```python
"""CharacterClass is typed end to end: the src loader yields engine models,
and the class-selection / tutorial render path works for every class."""
from __future__ import annotations

from engine.schema import CharacterClass


def test_load_class_data_returns_typed_models():
    from src.data_loader import load_class_data
    classes = load_class_data()
    for cid in ("guardian", "weaver", "shaman"):
        assert cid in classes
        klass = classes[cid]
        assert isinstance(klass, CharacterClass), type(klass)
        assert klass.base_health > 0 and klass.base_damage > 0


def test_class_selection_and_tutorial_render_headless():
    from engine.api import GameSession
    for cid in ("guardian", "weaver", "shaman"):
        s = GameSession()
        try:
            out = s.new_game("Tester", cid)
            assert out  # produced startup text without raising
        finally:
            s.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_classes.py -v`
Expected: `test_load_class_data_returns_typed_models` FAILS (loader returns dicts, not `CharacterClass`).

- [ ] **Step 3: Flip `src/data_loader.load_class_data` to typed models**

Replace the body (data_loader.py:11-39) with:

```python
def load_class_data():
    """Load character classes as typed engine CharacterClass models (id -> model)."""
    global _class_data_cache
    if _class_data_cache is not None:
        return _class_data_cache
    try:
        from engine.content.loader import load_classes
        _class_data_cache = {str(cid): klass for cid, klass in load_classes("data").items()}
        debug_log(f"Loaded class data: {list(_class_data_cache.keys())}")
        return _class_data_cache
    except Exception as e:
        debug_log(f"ERROR loading class data: {e}")
        return {}
```

- [ ] **Step 4: Update `src/player.py::load_class_attributes` (~85-101)**

```python
        self.max_health = class_info.base_health
        self.health = self.max_health
        self.total_damage = class_info.base_damage
        self.class_description = class_info.description
```
and:
```python
        self.starter_abilities = class_info.starter_abilities
```
Leave `classes_data.get(self.player_class)` and the `if not class_info:` guard as-is
(missing id → `None`; a model is always truthy).

- [ ] **Step 5: Update `src/combat.py::get_attacks_for_class` (~42)**

```python
        class_data = load_class_data()
        cls = class_data.get(player_class)
        attacks = (cls.attacks if cls else None) or ["strike"]
```

- [ ] **Step 6: Update `src/game_world.py` — delete own loader, unify, attribute reads**

`__init__` (line 50): keep `self.class_data = self._load_class_data()` OR change to the shared
loader. Replace `_load_class_data` (221-231) with a thin delegate so callers are unaffected:

```python
    def _load_class_data(self):
        """Class data as typed models (delegates to the shared loader)."""
        from src.data_loader import load_class_data
        return load_class_data()
```

Line 112-113:
```python
        class_info = self.class_data.get(player_class)
        power_scaling = class_info.power_scaling if class_info else "balanced"
```
Line 256:
```python
        starter_weapon = class_info.starter_weapon
```
Lines 283-285:
```python
        preferred_zones = class_info.preferred_zones
        loot_preferences = class_info.loot_preference
        power_scaling = class_info.power_scaling
```
(`self.class_data[player_class]` at 255/282 stays — membership is checked before both.)

- [ ] **Step 7: Update `src/game_engine.py::_validate_data_references` (~179-188)**

Replace the inline `yaml.safe_load` class block with the shared loader + attribute read:

```python
        # Load class data to validate starter weapons
        try:
            from src.data_loader import load_class_data
            class_data = load_class_data()
            for cls_name, cls_info in class_data.items():
                weapon = cls_info.starter_weapon
                if weapon and weapon not in items:
                    errors.append(f"Class '{cls_name}' starter_weapon '{weapon}' not found in items")
        except Exception as e:
            errors.append(f"Could not validate class data: {e}")
```

- [ ] **Step 8: Update `src/game_engine.py::_show_class_selection` (~690-703)**

```python
            for i, (class_id, cls) in enumerate(classes.items(), 1):
                d = cls.display
                color = d.color
                hp_color = d.hp_color
                dmg_color = d.dmg_color
                icon = self._CLASS_ICONS.get(class_id, "•")
                name = cls.name.upper()
                tagline = cls.description.split(" - ", 1)
                tagline_main = tagline[0] if tagline else ""
                tagline_sub = tagline[1] if len(tagline) > 1 else ""
                hp = d.hp_label
                dmg = d.dmg_label
                weapon = d.weapon_name
                pref = ", ".join(cls.preferred_zones or [])
```

- [ ] **Step 9: Update `src/game_engine.py::_show_tutorial_introduction` (~759-761)**

```python
            cls = classes.get(self.selected_class)
            selected_class_name = cls.name if cls else self.selected_class.title()
            selected_class_desc = (
                cls.display.echo_description if cls else "a mysterious entity"
            )
```

- [ ] **Step 10: Run the new test + full gate**

Run:
```bash
python -m pytest tests/test_classes.py -v
python -m pytest
python -c "import main; print('IMPORT OK')"
python -m engine.validate data
```
Expected: new tests PASS; full suite green (110 passed, 1 xfailed); `IMPORT OK`;
validate `OK: … 3 classes …`.

- [ ] **Step 11: Commit (propose to user)**

```bash
git add src/data_loader.py src/player.py src/combat.py src/game_world.py src/game_engine.py tests/test_classes.py
git commit -m "refactor(domain): type CharacterClass via engine model; unify 3 class loaders (strangler B)"
```

---

## Self-Review

**Spec coverage:** seam (Step 3), loader unification (Steps 3/6/7), player (4), combat (5),
game_world (6), game_engine validator + display + tutorial (7/8/9), tests (1). All covered.

**Placeholder scan:** none — every step shows the final code to write.

**Consistency:** `load_class_data() -> dict[str, CharacterClass]` used identically in the
interface block, Step 3, and every consumer. `ClassDisplay` fields (`color`, `hp_color`,
`dmg_color`, `hp_label`, `dmg_label`, `weapon_name`, `echo_description`) match the model.
