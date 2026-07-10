# HFSE Rewrite Plan — Headless Core, Typed Content, Tested

## Progress

- **Phase 1 — DONE.** Typed content schema (`engine/schema/`), loader + linker
  (`engine/content/`, fail-loud on dangling load-bearing refs), `python -m
  engine.validate`, test suite (`tests/test_content.py`), and CI gate (`Makefile`,
  `.github/workflows/ci.yml`). Caught: chmod_key phantom-room (fixed), root_key
  orphan (flagged), mirror_sector unreachable (flagged, xfail), master_key
  rarity typo (tolerated).
- **Phase 2 — DONE (2a + 2b).**
  - 2a: `HeadlessUI` (`engine/headless/`) + `GameSession` (`engine/api.py`) drive
    the engine via the synchronous event bus with no Textual App. Engine tests +
    randomised playthrough fuzz (`tests/test_headless.py`).
  - 2b: domain decoupled from the UI. `CommandHandler` and `CombatSession` no
    longer hold a `ui` reference — they write to a `GameOutput` sink
    (`src/game_output.py`); all ~137 `self.ui.update_output` sites became
    `self.output.write`. The engine injects a live, thread-safe forwarder
    (`_forward_output`) so the domain depends only on the sink abstraction
    (dependency inversion). `game_engine.py` remains the composition root that
    owns the concrete UI. Output ordering and the threaded game-over animation
    are preserved.
- **Phase 3 — DONE (21/21 verbs).** Command pattern: `src/commands/`
  (`Command` base, `build_registry`); dispatcher checks the registry and passes
  the full arg list (fixed the old first-token-only truncation bug — `find` was
  silently broken by it). All verbs migrated across 8 modules: info (help,
  shortcuts, pwd), display (journal, inventory/inv, keys, map), discovery (find,
  ps), system (save, quit/exit), items (drop, equip, examine, talk, take, cat),
  navigation (ls, cd), actions (use, attack). Shared `_handle_*` sub-handlers,
  `start_combat`, and `_find_*` helpers stay on the handler; commands call them
  via `ctx`. Legacy dispatch dict now empty. `command_handler.py`: 2457 → 1418
  (−42%). 43 tests (`tests/test_commands.py` + `tests/test_headless.py`).
  Fixed a regression mid-migration (a `@staticmethod` decorator clipped during
  method removal) — caught by strengthening the cat test.
- **Phase 4a — DONE (versioned saves).** `SAVE_VERSION` + `_migrate_save`
  chain in `src/save.py`: old (unversioned, snake-case) saves migrate to the v2
  camelCase envelope (`version`, `player`, `world`, `savedAt`, `saveDate`) on
  load. `Player.from_dict` no longer bracket-accesses required keys (was a
  KeyError on partial/legacy saves). `tests/test_saves.py` covers round-trip,
  envelope shape, v1→v2 migration, and partial-save tolerance. The player/world
  *payloads* stay snake_case — camelCasing their internals hits the field-vs-id
  ambiguity (inventory keyed by item ids, story_flags by flag ids) deliberately
  avoided since the start of this work.
- **Phase 4b — NOT DONE (reactive MVVM UI). Deferred: needs a live TUI to
  verify.** Rewriting `textual_ui.py` (~1000 lines) for Textual `reactive`
  binding + snapshot-based `view_builder` can't be exercised by the headless
  test net, so it should be done interactively by someone who can run the app,
  not blind. Concrete tasks when picked up: make `ViewBuilder.build_*` take
  immutable snapshots instead of reaching into live `world`/`player`/
  `combat_system` (`view_builder.py:65,133-164,296`); move `ROOM_ID_TO_PATH`
  (`view_builder.py:26-46`) out of the view layer; bind ViewModels to widgets via
  `reactive`; sync `UIProtocol` to the real contract.

## Context

HFSE (`/Users/duhonyoung/Documents/HFSE-updated`) is a ~10.4k-LOC Python terminal RPG on Textual. It works, but three structural problems make it fragile to change:

1. **String-coupled content schema.** YAML keys are read via raw string literals (`class_info.get("base_health")`) at ~300 sites (135 `.get()` + ~30 bracket + ~40 `in` in `command_handler.py` alone). A content/code mismatch fails silently, deep in play. This already shipped a bug: `ghost_hidden` required key `system_badge.dat` while the item id was `system_badge`, making a room permanently unreachable (fixed in tree). A `_validate_data_references` exists (`game_engine.py:170`) but **only logs, never fails, and is skipped on save-load**.
2. **No automated tests.** Zero test files against a large content graph. Every edit is unguarded.
3. **UI-coupled monolith.** The domain calls a live Textual reference `self.ui.update_output(...)` from ~180 sites (117 in `command_handler.py`, 20 in `combat.py`, ~40 in `game_engine.py`), and `command_handler.py` is a single 2,457-line class dispatching all verbs. Engine can't be tested or driven headlessly; importing `game_engine` transitively imports Textual.

**Intended outcome:** move failures from *silent, late, in-play* to *loud, early, at-load-or-in-CI*, and make the codebase changeable without fear — without a big-bang rewrite or a long unplayable period.

**Strategy: Strangler (in-place, incremental).** Each phase ships a working, test-green build. Keep the data-driven content model and low authoring barrier. Stay Python (modern, strict-typed) — a .NET/other rewrite buys type-safety obtainable in Python for a fraction of the cost while discarding a working TUI stack.

**Decisions (defaults, revisit if needed):**
- YAML content stays **snake_case**; camelCase applies only to the **serialized save JSON** via Pydantic field aliases (matches the global convention in `~/.claude/CLAUDE.md`: "API data properties camelCase").
- Textual stays the only frontend built now; the core is made frontend-agnostic so web/Discord is possible later without engine changes.

**Tooling to add:** `pydantic>=2`, `pytest`, `mypy`, `ruff` (add to `requirements.txt` / a `requirements-dev.txt`).

---

## Phase 1 — Load-time safety layer (highest value, no UI risk)

Goal: kill the string-coupling and the silent-failure class. Independently valuable; can stop here for ~70% of the benefit.

### 1a. Typed content schema (`engine/schema/`)
- New package: Pydantic v2 models — `CharacterClass`, `Room`, `Item` (+ subtypes weapon/consumable/key/lore/armor/trinket/crafting via a discriminated `type`), `Enemy`, `Ability`, `Attack`, `NPC`.
- Field names in the models are the **one and only** place YAML key strings live. Use `model_config = ConfigDict(populate_by_name=True)` and, on save-serialized models only, an `alias_generator` to camelCase.
- Ground the field lists in the current schema (from exploration):
  - `Room`: `name, description, detailed_description, exits, items, npcs, enemies, hidden, locked, key_required, zone, zone_level, requires_sudo`.
  - `CharacterClass`: `name, description, base_health(>0), base_damage(>0), starter_weapon, starter_abilities, preferred_zones, power_scaling, loot_preference, attacks, display{color,hp_label,...}`.
  - `Enemy`: `name, short_description, description, health, damage, is_boss, auto_attack, dialogue, drops[{item,chance}], on_defeat{message}, attack_patterns`.
  - `Item` (weapon): `name, description, type, damage, allowed_classes, rarity, tags, allowed_zones, persistence, special_effects[{type,value,description}]`; consumables add `usable, usable_in_combat, consumed_on_use, combat_effects, on_use{message}`.
- Add `id: <TypedId>` fields. Define `NewType` id aliases (`RoomId`, `ItemId`, `EnemyId`, `NpcId`, `AbilityId`) for readability.
- Validators enforce invariants (`base_health > 0`, valid `persistence`/`power_scaling` enums, `type` discriminator).

### 1b. Loader + linker (`engine/content/`)
- Rewrite loading to parse-then-validate: wrap the existing readers in `src/data_loader.py` (`load_class_data`, `load_enemy_data`, `load_room_data`, `load_weapon_data`, `load_consumable_data`, `load_abilities_data`) plus the engine-side item/npc loaders (`game_engine.py:_load_items` ~243, `_load_data_from_dir` ~210) into functions returning typed model instances.
- Add `link(world)`: after loading, resolve **every** id-reference into a real object and **raise `ContentError`** on any dangling ref — room `exits`/`items`/`npcs`/`enemies`, `key_required`, class `starter_weapon`/`starter_abilities`/`attacks`, enemy `drops[].item`. This is the enforced, fail-loud replacement for `game_engine.py:170`'s log-only `_validate_data_references`, and it runs on **both** fresh-start and save-load paths.
- Preserve current id conventions: enemy/npc ids are filename stems with dots (`corrupt_process.bin`); rooms are filename stems; items are `category->{id:def}`.

### 1c. Content test suite (`tests/test_content.py`)
- Reuse the harness already drafted at `scratchpad/integrity.py` as the seed (loads all data, checks rooms/exits/enemies/npcs/items/keys resolve, boots each of 3 classes, asserts stats populate).
- Assert: all rooms reachable from the start room (`home_grove`) via `exits` (graph reachability — catches unreachable content); every id-ref resolves; every class boots with `max_health>0`, `total_damage>0`; `link()` raises on a deliberately-broken fixture.
- Wire `pytest` + a GitHub Actions (or local `make check`) gate running `pytest`, `mypy`, `ruff`.

**Phase 1 verification:** `pytest` green; `python -m engine.validate data/` (new CLI) exits 0 on good content and non-zero with a precise message on a broken fixture (e.g. revert the `ghost_hidden` fix → linker must fail naming the room + missing item).

---

## Phase 2 — Headless core + facade (unblocks testing the engine)

Goal: sever domain→UI so the engine runs with no Textual.

### 2a. Result objects instead of direct UI calls
- Introduce a `Result`/`GameOutput` type (messages + emitted events + state deltas). Commands **return** it; they never call `self.ui`.
- Replace the ~180 `self.ui.update_output(...)` sites (`command_handler.py` 117, `combat.py` 20, `game_engine.py` ~40) with appended messages on the returned `Result`. The existing event-bus channel (`ROOM_ENTERED`, `PLAYER_STATS_CHANGED`, `PLAYER_INVENTORY_CHANGED`) stays for state; narrative text moves onto `Result`.
- Remove the `ui` param threaded through `CommandHandler.__init__` (`command_handler.py:21`) and `CombatSession.__init__` (`combat.py:273`). Remove the private back-refs in `game_engine.py:_bind_ui_refs` (72-79); expose `player`/`world`/`room_aliases` to the UI through a read-only accessor on the facade instead.

### 2b. `GameSession` facade (`engine/api.py`)
- The single entry point a frontend touches: `submit_command(str) -> Result`, plus read-only state accessors and an event-subscribe hook. No Textual import anywhere under `engine/`.
- `main()` (`game_engine.py:966`) becomes: build `GameSession`, hand it to a frontend.

### 2c. Headless driver + engine tests (`frontends/headless/`, `tests/test_commands.py`)
- A scriptable driver that feeds command strings and inspects `Result` — enables golden-file command tests and an automated random-walk playthrough asserting no crash and completability for all 3 classes (formalizes the `playtest-simulator` agent as CI).

**Phase 2 verification:** engine imports with Textual uninstalled; headless driver plays a scripted run start→combat→level-up; `pytest` green.

---

## Phase 3 — Command-pattern split (dissolve the monolith)

Goal: break the 2,457-line `command_handler.py` into one small class per verb.

- Define `Command` base (`name`, `execute(ctx, args) -> Result`). Registry auto-dispatch replaces the `self.commands` dict (`command_handler.py:111-135`).
- One file per verb under `engine/commands/`: `cd`(change_directory 815), `ls`(701), `cat`(921), `take`(993), `drop`(1079), `use`(1110), `equip`(1894), `examine`(1456), `talk`(1541), `attack`(1596), `map`(1660), `find`(1715), `ps`(1743), `keys`(1757), `inventory`(1622), `journal`(1308), `save`(2389), `quit`(2408), `help`(513), `pwd`(574), `shortcuts`(544).
- Extract shared helpers into a `GameContext` / services object: item resolution (`_find_item_by_name_or_id` 983, `_resolve_item_shortcut` 2310, `_normalize_item_name` 968), `execute_effect` (2032), `start_combat` (1815), hint/tutorial helpers, `room_aliases` (36-108).
- Fix the dispatcher truncation bug: it currently passes only `args[0]` (`command_handler.py:503-505`), truncating multi-word args — commands should receive the full arg list.
- The `use` verb keeps its `type`-string fan-out (`_handle_key_item` 1193 … `_handle_spell_item` 1436); model the effect hooks (`on_use/on_take/on_read/on_examine/on_talk/on_defeat`) as typed effect objects (Phase 1 schema) so `execute_effect` stops string-probing.
- One command-test per verb as each is extracted (TDD: test the extracted class against the old behavior before deleting the old method).

**Phase 3 verification:** every verb has a passing command test; `command_handler.py` reduced to thin routing or deleted; full playthrough green.

---

## Phase 4 — Versioned saves + reactive MVVM UI

### 4a. Versioned, validated saves (`src/save.py`, `player.py`, `game_world.py`)
- Add `version` to the save structure (`save.py:41-46`) and a migration chain (`migrate_1_2`, …). Serialize/deserialize player + world through the Phase-1 Pydantic models → camelCase aliases + validation-on-load for free.
- Fix `Player.from_dict` bracket-access fragility (`player.py:427-435` KeyErrors on old saves) via the model + a v0→v1 migration.
- Provide a snake→camel migration for existing `saves/` (per the earlier decision to preserve, not wipe, user saves).

### 4b. Strict MVVM with Textual reactivity (`frontends/tui/`)
- Keep the clean `view_models.py` DTOs (already pure). Make `view_builder.py` (`build_room_view` etc.) take **immutable snapshots** from the facade instead of reaching into live `world`/`player`/`combat_system` (currently calls `world.get_room_state`, `player.calculate_damage`, `combat_system.get_available_attacks` — `view_builder.py:65,133-164,296`). Move the `ROOM_ID_TO_PATH` content map (`view_builder.py:26-46`) out of the view layer into content.
- Bind ViewModels to widgets via Textual `reactive` properties so panels auto-render on engine events, replacing manual event-dict pushing.
- Enforce `UIProtocol` (`ui_interface.py`) as the real contract and sync it with actual calls (drop Textual-specific `update_output_renderable`/`call_from_thread` from the core-facing interface).

**Phase 4 verification:** old save loads via migration; TUI renders through snapshots only (no live-object reach-in); manual play session start→win for one class.

---

## Execution notes for agents

- **Order matters:** Phase 1 is independent and self-contained — do it first, merge, ship. Phases 2→3 are sequential (headless core before command split). Phase 4 depends on Phase 1 models.
- **Each phase merges green:** never leave `main` with failing `pytest`/`mypy`/`ruff`.
- **Preserve content authoring:** `data/*.yaml` layout and ids stay put; only the *reading* code changes in Phases 1–3.
- **Reuse, don't rebuild:** the pure DTO layer (`view_models.py`), the event bus (`events.py`), the FSM (`state_manager.py`), the `COMMAND_ENTERED` input path, and `scratchpad/integrity.py` (test seed) are already sound — build on them.

## Global verification

- `pytest -q` green (content + command + playthrough suites).
- `mypy --strict engine/` clean.
- `python -m engine.validate data/` exits 0; exits non-zero with a precise message when any id-ref is broken.
- Headless random-walk completes the game for Guardian / Weaver / Shaman without crash or softlock.
- Manual `python main.py` session unchanged for the player.
