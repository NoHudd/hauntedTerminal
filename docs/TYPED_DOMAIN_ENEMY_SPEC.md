# Typed Domain: Enemy — Spec (Strangler Step B, increment 2)

**Date:** 2026-07-08
**Status:** Approved design, not yet implemented.
**Why:** Second B increment (after the CharacterClass pilot). Types the enemy **template** on
the engine `Enemy` model, and — since the typing exposed it — fixes a real bug: enemy
`experience` values are dead (every enemy awards a flat 50 cycles). One combined commit.

## Plain summary

Enemy templates load as raw dicts today; combat also mutates enemies (copy + scale + HP
drop). We type the immutable **template** on the engine `Enemy` model (validated at load) and
convert model→dict at **one boundary** (`GameWorld.get_enemy`), so all combat/sim mutation
stays dict-based and unchanged. While there, we fix the `experience` bug the typing surfaced
and re-tune difficulty (sim-gated) to keep the win-rate band.

## Two parts, one commit

- **Part 1 — Type Enemy (zero gameplay change).** Seam + boundary + model enrichment +
  consumer sweep.
- **Part 2 — Award real experience (balance).** Author 7 missing `experience` values, read
  `experience` in combat + sim, re-tune `difficulty.yaml` to restore the band.

## Constraints (global)

- **Part 1 is behavior-neutral** (proven: `model_dump(exclude_unset=True)` reproduces every
  enemy's raw YAML keys — verified 0/24 mismatch). **Part 2 is a deliberate balance change**,
  gated by the sim.
- Advances adoption: `src/data_loader` imports `engine.content` (second such link; no cycle).
- Authoritative counts unchanged: 24 enemies. `sim/`+`src/` stay outside mypy/ruff; `engine/`
  is mypy-strict (Enemy model change must type-check).
- Gate: `source venv/bin/activate`; `python -m pytest` + `python -m engine.validate data` +
  `python -c "import main"` + sim band check. Bare `pytest` fails — use `python -m pytest`.
- User does own commits (propose commands; never run `git commit`). ONE commit.
- Model: `engine/schema/models.py` `Enemy` (+ `Drop`).

---

## Part 1 — Type the Enemy template

### 1a. Enrich the engine `Enemy` model
Add fields (promoting today's `extra="allow"` tail to typed, validated fields):
```python
    tier: int | None = None
    experience: int = 0
    dialogue: str = ""
    attack_patterns: list = Field(default_factory=list)
    loot_table: list = Field(default_factory=list)

    @field_validator("dialogue", mode="before")
    @classmethod
    def _dialogue_to_str(cls, v: object) -> str:
        return "" if v is None else str(v)
```
`weaknesses`/`resistances`/`loot`/`on_defeat` stay `extra="allow"` (flavor). `health > 0`,
`damage >= 0`, and `drops[].item` are already validated by the model + linker.

### 1b. Seam
`src/data_loader.load_enemy_data()` returns `dict[str, Enemy]` via
`engine.content.loader.load_enemies("data")` (ids keep dots, e.g. `corrupt_process.bin`).
`GameWorld` stores these typed templates in `self.enemies`.

### 1c. Boundary — `GameWorld.get_enemy` always returns a dict
This is the single template→runtime-dict conversion point. After fetching the template model,
dump it to a dict *before* any scaling, so `scale_enemy_stats`, difficulty scaling, combat, and
the sim's `_fight` remain 100% dict-based and untouched:
```python
    def get_enemy(self, enemy_id, player_class=None):
        enemy = self.enemies.get(enemy_id)
        if enemy is None:
            debug_log(f"WARNING: Requested non-existent enemy: {enemy_id}")
            return None
        if not isinstance(enemy, dict):
            enemy = enemy.model_dump(exclude_unset=True)  # typed template -> runtime dict
        if player_class:
            enemy = self.scale_enemy_stats(enemy, player_class)
        # ... existing difficulty scaling on the dict, unchanged ...
```
`scale_enemy_stats` is **unchanged** (it now always receives a dict).

### 1d. Direct template reads → attribute access
The few places that read `self.enemies[...]` (the model) directly, not via `get_enemy`:
- `game_world.py:~1147` `enemy_data.get("name")` → `enemy_data.name`
- `game_world.py:~1308` `self.enemies.get(enemy_id, {}).get('name', enemy_id)` →
  ```python
  e = self.enemies.get(enemy_id)
  enemy_name = e.name if e else enemy_id
  ```
- `src/enemy_pools.py:16,35` read `.get("tier")`. Its unit tests pass plain dict fixtures, so
  use a dict-or-model accessor:
  ```python
  def _field(e, key):
      return e.get(key) if isinstance(e, dict) else getattr(e, key, None)
  ```
  and replace `(edata or {}).get("tier")` / `(enemies.get(eid) or {}).get("tier")` with
  `_field(edata, "tier")` / `_field(enemies.get(eid), "tier")`.
- `sim/gauntlet.py::_threat` (`enemy.get("health")/.get("damage")`) → `enemy.health` /
  `enemy.damage` (its input is a template model via `load_enemy_data()`; update the type hint).

### 1e. Part 1 tests
- `load_enemy_data()` returns `Enemy` instances; `health > 0` for all 24.
- `enemy_pools.build_tier_pools(load_enemy_data())` still yields 6/6/6 (tier via attribute).
- `GameWorld.get_enemy(id, class)` returns a **dict** whose keys equal the enemy's raw YAML
  keys (faithfulness guard for a sample enemy).
- Existing `test_headless` / `test_commands` combat + `test_enemy_pools` + `test_sim` stay green.

---

## Part 2 — Award real experience (sim-gated balance change)

### 2a. Author the 7 missing `experience` values
These enemies have no `experience:` today (so they award the flat-50 default). Add
(starting values; the re-tune restores the band, not these exact numbers):

| enemy | experience |
|---|---|
| corrupt_file.exe | 15 |
| corrupt_process.bin | 15 |
| glitched_process.tmp | 16 |
| zombie_daemon.exe | 18 |
| permission_denied.sys | 28 |
| shadow_process (sudo-trial boss) | 100 |
| daemon_overlord.sys (final boss) | 150 |

### 2b. Read the real value (two sites, same bug)
- `src/combat.py:~671` `self.enemy_data.get("harvesting_cycles", 50)` →
  `self.enemy_data.get("experience", 50)`.
- `sim/simulator.py:~206` `enemy.get("harvesting_cycles", 50)` →
  `enemy.get("experience", 50)`.
(Both operate on the scaled runtime dict from `get_enemy`; `experience` is a modeled field so
`model_dump(exclude_unset=True)` carries it when present. Fallback `50` stays for safety.)

### 2c. Re-tune difficulty (sim loop)
Switching mooks from a flat 50 to their real ~15-45 slows leveling → win rates drop. Run the
sim, adjust `data/difficulty.yaml` (`xp_gain` and/or `enemy_damage`) to restore the tuned band
(**medium ~88% / hard ~62%**, tight per-class spread, no class collapse), same loop used for
the loot/difficulty work. `easy` stays comfortably above medium.

### 2d. Part 2 verification
`python -m pytest` green · `engine.validate data` OK · sim band restored (report per-class
medium/hard win rates) · `import main` clean.

---

## Non-goals

- Not typing the runtime combat enemy **instance** (stays a mutable dict — combat unchanged).
- Not typing Room or Item (later increments).
- Not modeling `weaknesses`/`resistances`/`loot`/`on_defeat` (stay `extra="allow"`).
- No change to drop/loot-table mechanics, saves, or enemy YAML beyond adding `experience`.

## Open decisions (defaults chosen)

- `enemy_pools` uses a dict-or-model accessor rather than forcing its unit-test fixtures onto
  models (keeps the pure-logic tests light).
- `experience` fallback stays `50` in both read sites (guards a future enemy that omits it),
  though all 24 will have a value after 2a.
- Re-tune adjusts `xp_gain` first (most direct lever for a leveling-pace change), then
  `enemy_damage` if the band needs finer correction.
