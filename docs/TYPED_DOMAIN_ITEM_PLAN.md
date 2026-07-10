# Typed Domain: Item — Implementation Plan (Strangler B, increment 4, final)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Enrich the `Item` model and load items through it so weapon `damage` / consumable `combat_effects` validate at load; `GameWorld.self.items` becomes typed; consumers keep dicts. One commit.

**Architecture:** `_load_items` → engine loader (self.items = `Item` models, validated at init). `get_item` dumps model→dict (consumers unchanged). `load_weapon_data`/`load_consumable_data` add a validation gate and return the same dict. The one live-template mutation (starter weapon `allowed_zones`) + two direct reads convert to attributes.

**Tech Stack:** Python 3.11, Pydantic v2, pytest.

## Global Constraints

- **Zero gameplay change.** `model_dump(exclude_unset=True)` == raw item dict; extras round-trip.
  Pre-flight verified: all 41 items pass the enriched field types.
- Outer `self.items` dict keeps dict semantics; only **values** are models. `get_item` returns a dict.
- No import cycle: `data_loader`/`game_engine` → `engine.content`/`engine.schema`.
- `sim/`+`src/` outside mypy/ruff; `engine/` mypy-strict (Item change type-checks).
- Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
- User does own commits (propose; never run `git commit`). ONE commit.
- Spec: `docs/TYPED_DOMAIN_ITEM_SPEC.md`.

## File Structure

| File | Change |
|---|---|
| `engine/schema/models.py` `Item` | +10 load-bearing fields (defaults) |
| `src/game_engine.py:206` `_load_items` | delegate to engine loader (models) |
| `src/game_world.py:1074` `get_item` | dump model→dict boundary |
| `src/game_world.py:259-266,345,1306` | direct `self.items` reads → attributes |
| `src/data_loader.py` weapon+consumable loaders | validation gate, return dict |
| `tests/test_item_typed.py` (new) | boundary + loader validation + placement |

---

## Task 1: Type Item end to end (atomic, one commit)

- [ ] **Step 1: Write the failing test** (`tests/test_item_typed.py`)

```python
"""Items validate at load; get_item hands consumers a dict; placement/mutation intact."""
from __future__ import annotations

import glob
import os

import pytest
import yaml


def test_get_item_returns_dict_matching_raw_yaml():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        # weapons.yaml first item
        weapons = yaml.safe_load(open("data/items/weapons.yaml")) or {}
        iid = next(iter(weapons))
        got = world.get_item(iid)
        assert isinstance(got, dict)
        assert set(weapons[iid].keys()) <= set(got.keys())
        assert got.get("damage") == weapons[iid].get("damage")
    finally:
        s.close()


def test_loaders_validate_and_return_dicts():
    from src.data_loader import load_weapon_data, load_consumable_data
    w = load_weapon_data("segfault_shield")
    assert isinstance(w, dict) and isinstance(w.get("damage"), int)
    c = load_consumable_data("health_packet")
    assert isinstance(c, dict) and isinstance(c.get("combat_effects"), dict)


def test_bad_item_field_raises_at_validation():
    from engine.schema import Item
    with pytest.raises(Exception):
        Item(id="x", name="X", type="weapon", damage="not-a-number")
```

- [ ] **Step 2: Run to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_item_typed.py -v`
Expected: `test_bad_item_field_raises_at_validation` FAILS (model has no `damage`, so a string is
accepted as an extra). `get_item` test may pass (already returns dict-of-dict today).

- [ ] **Step 3: Enrich `Item` in `engine/schema/models.py`**

After `unlocks: list[RoomId] = ...` in `class Item`:
```python
    short_description: str = ""
    tags: list = Field(default_factory=list)
    allowed_zones: list = Field(default_factory=list)
    damage: int = 0
    combat_effects: dict = Field(default_factory=dict)
    usable: bool = False
    usable_in_combat: bool = False
    consumed_on_use: bool = False
    takeable: bool = True
    droppable: bool = True
```

- [ ] **Step 4: `_load_items` → engine loader (src/game_engine.py:206-241)**

Replace the whole method body with:
```python
    def _load_items(self) -> Dict[str, Any]:
        """Load all items as typed engine Item models (id -> model), validated at load."""
        from engine.content.loader import load_items
        items: Dict[str, Any] = {str(iid): it for iid, it in load_items("data").items()}
        logger.info(f"Total items loaded: {len(items)}")
        return items
```

- [ ] **Step 5: `get_item` dump boundary (src/game_world.py:1074)**

```python
    def get_item(self, item_id):
        """Get item data by ID (typed template dumped to a runtime dict)."""
        item = self.items.get(item_id)
        if item is None:
            debug_log(f"WARNING: Requested non-existent item: {item_id}")
            return None
        return item.model_dump(exclude_unset=True) if not isinstance(item, dict) else item
```

- [ ] **Step 6: Convert the starter-weapon placement mutation (src/game_world.py:258-266)**

```python
        for item_id, item_data in self.items.items():
            name_match = item_data.name.lower().replace(" ", "_") == starter_weapon
            if item_id == starter_weapon or name_match:
                weapon_found = True
                # Ensure it can spawn in safe zones like home_grove
                if "safe" not in item_data.allowed_zones:
                    item_data.allowed_zones.append("safe")
                debug_log(f"Starter weapon {starter_weapon} configured for dynamic placement")
                break
```

- [ ] **Step 7: Convert the two direct reads (345, 1306)**

`345`:
```python
            it = self.items.get(item_id)
            "healing" in (it.tags if it else [])
```
(preserve the surrounding expression — replace `self.items.get(item_id, {}).get("tags", [])`
with `((it := self.items.get(item_id)) and it.tags) or []` if it's a single expression; otherwise
use the two-line form.)
`1306`:
```python
                it = self.items.get(item_id)
                item_name = it.name if it else item_id
```

- [ ] **Step 8: Validation gate in the lazy loaders (src/data_loader.py)**

`load_weapon_data` — after `weapon_data = weapons.get(weapon_id)` and inside `if weapon_data:`,
before `weapon_data["id"] = weapon_id`:
```python
                from engine.schema import Item
                Item(id=weapon_id, **weapon_data)  # validation gate; raises loud on a bad field
```
`load_consumable_data` — after `consumable_data = _consumables_data_cache[consumable_id].copy()`,
before `consumable_data["id"] = consumable_id`:
```python
        from engine.schema import Item
        Item(id=consumable_id, **consumable_data)  # validation gate
```

- [ ] **Step 9: Run the suite; sweep stragglers**

Run: `python -m pytest 2>&1 | tail -20`
Any `AttributeError: 'Item' object has no attribute 'get'` / `... '__getitem__'` points to a
missed direct `self.items[...]` reader — convert that `item.get("X")`/`item["X"]`/`"X" in item`
to attribute access (or route through `get_item` for a dict). Re-run until green. (Expect a few
in placement / loot / rarity code.)

- [ ] **Step 10: Full gate**

```bash
python -m pytest
python -c "import main; print('IMPORT OK')"
python -m engine.validate data
```
Expected: all green; `IMPORT OK`; validate `OK: … 41 items …`.

- [ ] **Step 11: Commit (propose to user)**

```bash
git add engine/schema/models.py src/game_engine.py src/game_world.py src/data_loader.py \
        tests/test_item_typed.py
git commit -m "refactor(domain): type Item via enriched engine model (strangler B, final)

Enrich Item model with load-bearing fields (damage/combat_effects/tags/allowed_zones/
flags) so weapon damage and consumable heals validate at load. _load_items goes through
the engine loader (self.items = validated models); get_item dumps model->dict so combat/
inventory/use consumers stay dict-based. load_weapon_data/load_consumable_data add a
validation gate and return the same dicts. Starter-weapon placement mutation + direct
self.items reads converted to attribute access. Completes B: classes+enemies+rooms+items."
```

---

## Self-Review

**Spec coverage:** model enrich (S3), self.items seam (S4), get_item boundary (S5), placement
mutation (S6), direct reads (S7), loader gates (S8), tests (S1), sweep (S9). All covered.

**Placeholder scan:** none — every step shows final code; S9 is the mechanical straggler sweep.

**Consistency:** `get_item` returns dict; `_load_items` returns `dict[str, Item]`; 41 items;
`load_weapon_data`/`load_consumable_data` validate then return the raw dict (shape unchanged).
