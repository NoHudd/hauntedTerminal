# Typed Domain: Room — Spec (Strangler B, increment 3)

**Date:** 2026-07-08
**Status:** Approved design, not yet implemented.
**Why:** Third B increment. Types the room **template** on the engine `Room` model and deletes
the dead legacy content validator. Lower marginal value than classes/enemies (the linker
already validates room refs at load), but completes the domain typing and removes a duplicate.

## Plain summary

Rooms load as raw dicts today. We load them through the typed `Room` model (validated at load)
and add the one missing field, `class_restriction`. Because one spot **mutates a room live**
(removing a defeated enemy so it doesn't respawn), rooms stay typed everywhere — every
room-template read switches from dict style (`room["name"]` / `room.get("name")`) to attribute
style (`room.name`). Separately, delete the legacy log-only `_validate_data_references` (a dead
duplicate of the engine linker that has to be hand-patched each typing increment).

## Constraints (global)

- **Zero gameplay change.** Same rooms, navigation, fights.
- Advances adoption: `src/data_loader` imports `engine.content` (third such link; no cycle).
- Content ref-integrity is still enforced by `engine.validate` / `link` (the linker) — that is
  **kept**. Only the redundant legacy validator is removed. Pydantic models validate field
  shapes at load; they do **not** check id resolution (that stays the linker's job).
- 18 rooms. `sim/`+`src/` outside mypy/ruff; `engine/` mypy-strict (Room change type-checks).
- Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
- User does own commits (propose only). One commit.
- Model: `engine/schema/models.py` `Room` (already has name/description/exits/items/npcs/enemies/
  hidden/locked/key_required/zone/zone_level/requires_sudo/path/aliases).

---

## Part A — Type the Room template

### A1. Model
Add to `Room`: `class_restriction: str = ""`. (Everything else is already modeled.)

### A2. Seam
`src/data_loader.load_room_data()` returns `dict[str, Room]` via
`engine.content.loader.load_rooms("data")`. `GameWorld` stores typed templates in `self.rooms`.

### A3. `get_room` returns the LIVE model (no dump boundary)
Unlike enemies, there is no dump-copy: `remove_enemy_from_room` mutates the template's `enemies`
list in place (it must, because `get_enemies_in_room` unions dynamic `enemy_locations` with the
template `enemies` list — a defeated enemy would otherwise reappear). So `get_room` keeps
returning `self.rooms.get(room_id)` (the live `Room` model), and consumers use attributes.

### A4. Consumer conversions (dict → attribute)
Every read of a room template field becomes attribute access. Room is falsy-safe: `if room`
works (None → falsy, model → truthy). Available fields: `name, description,
detailed_description, exits, items, npcs, enemies, hidden, locked, key_required, zone,
zone_level, requires_sudo, class_restriction, path, aliases`.

**`src/game_world.py`:**
- `_initialize_world_state` loop (148-206): `room_data.get("locked"/"hidden"/"key_required")`
  (153-155), `room_data.get("npcs")` (193), `room_data.get("items")` (206) → `room_data.<field>`.
  (The built `room_states[room_id]` stays a **dict** — dynamic state.)
- 704 `room_data.get("zone", "neutral")` → `room_data.zone or "neutral"`.
- 933 `self.rooms.get(room_id, {}).get("zone", "")` →
  `r = self.rooms.get(room_id); room_zone = r.zone if r else ""`.
- `get_items_in_room` (1016-1018): `if room_data and "items" in room_data` /
  `room_data.get("items", []) or []` → `if room_data and room_data.items` / `room_data.items or []`.
- `get_enemies_in_room` (1044-1046): same pattern → `room_data.enemies`.
- `get_npcs_in_room` (1062-1064): same pattern → `room_data.npcs`.
- `remove_enemy_from_room` (1161-1171): `room_data["enemies"]` reads + `.remove(x)` →
  `room_data.enemies` (model list, mutated in place — the live-model requirement).
- `get_exits` (1229): `room.get("exits", [])` → `room.exits`.
- `build_room_description` / room-info builder (1291+): convert **every** room-template field
  read in the method to attribute access.

**`src/command_handler.py`:**
- 452 `room = self.world.get_room(room_id)` + subsequent room-field reads → attributes.

**`src/commands/navigation.py`:**
- 259 `new_room.get("name", directory)` → `new_room.name if new_room else directory`.

Sweep method: after converting the known sites, run the **full suite** — any missed consumer
raises `AttributeError` (the same sweep that caught stragglers in the enemy increment).

---

## Part B — Delete the legacy content validator

`src/game_engine.py::_validate_data_references` (method 174-211) + its call (line 155) are a
log-only, never-stops duplicate of the engine linker. It also reads rooms/enemies as dicts (so
it would need conversion anyway). **Delete the method and the call.**

Rationale (user decision): the engine linker (`engine.validate` / `link`, run in CI + tests)
remains the single referential-integrity check; typed models catch field-shape bugs at load.
The legacy validator only logged (never halted), so removing it loses no real protection.

---

## Zero gameplay change / tests

- No mutation lost (`get_room` returns the live model; `room.enemies.remove` mutates in place).
- Room refs still validated by the linker; field shapes validated by the model at load.
- Tests (`tests/test_room_typed.py`):
  - `load_room_data()` returns `Room` instances; all 18 present.
  - A headless run: enter a room, start + win a fight, confirm the defeated enemy does **not**
    reappear in `get_enemies_in_room` (guards the live-model mutation).
  - `get_exits` / navigation into a class-restricted room (`opt_mage_tower`) works.
- Existing `test_headless` / `test_commands` / `test_content` cover the rest.

## Non-goals

- Not typing Item (later, if at all — thin model + mutation).
- Not fixing the `room_state.get("class_restriction")`-always-None dead indicator (out of scope;
  zero-change).
- Not changing the `get_enemies_in_room` template-union hack (leave behavior as-is).
- Not wiring the engine linker into live startup (user chose to keep it CI/test-only).
