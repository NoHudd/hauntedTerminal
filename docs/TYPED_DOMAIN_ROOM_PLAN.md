# Typed Domain: Room — Implementation Plan (Strangler B, increment 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Type the room template on the engine `Room` model (zero gameplay change) and delete the dead legacy content validator. One commit.

**Architecture:** `load_room_data` returns typed `Room` models; `get_room` returns the **live** model (a room-enemy mutation needs it), so every room-template read becomes attribute access. The log-only `_validate_data_references` is deleted; `engine.validate`/linker stays the ref check.

**Tech Stack:** Python 3.11, Pydantic v2, pytest.

## Global Constraints

- **Zero gameplay change.** Refs still validated by the linker; models validate field shapes at load.
- Outer `self.rooms` dict keeps dict semantics; only **values** are models. `get_room` returns a model.
- No import cycle: `data_loader → engine.content.loader → engine.schema`.
- `sim/`+`src/` outside mypy/ruff; `engine/` mypy-strict (Room change type-checks).
- Gate: `source venv/bin/activate`; `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
- User does own commits (propose; never run `git commit`). ONE commit.
- Spec: `docs/TYPED_DOMAIN_ROOM_SPEC.md`. Available `Room` fields: name, description,
  detailed_description, exits, items, npcs, enemies, hidden, locked, key_required, zone,
  zone_level, requires_sudo, class_restriction, path, aliases.

## File Structure

| File | Change |
|---|---|
| `engine/schema/models.py` `Room` | +`class_restriction: str = ""` |
| `src/data_loader.py:138` `load_room_data` | return `dict[str, Room]` via engine loader |
| `src/game_world.py` | ~14 room-template reads → attributes; live-model mutation |
| `src/command_handler.py:462,464` | room field reads → attributes |
| `src/commands/navigation.py:259` | `new_room.get("name")` → attribute |
| `src/game_engine.py` | DELETE `_validate_data_references` (method + call) |
| `tests/test_room_typed.py` (new) | typed loader + live-mutation + navigation |

---

## Task 1: Type Room + delete legacy validator (atomic, one commit)

- [ ] **Step 1: Write the failing test** (`tests/test_room_typed.py`)

```python
"""Room templates are typed; get_room returns a live model; enemy removal persists."""
from __future__ import annotations

from engine.schema import Room


def test_load_room_data_returns_typed_models():
    from src.data_loader import load_room_data
    rooms = load_room_data()
    assert len(rooms) == 18
    for rid, r in rooms.items():
        assert isinstance(r, Room), (rid, type(r))
        assert r.name


def test_defeated_enemy_does_not_reappear():
    # get_enemies_in_room unions dynamic + template enemies; removal must mutate
    # the live template model so a cleared enemy stays gone.
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        # find a room that has an enemy
        room_id = next(
            (rid for rid in world.rooms if world.get_enemies_in_room(rid)), None
        )
        assert room_id, "expected some room with an enemy"
        eid = world.get_enemies_in_room(room_id)[0]
        world.remove_enemy_from_room(eid)
        assert eid not in world.get_enemies_in_room(room_id)
    finally:
        s.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_room_typed.py -v`
Expected: `test_load_room_data_returns_typed_models` FAILS (loader returns dicts).

- [ ] **Step 3: Add `class_restriction` to `Room` (engine/schema/models.py)**

After `requires_sudo` (and before `path`):
```python
    class_restriction: str = ""
```

- [ ] **Step 4: Flip `src/data_loader.load_room_data` to typed models**

```python
def load_room_data():
    """Load all rooms as typed engine Room models (id -> model)."""
    try:
        from engine.content.loader import load_rooms
        rooms = {str(rid): r for rid, r in load_rooms("data").items()}
        return rooms
    except Exception as e:
        debug_log(f"ERROR loading room data: {e}")
        return {}
```

- [ ] **Step 5: Convert `src/game_world.py` template reads → attributes**

`_initialize_world_state` loop:
```python
            self.room_states[room_id] = {
                "visited": False,
                "locked": room_data.locked,
                "hidden": room_data.hidden,
                "key_required": room_data.key_required,
            }
```
`193`: `for npc_id in room_data.npcs or []:`  ·  `206`: `for item_id in room_data.items or []:`
`704`: `zone = room_data.zone or "neutral"`
`933`:
```python
            r = self.rooms.get(room_id)
            room_zone = r.zone if r else ""
```
`get_items_in_room` (1016-1018):
```python
        room_data = self.get_room(room_id)
        if room_data and room_data.items:
            items_in_room_data = room_data.items or []
```
`get_enemies_in_room` (1044-1046): same shape → `room_data.enemies`.
`get_npcs_in_room` (1062-1064): same shape → `room_data.npcs`.
`remove_enemy_from_room` (1161-1171):
```python
                if enemy_id in room_data.enemies:
                    room_data.enemies.remove(enemy_id)
```
and the second block:
```python
                for e_id in list(room_data.enemies):
                    if ...:
                        room_data.enemies.remove(e_id)
```
`get_exits` (1229): `exits = room.exits`
`build_room_description` (1296-1297):
```python
        name = room_data.name or 'An Unnamed Room'
        description = room_data.description or 'A featureless space.'
```

- [ ] **Step 6: Convert `src/command_handler.py` (462, 464)**

```python
        room_name = room.name or room_id
        title = Text(f"{room_name}", style="bold white on dark_blue")
        description = Text(room.description or "No description available.")
```

- [ ] **Step 7: Convert `src/commands/navigation.py` (259)**

```python
        new_room = ctx.world.get_room(directory)
        room_name = new_room.name if new_room else directory
```

- [ ] **Step 8: Delete the legacy validator (src/game_engine.py)**

Remove the call at line ~155 (`self._validate_data_references(rooms, items, enemies)`) and the
entire `_validate_data_references` method (~174-211).

- [ ] **Step 9: Run the suite; sweep stragglers**

Run: `python -m pytest 2>&1 | tail -20`
Any `AttributeError: 'Room' object has no attribute 'get'` (or `... no attribute '__getitem__'`)
points to a missed consumer — convert that `room.get("X")`/`room["X"]`/`"X" in room` to
`room.X` and re-run until green. (Same sweep that finished the enemy increment.)

- [ ] **Step 10: Full gate**

Run:
```bash
python -m pytest
python -c "import main; print('IMPORT OK')"
python -m engine.validate data
```
Expected: all green; `IMPORT OK`; validate `OK: 18 rooms …`.

- [ ] **Step 11: Commit (propose to user)**

```bash
git add engine/schema/models.py src/data_loader.py src/game_world.py \
        src/command_handler.py src/commands/navigation.py src/game_engine.py \
        tests/test_room_typed.py
git commit -m "refactor(domain): type Room via engine model; delete dead legacy validator (strangler B)

load_room_data returns typed Room models (+class_restriction). get_room returns the
live model (remove_enemy_from_room mutates the template enemies list in place, which
get_enemies_in_room unions with dynamic locations). All room-template reads switch to
attribute access. Deleted the log-only _validate_data_references duplicate; engine.validate
/linker remains the single referential-integrity check, models validate field shapes at load."
```

---

## Self-Review

**Spec coverage:** model (S3), seam (S4), get_room live-model + conversions (S5-7), validator
delete (S8), tests (S1), sweep (S9). All covered.

**Placeholder scan:** none — every step shows final code. S9 is an explicit straggler sweep,
not a placeholder (the transform is mechanical: any room dict-op → attribute).

**Consistency:** `get_room` returns a model everywhere; `load_room_data -> dict[str, Room]`;
18 rooms; `remove_enemy_from_room` mutates `room_data.enemies` (live model list).
