# Typed Domain: Item — Spec (Strangler B, increment 4, final)

**Date:** 2026-07-08
**Status:** Approved design, not yet implemented.
**Why:** Final B increment. Types items on the enriched engine `Item` model so the
tune-critical fields (weapon `damage`, consumable `combat_effects`) validate **at load**, and
`GameWorld.self.items` becomes typed like the rest of the domain. Completes B (classes +
enemies + rooms + items).

## Plain summary

Items load as loose dicts; the model only typed 8 of ~28 fields. We enrich the `Item` model
with the load-bearing fields, load items through it (validating weapon damage / heal effects at
startup instead of silently mid-combat), and hand dicts back to the pervasive consumer code so
nothing else changes. One live-template mutation (starter-weapon `allowed_zones`) is handled
model-style.

## Constraints (global)

- **Zero gameplay change.** `model_dump(exclude_unset=True)` reproduces raw item dicts; extras
  round-trip. Refs already linker-validated. **New:** field-shape validation at load.
- Pre-flight verified: all 41 current items pass the enriched field types (no existing data bug).
- Advances adoption: `src` loaders import `engine.content`/`engine.schema` (no cycle).
- 41 items. `sim/`+`src/` outside mypy/ruff; `engine/` mypy-strict (Item change type-checks).
- Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
- User does own commits (propose only). One commit.
- Model: `engine/schema/models.py` `Item`.

---

## Part A — Enrich the `Item` model

Add the load-bearing fields (promoting today's `extra="allow"` tail to typed, validated):
```python
    short_description: str = ""
    tags: list = Field(default_factory=list)
    allowed_zones: list = Field(default_factory=list)
    damage: int = 0                      # weapons
    combat_effects: dict = Field(default_factory=dict)   # consumable heals etc.
    usable: bool = False
    usable_in_combat: bool = False
    consumed_on_use: bool = False
    takeable: bool = True
    droppable: bool = True
```
Deeply-nested / varied effect hooks stay `extra="allow"` (carried, not validated):
`on_use`, `on_take`, `on_read`, `on_examine`, `on_drop`, `effects`, `special_effects`,
`status_effect`, `story_flag`, `healing`, `allowed_rooms`. (`unlocks` is already modeled.)

Note the existing `Item` validator keeps `rarity` tolerant (coerces scalars to str). No new
required fields — every added field has a default, so absent keys don't fail.

## Part B — Seams (validate, hand back dicts)

- **`GameWorld.self.items`** — `game_engine._load_items` delegates to
  `engine.content.loader.load_items("data")`, so **all 41 items validate at world init** and
  `self.items` holds `Item` models. `GameWorld.get_item(item_id)` becomes the dump boundary:
  ```python
  def get_item(self, item_id):
      item = self.items.get(item_id)
      if item is None:
          debug_log(f"WARNING: Requested non-existent item: {item_id}")
          return None
      return item.model_dump(exclude_unset=True) if not isinstance(item, dict) else item
  ```
  All `get_item` consumers stay dict-based, unchanged.
- **Inventory/combat path** — `data_loader.load_weapon_data(id)` / `load_consumable_data(id)`
  add a validation gate and return the (unchanged-shape) dict:
  ```python
  from engine.schema import Item
  Item(id=item_id, **item_body)   # raises loud on a bad field; result discarded
  return item_body                # raw validated dict — inventory/equip/use unchanged
  ```
  This makes the lazy loaders fail loud too, without changing what the inventory receives.

## Part C — Direct `self.items` template reads (non-`get_item` sites)

- **`game_world.py:259-266`** — starter-weapon placement iterates `self.items.items()` (models)
  and mutates the template's `allowed_zones` in place:
  ```python
  for item_id, item_data in self.items.items():
      name_match = item_data.name.lower().replace(" ", "_") == starter_weapon
      if item_id == starter_weapon or name_match:
          if "safe" not in item_data.allowed_zones:
              item_data.allowed_zones.append("safe")   # live model list mutation
          ...
  ```
  (Drop the `isinstance(item_data, dict)` guard — items are models now.)
- **`game_world.py:345`** `self.items.get(id,{}).get("tags")` and **`:1306`**
  `...get("name")` → guarded attribute:
  ```python
  it = self.items.get(item_id)
  ... it.tags if it else [] ... / ... it.name if it else item_id ...
  ```

## Zero gameplay change / tests

- `model_dump(exclude_unset=True)` = raw dict (proven pattern); combat/use/placement read dicts
  unchanged; `damage`/`combat_effects` now validated at load.
- Tests (`tests/test_item_typed.py`):
  - `GameWorld.get_item(id)` returns a dict whose keys ⊇ the item's raw YAML keys.
  - `load_weapon_data`/`load_consumable_data` return dicts with `damage`/`combat_effects`
    intact; a deliberately bad field (e.g. `damage: "x"`) raises.
  - Headless run: take + equip a weapon (damage applies), use a heal (combat_effects path),
    and the starter-weapon placement lands in `home_grove` (guards the `265` model mutation).
- Existing `test_gear_pool`/`test_armor`/`test_loot_drops`/`test_commands`/`test_headless` cover the rest.

## Sweep

After the known conversions, run the full suite; any `AttributeError: 'Item' object has no
attribute 'get'` (or `__getitem__`) is a missed direct-`self.items` reader — convert it. (Same
sweep that finished the enemy/room increments — expect a few in placement/loot code.)

## Non-goals

- Not modeling the effect-hook blocks (`on_use`/`special_effects`/…) — stay extras.
- Not changing inventory/combat/use logic (they keep reading dicts).
- Not fixing any latent item bug surfaced by validation beyond noting it.
