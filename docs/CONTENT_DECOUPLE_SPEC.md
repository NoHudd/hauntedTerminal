# Content Decoupling Spec — Flat Items + Room Paths (Strangler Step C)

**Date:** 2026-07-07
**Status:** Approved design, not yet implemented.
**Why:** First concrete step of the `src/` → `engine/` strangler (the C in the agreed
C → B → A order). Kills two "silent failure" bugs in content loading and advances the
typed core, without changing gameplay.

## Plain summary

Two spots in content loading can break quietly. We fix both, keep the game identical.

1. **Items** need a "header word" at the top of each file (`weapons:`, `armor:`…) that must
   match the filename. Get it wrong → that file loads **zero items, silently**. Fix: drop
   the header; each file just lists items (every item already says `type: weapon` etc.).
2. **Room paths/nicknames** (what `cd /var` or `cd dungeon` resolves to) live in **three**
   places that must agree. Forget one when adding a room → navigation breaks silently. Fix:
   each room file states its own `path` + `aliases`; the game builds the lookup from that.

Both changes also teach `engine.validate` the new shape so mistakes fail **loud, at load**.

## Constraints (global)

- **Zero gameplay change.** Same 41 items, same ids/stats. Same navigation — every `cd`
  string resolves to the same room it does today (proven by a snapshot test, below).
- **Full strangler:** change `src/` runtime AND `engine/` (schema + validate guards) + tests.
- **Authoritative counts:** 18 rooms, 41 items. Classes Guardian/Weaver/Shaman.
- YAML stays snake_case. `sim/` and `src/` stay outside mypy/ruff; `engine/` additions are
  mypy-strict.
- Gate per part: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
  Run in venv; bare `pytest` fails (`No module named 'src'`) — use `python -m pytest`.
- User does own commits (propose commands only). Two commits: C1, then C2.

---

## Part C1 — Flatten item YAML

### Current shape (the bug)
`data/items/*.yaml` (5 files: `armor`, `consumables`, `keys`, `lore_fragments`, `weapons`).
Each file wraps its items under one key equal to the filename stem:
```yaml
weapons:              # <- must equal filename "weapons"
  segfault_shield:
    type: "weapon"
    ...
```
`game_engine._load_items` (src/game_engine.py:247-279) computes
`category = filename-stem` and reads `data.get(category, {})`. If the wrapper key and
filename ever disagree (rename, typo), the file loads as **zero items with only a debug
log** — a silent content loss. `engine/content/loader.load_items` (engine/content/loader.py:97-108)
has the same wrapper assumption.

Every item already carries an explicit `type:` (weapon/armor/consumable/key/lore), so the
wrapper carries no information the item doesn't already have.

### Target shape
Each `data/items/*.yaml` is a flat map of `item_id: {def}` with no wrapper:
```yaml
segfault_shield:
  type: "weapon"
  ...
```
Files stay split by category for authoring convenience; `type` (now **required** on every
item) is the source of truth for category, not the filename.

### Changes
- **Data:** dedent all 5 item files one level; delete the wrapper key. (Item bodies unchanged.)
- **`game_engine._load_items`:** read each file's top-level dict directly as `id → def`.
  Drop the `category`/`data.get(category)` logic. For each item: require `type` present
  (loud error + skip if missing); on a **duplicate id across files**, raise (don't silently
  overwrite). Total item count must stay 41.
- **`data_loader.load_weapon_data(id)` / `load_consumable_data(id)`** (src/data_loader.py:41,176):
  repoint to the flat read (read the file as a flat id→def map). Keep the function names and
  signatures so existing call sites don't change.
- **`engine/content/loader.load_items`:** replace the `for category, items in doc.items()`
  wrapper loop with a flat `for item_id, body in doc.items()` per file. Raise
  `ContentValidationError` on a duplicate id across files. `Item` schema model is unchanged
  (its `type` discriminator already exists).
- **`engine.validate`:** duplicate-item-id and missing-`type` now surface as loud validation
  errors (they were silent or impossible to express before).

### C1 tests
- `test_content`: item registry still resolves to **41** items with the same ids.
- New: a temp item file **without** a wrapper (flat) loads; a wrapper-style file no longer
  needed — the loader reads flat.
- New: two files declaring the same item id → `engine.validate` raises naming the id.
- New: an item missing `type` → loud error (validate raises).

### C1 ship gate
`python -m pytest` green · `engine.validate data` → `OK: … 41 items …` · `import main` clean.

---

## Part C2 — Room path/aliases from YAML

### Current shape (the bug)
The mapping from a typed string (`/var`, `var`, `dungeon`) to a room id is spread across
three hand-maintained places that must stay in sync:
1. `src/room_paths.py::ROOM_ID_TO_PATH` — `room_id → canonical path` (18 entries), used by
   the UI exits strip (`view_builder.py:12,127`) and `room_path()`.
2. `command_handler.room_aliases` (src/command_handler.py:47-114, ~65 entries) —
   `input string → room_id`, including arbitrary synonyms (`dungeon`→`var_dungeon`,
   `forest`→`mnt_forest`) and `/`-prefixed forms.
3. The room YAML itself (the room's existence).

Add a room and miss #1 or #2 → its display path or its `cd` navigation breaks, silently.

### Target shape
Each of the 18 `data/rooms/*.yml` declares its own nav identity:
```yaml
path: /var                       # canonical path (required, unique)
aliases: [var, dungeon, /var/dungeon]   # every synonym it has today, verbatim
```
(The existing `zone:` field is unrelated — it's the loot bucket — and stays.)

A load-time builder derives the two lookup tables from room data:
`build_nav_tables(rooms) -> (id_to_path: dict[str,str], alias_to_id: dict[str,str])`.
- `id_to_path[room_id] = room.path` — display only (exits strip, `room_path()`).
- `alias_to_id` maps **every entry in `aliases` → room id**, and nothing else. The builder
  does **not** auto-add `path` or the bare room id. Today's two tables are independent and
  slightly inconsistent (e.g. `mirror_sector` has display path `/mirror` but **no** `cd`
  alias for it), so `path` navigability is encoded by whether the path string is listed in
  `aliases` — copied verbatim from today. `cd <room_id>` continues to work via the resolver's
  existing id fallback (unchanged). This reproduces today's `room_aliases` byte-for-byte.

Both consumers are populated from the builder instead of hand-written literals:
- `command_handler.room_aliases` ← `alias_to_id` (the hardcoded dict at lines 47-114 is deleted).
- `room_paths.ROOM_ID_TO_PATH` ← `id_to_path` (the hardcoded dict is deleted); `room_path()`
  keeps its signature and fallback behavior; `view_builder`'s import keeps working.

### Migration (verbatim, no invention)
The `path:` and `aliases:` values are copied **exactly** from today's `ROOM_ID_TO_PATH` +
`room_aliases`, so no navigation string changes. Example (`var_dungeon`): today its path is
`/var` and its `cd` aliases are `/var, /var/dungeon, var, dungeon`. In YAML:
`path: /var`, `aliases: [/var, /var/dungeon, var, dungeon]` — the aliases list holds every
string that resolves to it today, path form included.

### engine guard
- `Room` schema model gains `path: str` and `aliases: list[str] = []`.
- The linker / `engine.validate` enforces:
  - every room has a non-empty `path`;
  - **paths are unique** across rooms;
  - **no alias collides** — the same string never maps to two different room ids (across all
    rooms' `path` + `aliases` + id). A collision raises `ContentValidationError` naming the
    string and the two rooms.

### C2 tests (the zero-change safety net)
- **Snapshot test:** freeze today's exact `room_aliases` dict and `ROOM_ID_TO_PATH` as a
  fixture in the test, then assert `build_nav_tables(load_rooms())` reproduces them
  **byte-for-byte**. If any `cd` string would resolve differently, this fails.
- New: a room missing `path` → `engine.validate` raises.
- New: two rooms declaring the same `path` (or a shared alias) → validate raises naming both.

### C2 ship gate
`python -m pytest` green (incl. snapshot) · `engine.validate data` → `OK: 18 rooms …` ·
`import main` clean.

---

## Sequencing

1. **C1 (items)** — independent, ships + commits alone.
2. **C2 (rooms)** — independent, ships + commits alone.

Each is a self-contained strangler step: working, test-green, gameplay-identical.

## Non-goals

- No item stat/id changes; no merging item files; no new item categories.
- No new navigation strings, no removed synonyms (verbatim migration only).
- No `src/` → `engine/` domain move beyond content loading (that's later B/A work).
- No change to `zone`/loot, combat, UI rendering, or saves.

## Open decisions (defaults chosen)

- Item files stay 5, split by category (authoring clarity); `type` drives category. (Not merged.)
- `aliases` lists **every** string that resolves to the room in today's `room_aliases` —
  including the path form(s) and any synonym equal to the room id. The builder auto-adds
  nothing (not `path`, not id); it just unions the `aliases` lists. `path` is a separate,
  display-only field. This reproduces today's table exactly, including quirks like
  `mirror_sector` (path `/mirror`, empty `aliases`).
- Duplicate-id / collision handling: **raise** (fail loud), never silently pick one.
