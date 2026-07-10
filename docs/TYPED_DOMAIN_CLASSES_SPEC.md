# Typed Domain: CharacterClass — Spec (Strangler Step B, pilot)

**Date:** 2026-07-08
**Status:** Approved design, not yet implemented.
**Why:** First B increment of the `src/` → `engine/` strangler (agreed path C → B → A;
C shipped). Proves the "dict → typed model" seam on the smallest, best-tested subsystem:
character classes. `src/` starts consuming `engine/` typed content, killing the
silent-default / string-coupling class on the character-build path.

## Plain summary

Today `src/` reads class data as raw dicts — `class_info.get("base_health", 100)` — so a
renamed/typo'd key silently falls back to a default instead of failing. And class data is
loaded in **three** different places. This increment makes the class loader return the
existing typed `engine` `CharacterClass` model, collapses the three loaders into one, and
switches the read sites to attribute access (`class_info.base_health`). Gameplay identical.

## Constraints (global)

- **Zero gameplay change.** Same class stats, same class-selection screen, same combat.
- **Advances adoption:** `src/` now imports `engine.content`/`engine.schema` (first such link).
  No import cycle: `data_loader → engine.content.loader → engine.schema`; none import back
  into `src.data_loader`.
- YAML content unchanged (already snake_case; classes live in `data/classes.yaml`).
- `sim/` and `src/` stay outside mypy/ruff; `engine/` is mypy-strict (no `engine/` change here).
- Gate: `source venv/bin/activate` then `python -m pytest` + `python -m engine.validate data`
  + `python -c "import main"`. Bare `pytest` fails (`No module named 'src'`) — use `python -m pytest`.
- User does own commits (propose commands only). One commit.
- Model reference: `engine/schema/models.py` — `CharacterClass` (id, name, description,
  base_health>0, base_damage>0, starter_weapon, starter_abilities, attacks, preferred_zones,
  power_scaling, loot_preference, display) and `ClassDisplay` (color, hp_label, hp_color,
  dmg_label, dmg_color, weapon_name, echo_description). Every key `src/` reads is covered.

## Architecture — the seam

`src/data_loader.load_class_data()` becomes the **single** class-data source and returns
`dict[str, CharacterClass]` (engine models) instead of raw dicts:

- It delegates to `engine.content.loader.load_classes("data")`, keeping its own name and its
  module-level cache (`_class_data_cache`). The outer dict stays keyed by class id (plain
  `str`); each value is a typed `CharacterClass`.
- `engine.content.loader.load_classes` already reads `data/classes.yaml`'s `classes:` section
  and validates it (`base_health/base_damage > 0`) — so a bad class now fails **loud at load**.

## Unify the three loaders → one

1. `src/game_world.py::_load_class_data` (its own inline `yaml.safe_load`) — **delete**;
   `GameWorld.__init__` sets `self.class_data = load_class_data()` (import from `src.data_loader`).
2. `src/game_engine.py::_validate_data_references` (line ~180) inline `yaml.safe_load` —
   replace with `load_class_data()`; read `cls.starter_weapon`.
3. `src/game_engine.py` class-selection paths already call `load_class_data()` — unchanged
   source, now typed values.

## Consumer edits (dict `.get` → attribute access)

All values are `CharacterClass` models; the **outer** dict keeps dict semantics
(`pc in classes`, `classes[pc]`, `classes.get(pc)`, `classes.items()`, `classes.keys()`).

**`src/player.py::load_class_attributes` (~85-101):**
- `class_info.get("base_health", 100)` → `class_info.base_health`
- `class_info.get("base_damage", 5)` → `class_info.base_damage`
- `class_info.get("description", ...)` → `class_info.description`
- `class_info.get("starter_abilities", [])` → `class_info.starter_abilities`
- `class_info = classes_data.get(self.player_class)` and the `if not class_info:` guard stay
  (a missing id → `None`; a model is always truthy).

**`src/combat.py::get_attacks_for_class` (~42):**
- `class_data.get(player_class, {}).get("attacks", ["strike"])` →
  ```python
  cls = class_data.get(player_class)
  attacks = (cls.attacks if cls else None) or ["strike"]
  ```
  (preserves today's `["strike"]` fallback for a class with no attacks).

**`src/game_world.py` (~112, 255, 282):**
- `class_info.get("power_scaling", "balanced")` → `class_info.power_scaling`
- `class_info.get("starter_weapon")` → `class_info.starter_weapon`
- `class_info.get("preferred_zones", [])` → `class_info.preferred_zones`
- `class_info = self.class_data.get(player_class, {})` → `self.class_data.get(player_class)`;
  where the code then reads a field, guard `if class_info:` (it already checks membership
  before the `[player_class]` reads at 255/282).

**`src/game_engine.py::_show_class_selection` (~690-703) and `_show_tutorial_introduction` (~759-761):**
- `d = cls.get("display", {})` → `d = cls.display` (`ClassDisplay`, always present via default).
- `d.get("color"/"hp_color"/"dmg_color"/"hp_label"/"dmg_label"/"weapon_name", ...)` → `d.color`, etc.
- `cls.get("name", class_id)` → `cls.name`; `cls.get("description", "")` → `cls.description`;
  `cls.get("preferred_zones", [])` → `cls.preferred_zones`.
- tutorial: `cls = classes.get(self.selected_class)`; guard `if cls:` then `cls.name` and
  `cls.display.echo_description`, else keep the existing fallbacks.

**`src/game_engine.py::_validate_data_references` (~183):**
- `for cls_name, cls_info in class_data.items(): weapon = cls_info.get("starter_weapon")` →
  `weapon = cls_info.starter_weapon`.

## Why it's safe / zero gameplay change

- Model field defaults equal today's `.get` fallbacks; `base_health`/`base_damage` validate
  `>0` at load (loud, replacing silent 100/5 defaults).
- `ClassDisplay` is always instantiated (default factory), so `cls.display.<field>` is safe
  even if a class omits `display:` — matching `.get("display", {})`.
- Class data is **read-only** on every path above (player copies values into its own attrs;
  nothing mutates the class object) — so model-vs-dict can't bite on a write.

## Tests

- New (`tests/test_content.py` or a small `tests/test_classes.py`): `load_class_data()` returns
  `CharacterClass` instances for guardian/weaver/shaman, with `base_health/base_damage > 0`.
- New: `GameSession.new_game(..., "guardian")` (headless) drives the class-selection +
  tutorial render without error, for all 3 classes — exercises the display attribute path.
- Existing coverage stays green: `test_content` boots every class; `test_headless` plays a run;
  `test_commands` covers combat (attacks-for-class path).

## Non-goals

- Not typing Item / Enemy / Room yet (later B increments; Item needs schema enrichment first).
- Not adding `src/` to mypy (static checking is a separate step; this removes the *runtime*
  silent-default class now).
- No change to combat math, item placement, saves, or the class YAML content.

## Gate

`python -m pytest` green · `engine.validate data` → `OK: … 3 classes …` · `import main` clean.
Manual sanity (optional): launch `python main.py`, confirm the class-selection screen renders
all three cards identically to before.
