# Content Decoupling — Implementation Plan (Strangler Step C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kill two silent content-loading failures — item-file wrapper keys and the triple-synced room path/alias tables — by moving both to per-file data with fail-loud validation, without changing gameplay.

**Architecture:** Two independent parts. C1 flattens `data/items/*.yaml` (drop wrapper key; `type` becomes required) and updates both the `src/` runtime loader and the `engine/` typed loader + validate. C2 adds `path:`/`aliases:` to each room YAML and builds the nav tables at load, replacing two hardcoded dicts, with an engine validate guard and a byte-for-byte snapshot test proving navigation is unchanged.

**Tech Stack:** Python 3.11, PyYAML, Pydantic v2 (engine schema), pytest.

## Global Constraints

- **Zero gameplay change.** Same 41 items (ids/stats). Navigation resolves identically —
  proven by the C2 snapshot test.
- **Authoritative counts:** 18 rooms, 41 items. Classes Guardian/Weaver/Shaman.
- YAML stays snake_case. `sim/` and `src/` stay out of mypy/ruff; `engine/` additions are mypy-strict.
- Gate per part: `source venv/bin/activate` then `python -m pytest` + `python -m engine.validate data`
  + `python -c "import main"`. Bare `pytest` fails (`No module named 'src'`) — use `python -m pytest`.
- User does own commits (propose commands; never run `git commit`). Two commits: C1, then C2.
- Spec: `docs/CONTENT_DECOUPLE_SPEC.md`.

## File Structure

| File | Part | Change |
|---|---|---|
| `data/items/*.yaml` (5) | C1 | Drop wrapper key; flat `id: {def}` |
| `src/game_engine.py:247` `_load_items` | C1 | Flat read; require `type`; raise on dup id |
| `src/data_loader.py:41,176` | C1 | Repoint weapon/consumable reads to flat files |
| `engine/content/loader.py:97` `load_items` | C1 | Flat per-file read; raise on dup id / missing type |
| `engine/content/linker.py` | C1+C2 | Add item-dup + nav checks (or in loader/validate) |
| `data/rooms/*.yml` (18) | C2 | Add `path:` + `aliases:` |
| `src/room_paths.py` | C2 | `build_nav_tables(rooms)`; tables built from data |
| `src/command_handler.py:47` | C2 | `room_aliases` built from data (delete literal) |
| `engine/schema/models.py:48` `Room` | C2 | Add `path`, `aliases` fields |
| `tests/test_content.py`, new `tests/test_nav.py` | C1+C2 | Guards + snapshot |

---

## Part C1 — Flatten item YAML

### Task 1: Flatten the item files + flat engine loader

**Files:**
- Modify: `data/items/armor.yaml`, `consumables.yaml`, `keys.yaml`, `lore_fragments.yaml`, `weapons.yaml`
- Modify: `engine/content/loader.py:97-108`
- Test: `tests/test_content.py`

**Interfaces:**
- Produces: `engine.content.loader.load_items(data_dir) -> dict[ItemId, Item]` reading flat files; raises `ContentValidationError` on duplicate id or missing `type`.

- [ ] **Step 1: Write the failing test** (add to `tests/test_content.py`)

```python
def test_items_load_flat_and_count_41():
    from engine.content.loader import load_items
    items = load_items("data")
    assert len(items) == 41, len(items)
    # every item carries an explicit type (no wrapper-derived category)
    assert all(getattr(i, "type", None) for i in items.values())

def test_duplicate_item_id_raises(tmp_path):
    import pytest
    from engine.schema import ContentValidationError
    from engine.content.loader import load_items
    d = tmp_path / "items"; d.mkdir()
    (d / "a.yaml").write_text("sword:\n  name: A\n  type: weapon\n")
    (d / "b.yaml").write_text("sword:\n  name: B\n  type: weapon\n")
    (tmp_path / "rooms").mkdir()
    with pytest.raises(ContentValidationError):
        load_items(str(tmp_path))
```

- [ ] **Step 2: Run to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_content.py::test_duplicate_item_id_raises tests/test_content.py::test_items_load_flat_and_count_41 -v`
Expected: FAIL (loader still wrapper-based → count 0 or wrong; no dup detection).

- [ ] **Step 3: Rewrite `engine/content/loader.load_items` to flat**

Replace the body (lines 97-108) with:

```python
def load_items(data_dir: str = DATA_DIR) -> dict[ItemId, Item]:
    out: dict[ItemId, Item] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.y*ml"))):
        doc = _read_yaml(path)
        for item_id, body in doc.items():
            if not isinstance(body, dict):
                continue
            if "type" not in body:
                raise ContentValidationError(f"{path}: item '{item_id}' missing 'type'")
            iid = ItemId(item_id)
            if iid in out:
                raise ContentValidationError(
                    f"{path}: duplicate item id '{item_id}' (already defined elsewhere)"
                )
            out[iid] = _build(Item, iid, body, path)
    return out
```

- [ ] **Step 4: Flatten the 5 YAML files**

For each `data/items/*.yaml`: delete the top wrapper line (`weapons:`, `armor:`, `consumables:`,
`keys:`, `lore_fragments:`) and dedent every remaining line by one level (2 spaces). Item ids
become top-level keys. Comments stay. Do not touch any item body content.

Verify each file parses and item count holds:
```bash
python -c "import glob,yaml; n=sum(len(yaml.safe_load(open(f))) for f in glob.glob('data/items/*.yaml')); print(n)"   # expect 41
```

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_content.py -v`
Expected: PASS (41 items, dup raises).

- [ ] **Step 6: Commit (propose to user)**

```bash
git add data/items/ engine/content/loader.py tests/test_content.py
git commit -m "refactor(content): flat item files (drop wrapper key); fail loud on dup id / missing type"
```

### Task 2: Point the src runtime loaders at the flat files

**Files:**
- Modify: `src/game_engine.py:247-279` `_load_items`
- Modify: `src/data_loader.py:41-78` `load_weapon_data`, `:176-201` `load_consumable_data`
- Test: `tests/test_commands.py` (existing playthrough covers item pickup/equip/use)

**Interfaces:**
- Consumes: flat `data/items/*.yaml` from Task 1.
- Produces: `_load_items() -> dict[str, dict]` with 41 items, each carrying `type`; raises on dup id.

- [ ] **Step 1: Rewrite `_load_items` (src/game_engine.py:247)**

```python
    def _load_items(self) -> Dict[str, Any]:
        """Load all items from flat YAML files into a single dict (id -> def)."""
        items: Dict[str, Any] = {}
        items_dir = 'data/items'
        if not os.path.exists(items_dir):
            logger.warning(f"Items directory {items_dir} does not exist")
            return items
        for filename in os.listdir(items_dir):
            if not filename.endswith(('.yaml', '.yml')):
                continue
            filepath = os.path.join(items_dir, filename)
            try:
                with open(filepath, 'r') as file:
                    data = yaml.safe_load(file) or {}
            except Exception as e:
                logger.error(f"Error loading items from {filename}: {e}")
                continue
            for item_id, item_data in data.items():
                if not isinstance(item_data, dict):
                    continue
                if 'type' not in item_data:
                    logger.error(f"{filename}: item '{item_id}' missing 'type' — skipped")
                    continue
                if item_id in items:
                    raise ValueError(f"duplicate item id '{item_id}' in {filename}")
                item_data['id'] = item_id
                items[item_id] = item_data
        logger.info(f"Total items loaded: {len(items)}")
        return items
```

- [ ] **Step 2: Repoint `data_loader.load_weapon_data` (src/data_loader.py:41)**

Change the weapons read from `data.get("weapons", {})` to treat the file as a flat map:

```python
def load_weapon_data(weapon_id):
    """Load data for a specific weapon from the flat weapons.yaml."""
    try:
        filepath = 'data/items/weapons.yaml'
        with open(filepath, 'r') as f:
            weapons = yaml.safe_load(f) or {}
        weapon_data = weapons.get(weapon_id)
        if weapon_data:
            weapon_data = dict(weapon_data)
            weapon_data['id'] = weapon_id
            return weapon_data
        debug_log(f"ERROR: Weapon {weapon_id} not found in weapons.yaml")
        return None
    except Exception as e:
        debug_log(f"ERROR loading weapon {weapon_id}: {e}")
        return None
```

(Preserve the existing imports/`debug_log` usage already in the file; keep the function name/signature.)

- [ ] **Step 3: Repoint `load_consumable_data` (src/data_loader.py:176)**

Change the cache fill from `data.get("consumables", {})` to the flat map:

```python
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f) or {}
            _consumables_data_cache = data if isinstance(data, dict) else {}
```

(Keep the `filepath = 'data/items/consumables.yaml'`, caching, and lookup logic below it unchanged.)

- [ ] **Step 4: Run the full suite + import**

Run: `python -m pytest && python -c "import main; print('IMPORT OK')"`
Expected: all pass; `IMPORT OK`.

- [ ] **Step 5: Validate content graph**

Run: `python -m engine.validate data`
Expected: `OK: 18 rooms, 41 items, 24 enemies, 12 npcs, 3 classes, 10 abilities, 11 attacks — all references resolve.`

- [ ] **Step 6: Commit (propose to user)**

```bash
git add src/game_engine.py src/data_loader.py
git commit -m "refactor(content): src item loaders read flat files; raise on dup id"
```

---

## Part C2 — Room path/aliases from YAML

### Task 3: Add path/aliases to room schema + validate guard

**Files:**
- Modify: `engine/schema/models.py:48-66` `Room`
- Modify: `engine/content/linker.py` (add `find_nav_problems`, call in `link`)
- Test: `tests/test_content.py`

**Interfaces:**
- Produces: `Room.path: str`, `Room.aliases: list[str]`; `find_nav_problems(content) -> list[str]`
  flagging missing path, duplicate path, alias collisions; `link()` raises on any.

- [ ] **Step 1: Write the failing test** (`tests/test_content.py`)

```python
def test_live_rooms_have_unique_paths_and_no_alias_collisions():
    from engine.content.loader import load_rooms
    from engine.content.world import GameContent
    from engine.content.linker import find_nav_problems
    rooms = load_rooms("data")
    content = GameContent(rooms=rooms, items={}, enemies={}, npcs={},
                          classes={}, abilities={}, attacks={})
    assert find_nav_problems(content) == []
    assert all(r.path for r in rooms.values()), "every room needs a path"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_content.py::test_live_rooms_have_unique_paths_and_no_alias_collisions -v`
Expected: FAIL (`find_nav_problems` undefined; rooms lack `path`).

- [ ] **Step 3: Add fields to `Room` (engine/schema/models.py:60, after `zone_level`)**

```python
    path: str = ""
    aliases: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add `find_nav_problems` to `engine/content/linker.py`** (and call it in `link`)

```python
def find_nav_problems(content: GameContent) -> list[str]:
    """Room path/alias integrity (empty == clean)."""
    problems: list[str] = []
    path_owner: dict[str, str] = {}
    alias_owner: dict[str, str] = {}
    for rid, room in content.rooms.items():
        if not room.path:
            problems.append(f"room '{rid}': missing 'path'")
        elif room.path in path_owner:
            problems.append(
                f"room '{rid}': path '{room.path}' already used by '{path_owner[room.path]}'"
            )
        else:
            path_owner[room.path] = str(rid)
        for alias in room.aliases:
            if alias in alias_owner and alias_owner[alias] != str(rid):
                problems.append(
                    f"alias '{alias}' maps to both '{alias_owner[alias]}' and '{rid}'"
                )
            else:
                alias_owner[alias] = str(rid)
    return problems
```

In `link()` (linker.py:87), extend the fatal check:

```python
def link(content: GameContent) -> GameContent:
    problems = find_broken_references(content) + find_nav_problems(content)
    if problems:
        raise DanglingReferenceError(
            f"{len(problems)} content problem(s):\n  - " + "\n  - ".join(problems)
        )
    return content
```

- [ ] **Step 5: Add `path:`/`aliases:` to all 18 room YAMLs**

Append these two fields to each `data/rooms/<id>.yml` (values copied verbatim from today's
`ROOM_ID_TO_PATH` + `command_handler.room_aliases`). YAML list form is fine, e.g.:
```yaml
path: /var
aliases: ["/var", "/var/dungeon", "var", "dungeon"]
```

| room file | `path` | `aliases` |
|---|---|---|
| home_grove | `/home` | `/home, /home/grove, home, grove` |
| var_dungeon | `/var` | `/var, /var/dungeon, var, dungeon` |
| mnt_forest | `/mnt` | `/mnt, /mnt/forest, mnt, forest` |
| bin_armory | `/bin` | `/bin, /bin/armory, bin, armory` |
| usr_lib_arcane | `/usr` | `/usr, /usr/lib, /usr/lib/arcane, usr, lib, arcane` |
| usr_share_games | `/usr/share/games` | `/usr/share, /usr/share/games, share, games` |
| cowsay_secret | `/cowsay` | `/usr/share/games/cowsay, /cowsay, cowsay` |
| opt_mage_tower | `/opt` | `/opt, /opt/tower, /opt/mage_tower, opt, tower` |
| srv_warrior_tomb | `/srv` | `/srv, /srv/tomb, /srv/warrior_tomb, srv, tomb` |
| proc_secrets | `/proc` | `/proc, /proc/secrets, proc, secrets` |
| etc_hidden_configs | `/etc` | `/etc, /etc/configs, etc, configs` |
| dev_null_void | `/dev` | `/dev, /dev/null, dev, null, void` |
| ghost_hidden | `/ghost` | `/ghost, ghost` |
| archive | `/archive` | `/archive, archive` |
| deprecated_dir | `/deprecated` | `/deprecated, deprecated` |
| root | `/` | `/, /root, root` |
| core | `/core` | `/core, core` |
| mirror_sector | `/mirror` | *(empty list `[]`)* |

- [ ] **Step 6: Run tests + validate**

Run: `python -m pytest tests/test_content.py -v && python -m engine.validate data`
Expected: PASS; validate OK (18 rooms).

- [ ] **Step 7: Commit (propose to user)**

```bash
git add engine/schema/models.py engine/content/linker.py data/rooms/ tests/test_content.py
git commit -m "feat(content): room path/aliases in YAML + validate uniqueness guard"
```

### Task 4: Build nav tables from data; delete the hardcoded dicts

**Files:**
- Modify: `src/room_paths.py`
- Modify: `src/command_handler.py:47-114`
- Test: new `tests/test_nav.py`

**Interfaces:**
- Consumes: `Room.path`/`aliases` (Task 3), the live `world.rooms` dict (id -> room dict).
- Produces: `src.room_paths.build_nav_tables(rooms) -> tuple[dict[str,str], dict[str,str]]`
  returning `(id_to_path, alias_to_id)`.

- [ ] **Step 1: Write the failing snapshot test** (`tests/test_nav.py`)

The fixtures below are today's tables, frozen. The builder must reproduce them exactly.

```python
"""Navigation tables are built from room YAML and must match the legacy hardcoded maps."""
from src.room_paths import build_nav_tables
from src.data_loader import load_room_data

LEGACY_ID_TO_PATH = {
    "home_grove": "/home", "var_dungeon": "/var", "mnt_forest": "/mnt",
    "bin_armory": "/bin", "usr_lib_arcane": "/usr", "opt_mage_tower": "/opt",
    "srv_warrior_tomb": "/srv", "proc_secrets": "/proc", "etc_hidden_configs": "/etc",
    "dev_null_void": "/dev", "ghost_hidden": "/ghost", "archive": "/archive",
    "deprecated_dir": "/deprecated", "root": "/", "core": "/core",
    "cowsay_secret": "/cowsay", "mirror_sector": "/mirror",
    "usr_share_games": "/usr/share/games",
}

LEGACY_ALIAS_TO_ID = {
    "/home": "home_grove", "/home/grove": "home_grove", "/var": "var_dungeon",
    "/var/dungeon": "var_dungeon", "/mnt": "mnt_forest", "/mnt/forest": "mnt_forest",
    "/bin": "bin_armory", "/bin/armory": "bin_armory", "/usr": "usr_lib_arcane",
    "/usr/lib": "usr_lib_arcane", "/usr/lib/arcane": "usr_lib_arcane",
    "/usr/share": "usr_share_games", "/usr/share/games": "usr_share_games",
    "/usr/share/games/cowsay": "cowsay_secret", "/cowsay": "cowsay_secret",
    "/opt": "opt_mage_tower", "/opt/tower": "opt_mage_tower",
    "/opt/mage_tower": "opt_mage_tower", "/srv": "srv_warrior_tomb",
    "/srv/tomb": "srv_warrior_tomb", "/srv/warrior_tomb": "srv_warrior_tomb",
    "/proc": "proc_secrets", "/proc/secrets": "proc_secrets",
    "/etc": "etc_hidden_configs", "/etc/configs": "etc_hidden_configs",
    "/dev": "dev_null_void", "/dev/null": "dev_null_void", "/ghost": "ghost_hidden",
    "/archive": "archive", "/deprecated": "deprecated_dir", "/": "root",
    "/root": "root", "/core": "core",
    "home": "home_grove", "grove": "home_grove", "var": "var_dungeon",
    "dungeon": "var_dungeon", "mnt": "mnt_forest", "forest": "mnt_forest",
    "bin": "bin_armory", "armory": "bin_armory", "usr": "usr_lib_arcane",
    "lib": "usr_lib_arcane", "arcane": "usr_lib_arcane", "share": "usr_share_games",
    "games": "usr_share_games", "cowsay": "cowsay_secret", "opt": "opt_mage_tower",
    "tower": "opt_mage_tower", "srv": "srv_warrior_tomb", "tomb": "srv_warrior_tomb",
    "proc": "proc_secrets", "secrets": "proc_secrets", "etc": "etc_hidden_configs",
    "configs": "etc_hidden_configs", "dev": "dev_null_void", "null": "dev_null_void",
    "void": "dev_null_void", "ghost": "ghost_hidden", "deprecated": "deprecated_dir",
    "archive": "archive", "root": "root", "core": "core",
}

def test_built_tables_match_legacy():
    id_to_path, alias_to_id = build_nav_tables(load_room_data())
    assert id_to_path == LEGACY_ID_TO_PATH
    assert alias_to_id == LEGACY_ALIAS_TO_ID
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_nav.py -v`
Expected: FAIL (`build_nav_tables` undefined).

- [ ] **Step 3: Add `build_nav_tables` to `src/room_paths.py`**

Replace the hardcoded `ROOM_ID_TO_PATH` literal with a data-built table. Keep a module-level
`ROOM_ID_TO_PATH` dict object (so `view_builder`'s `from src.room_paths import ROOM_ID_TO_PATH`
keeps working) but populate it via `refresh_from_rooms`, mutating in place.

```python
from __future__ import annotations

ROOM_ID_TO_PATH: dict[str, str] = {}


def build_nav_tables(rooms: dict) -> tuple[dict[str, str], dict[str, str]]:
    """From room data (id -> room dict/obj) build (id_to_path, alias_to_id)."""
    id_to_path: dict[str, str] = {}
    alias_to_id: dict[str, str] = {}
    for rid, room in rooms.items():
        get = room.get if isinstance(room, dict) else (lambda k, d=None: getattr(room, k, d))
        path = get("path", "") or ""
        if path:
            id_to_path[str(rid)] = path
        for alias in (get("aliases", []) or []):
            alias_to_id[str(alias)] = str(rid)
    return id_to_path, alias_to_id


def refresh_from_rooms(rooms: dict) -> dict[str, str]:
    """Rebuild ROOM_ID_TO_PATH in place and return alias_to_id."""
    id_to_path, alias_to_id = build_nav_tables(rooms)
    ROOM_ID_TO_PATH.clear()
    ROOM_ID_TO_PATH.update(id_to_path)
    return alias_to_id


def room_path(room_id: str) -> str:
    """Path for a room id, falling back to the id itself."""
    return ROOM_ID_TO_PATH.get(room_id, room_id)
```

- [ ] **Step 4: Build `command_handler.room_aliases` from data**

In `CommandHandler.__init__` (src/command_handler.py), delete the hardcoded `self.room_aliases = { ... }`
literal (lines 47-114) and replace with:

```python
        # Navigation aliases are built from each room's path/aliases (data-driven).
        from src import room_paths
        self.room_aliases = room_paths.refresh_from_rooms(self.world.rooms)
```

(Verified: `CommandHandler.__init__` sets `self.world = world`, and `GameWorld.rooms`
(game_world.py:23) is the id -> room-dict mapping. `load_room_data()` returns raw YAML dicts,
so `path`/`aliases` are present as dict keys — `build_nav_tables` reads them via `room.get`.)

- [ ] **Step 5: Run nav snapshot + full suite + import + validate**

Run:
```bash
python -m pytest tests/test_nav.py -v
python -m pytest
python -c "import main; print('IMPORT OK')"
python -m engine.validate data
```
Expected: snapshot PASS (tables match legacy byte-for-byte); full suite green; `IMPORT OK`;
validate `OK: 18 rooms …`.

- [ ] **Step 6: Commit (propose to user)**

```bash
git add src/room_paths.py src/command_handler.py tests/test_nav.py
git commit -m "refactor(nav): build room path/alias tables from YAML; delete hardcoded dicts"
```

---

## Self-Review

**Spec coverage:** C1 flatten (data + src loader + engine loader + validate) → Tasks 1-2.
C2 room path/aliases (schema + validate + YAML + builder + delete literals + snapshot) →
Tasks 3-4. All spec sections covered.

**Placeholder scan:** No TBD. All code shown in full. The one soft spot — `self.world.rooms`
as the rooms source in Task 4 Step 4 — is called out with a fallback instruction; the executor
verifies the exact attribute the handler already uses to reach rooms.

**Consistency:** 41 items / 18 rooms throughout. `build_nav_tables` signature identical in
interface block, Task 4 test, and implementation. `find_nav_problems` signature identical in
Task 3 test and implementation. Legacy snapshot fixtures are the verbatim current dicts.
