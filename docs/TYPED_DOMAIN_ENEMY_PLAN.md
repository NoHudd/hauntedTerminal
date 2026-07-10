# Typed Domain: Enemy — Implementation Plan (Strangler B, increment 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Type the enemy template on the engine `Enemy` model (zero gameplay change), then fix the dead-`experience` XP bug and re-tune difficulty. One commit.

**Architecture:** Templates load as typed `Enemy` models; `GameWorld.get_enemy` dumps model→dict at the single boundary so combat/sim stay dict-based and unchanged. Then combat + sim read real `experience`, and `difficulty.yaml` is re-tuned via the sim.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, the `sim/` harness.

## Global Constraints

- **Part 1 behavior-neutral** (`model_dump(exclude_unset=True)` == raw YAML keys, verified 0/24).
  **Part 2 is a balance change** (sim-gated).
- Outer `self.enemies` dict keeps dict semantics; only **values** are models. `get_enemy` returns a dict.
- No import cycle: `data_loader → engine.content.loader → engine.schema`.
- `sim/`+`src/` outside mypy/ruff; `engine/` mypy-strict (Enemy change must type-check).
- Gate: `source venv/bin/activate`; `python -m pytest` + `python -m engine.validate data` + `python -c "import main"`.
  Bare `pytest` fails — use `python -m pytest`.
- User does own commits (propose; never run `git commit`). ONE commit at the end.
- Spec: `docs/TYPED_DOMAIN_ENEMY_SPEC.md`. Target band: medium ~88% / hard ~62%.

## File Structure

| File | Change |
|---|---|
| `engine/schema/models.py` `Enemy` | +tier/experience/dialogue/attack_patterns/loot_table (+dialogue coerce) |
| `src/data_loader.py:118` `load_enemy_data` | return `dict[str, Enemy]` via engine loader |
| `src/game_world.py:1080` `get_enemy` | dump model→dict boundary |
| `src/game_world.py:~1147,~1308` | template `.name` attribute reads |
| `src/enemy_pools.py` | dict-or-model `_field` accessor for `tier` |
| `sim/gauntlet.py` `_threat` | attribute reads |
| `src/combat.py:671`, `sim/simulator.py:206` | read `experience` not `harvesting_cycles` |
| `data/enemies/*.yml` (7) | author `experience` |
| `data/difficulty.yaml` | re-tune |
| `tests/test_enemy_typed.py` (new) | typed loader + boundary faithfulness |

---

## Task 1: Type the Enemy template (Part 1, atomic — zero gameplay change)

- [ ] **Step 1: Write the failing test** (`tests/test_enemy_typed.py`)

```python
"""Enemy templates are typed; get_enemy hands combat a dict identical to the raw YAML."""
from __future__ import annotations

import glob
import os

import yaml

from engine.schema import Enemy


def test_load_enemy_data_returns_typed_models():
    from src.data_loader import load_enemy_data
    enemies = load_enemy_data()
    assert len(enemies) == 24
    for eid, e in enemies.items():
        assert isinstance(e, Enemy), (eid, type(e))
        assert e.health > 0


def test_get_enemy_returns_dict_matching_raw_yaml():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("Tester", "guardian")
        world = s.engine.cmd_handler.world
        # pick any enemy id present in data/
        path = sorted(glob.glob("data/enemies/*.yml"))[0]
        eid = os.path.basename(path)[:-4]
        raw = yaml.safe_load(open(path)) or {}
        got = world.get_enemy(eid)  # no player_class -> unscaled dict
        assert isinstance(got, dict)
        # every raw YAML key survives the model round-trip
        assert set(raw.keys()) <= set(got.keys())
    finally:
        s.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_enemy_typed.py -v`
Expected: FAIL (`load_enemy_data` returns dicts, not `Enemy`).

- [ ] **Step 3: Enrich `Enemy` in `engine/schema/models.py`**

In `class Enemy(_Base)`, after `drops`:
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
(`field_validator` is already imported in this module.)

- [ ] **Step 4: Flip `src/data_loader.load_enemy_data` to typed models**

Replace its body with:
```python
def load_enemy_data():
    """Load all enemies as typed engine Enemy models (id -> model, dots kept)."""
    try:
        from engine.content.loader import load_enemies
        enemies = {str(eid): e for eid, e in load_enemies("data").items()}
        debug_log(f"Total enemies loaded: {len(enemies)}")
        return enemies
    except Exception as e:
        debug_log(f"ERROR loading enemy data: {e}")
        return {}
```

- [ ] **Step 5: Make `GameWorld.get_enemy` the model→dict boundary (game_world.py:1080)**

Right after the `if enemy is None: ... return enemy` guard, before scaling:
```python
        if not isinstance(enemy, dict):
            enemy = enemy.model_dump(exclude_unset=True)  # typed template -> runtime dict
```
Leave `scale_enemy_stats` and the difficulty-scaling block below unchanged (they now always get a dict).

- [ ] **Step 6: Convert the direct template reads**

`game_world.py` ~1147 (inside the display-name search loop):
```python
                enemy_data = self.enemies.get(potential_enemy_id)
                if enemy_data and enemy_data.name == enemy_id:
```
`game_world.py` ~1308:
```python
                e = self.enemies.get(enemy_id)
                enemy_name = e.name if e else enemy_id
```

- [ ] **Step 7: `src/enemy_pools.py` dict-or-model accessor**

Add near the top:
```python
def _field(e, key):
    return e.get(key) if isinstance(e, dict) else getattr(e, key, None)
```
Replace `(edata or {}).get("tier")` → `_field(edata, "tier")` and
`(enemies.get(eid) or {}).get("tier")` → `_field(enemies.get(eid), "tier")`.

- [ ] **Step 8: `sim/gauntlet.py::_threat` attribute reads**

```python
def _threat(enemy) -> float:
    return (enemy.health or 0) + (enemy.damage or 0) * _DAMAGE_WEIGHT
```
(input is a template model from `load_enemy_data()`.)

- [ ] **Step 9: Run Part-1 gate**

Run:
```bash
python -m pytest tests/test_enemy_typed.py tests/test_enemy_pools.py tests/test_sim.py -v
python -m pytest
python -c "import main; print('IMPORT OK')"
python -m engine.validate data
```
Expected: new tests PASS; full suite green (no new failures vs the 111 baseline + new tests);
`IMPORT OK`; validate `OK: … 24 enemies …`.
**Do not commit yet** — Part 2 lands in the same commit.

---

## Task 2: Award real experience + re-tune (Part 2, balance)

- [ ] **Step 1: Author `experience` for the 7 missing enemies**

Add `experience: <N>` to each file (place near `is_boss`/existing stat lines):
| file | value |
|---|---|
| `data/enemies/corrupt_file.exe.yml` | 15 |
| `data/enemies/corrupt_process.bin.yml` | 15 |
| `data/enemies/glitched_process.tmp.yml` | 16 |
| `data/enemies/zombie_daemon.exe.yml` | 18 |
| `data/enemies/permission_denied.sys.yml` | 28 |
| `data/enemies/shadow_process.yml` | 100 |
| `data/enemies/daemon_overlord.sys.yml` | 150 |

Verify: `python -c "import glob,yaml; print(sum('experience' in (yaml.safe_load(open(f))or{}) for f in glob.glob('data/enemies/*.yml')))"` → **24**.

- [ ] **Step 2: Read real `experience` in combat + sim**

`src/combat.py:671`:
```python
            base_cycles = self.enemy_data.get("experience", 50)
```
`sim/simulator.py:206`:
```python
        base = enemy.get("experience", 50)
```

- [ ] **Step 3: Measure the pre-tune band**

Run: `python -m sim.playtest` (or the project's sim entry — `python -c "from sim.simulator import measure; [print(m.mode, m.player_class, round(m.win_rate,2)) for c in ('guardian','weaver','shaman') for m in [measure(c,'medium',200), measure(c,'hard',200)]]"`).
Record medium/hard win rates per class. Expect a drop from the flat-50 baseline.

- [ ] **Step 4: Re-tune `data/difficulty.yaml`**

Raise `xp_gain` (primary lever for a leveling-pace change) and, if needed, nudge `enemy_damage`,
re-measuring until: **medium ~88%**, **hard ~62%**, tight per-class spread, no class at ~100% or
collapsed. Keep `easy` above medium. Update the header comment in `difficulty.yaml` with the new
band + that it reflects real-experience XP.

- [ ] **Step 5: Full gate**

Run:
```bash
python -m pytest
python -c "import main; print('IMPORT OK')"
python -m engine.validate data
```
Expected: all green; `IMPORT OK`; validate OK (24 enemies).

- [ ] **Step 6: Commit (propose to user)**

```bash
git add engine/schema/models.py src/data_loader.py src/game_world.py src/enemy_pools.py \
        src/combat.py sim/gauntlet.py sim/simulator.py \
        data/enemies/ data/difficulty.yaml tests/test_enemy_typed.py
git commit -m "refactor(domain): type Enemy via engine model; fix dead experience XP + re-tune (strangler B)

Part 1 (zero gameplay change): load_enemy_data returns typed Enemy models;
GameWorld.get_enemy dumps model->dict at the one boundary so combat/sim stay
dict-based. Enemy model enriched (tier/experience/dialogue/attack_patterns/
loot_table). enemy_pools + sim gauntlet read via attribute.
Part 2 (balance): enemies now award their real 'experience' (combat + sim read
it, not the dead harvesting_cycles/50 default); authored experience for 7 enemies
(incl. both bosses); re-tuned difficulty.yaml to hold medium ~88% / hard ~62%."
```

---

## Self-Review

**Spec coverage:** model enrichment (T1.3), seam (T1.4), boundary (T1.5), template reads
(T1.6), enemy_pools (T1.7), sim gauntlet (T1.8), XP author (T2.1), read sites (T2.2), re-tune
(T2.3-4), tests (T1.1). All covered.

**Placeholder scan:** none — every step shows final code/values. The re-tune (T2.4) is an
iterative sim loop by design, with an explicit target band.

**Consistency:** `get_enemy` returns dict everywhere; `load_enemy_data -> dict[str, Enemy]`;
24 enemies; band medium ~88% / hard ~62% matches the current tune.
