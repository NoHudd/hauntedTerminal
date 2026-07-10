# Difficulty-Sim — Working Status / Handoff

**Last updated:** 2026-07-06
**State:** difficulty tune COMPLETE (per-class imbalance solved, config applied).
Next up = rooms/loot randomization as a separate spec. Read this before touching
difficulty/sim again.

## What's DONE and committed-worthy

- **Difficulty modes** (`data/difficulty.yaml`, `src/difficulty.py`) — easy/medium/hard
  multipliers on enemy HP, enemy damage, XP. Player-facing (Settings toggle).
- **Seedable RNG** (`src/rng.py`) — deterministic sims.
- **Sim harness** (`sim/`) — `gauntlet.py` (main-path enemy list), `bot.py` (optimal
  bot), `simulator.py` (`measure`), `playtest.py` (CLI), `tune.py` (auto-tuner →
  proposal only, never writes live config).
- **Win condition WIRED** (`src/command_handler.py`) — this was previously
  **non-functional**: `check_game_completion()` was never called and required a
  never-authored `backup.bak` item. Now: win = defeat the Daemon Overlord in
  `/core`; fires from `_on_combat_ended` on victory; `win_game()` shows the
  class-branched ending + restart/new/quit prompt (no more `exit(0)`).
  Tests in `tests/test_commands.py`.
- **Content fix:** removed dead `root_key`/`root_vault` orphan (item + enemy drop).
- **Gauntlet filter fix** (`sim/gauntlet.py`) — now excludes `hidden`, `locked`,
  AND `class_restriction` rooms. Before, it only excluded `hidden`, so the
  guardian-only `srv_warrior_tomb` boss (`corruption_overlord.exe`) was wrongly
  thrown at weaver/shaman — it was the phantom source of ~all measured deaths.
- **Heal-economy fix** (`sim/simulator.py`) — THE key insight. Real game gives
  ~**2 heals total** on the main path (1 guaranteed home_grove `health_packet` +
  probabilistic drops from `permission_denied.sys` 40% / `zombie_daemon.exe` 50%;
  no restock, no shop). Sim previously gifted ~13 (3 start + 1/fight). Now:
  `STARTING_HEALS=1`, no per-fight restock, rolls **actual drop chances** via
  seeded RNG. Heal scarcity — not enemy stats — is the game's real difficulty lever.
- **VS16 emoji strip** — removed 19 `U+FE0F` selectors across 7 UI/source files
  (glyph-collision fix). See `docs/UX_REDESIGN.md` (Stage A/B shipped).

## SOLVED: per-class imbalance (2026-07-06)

Root cause was the class-kit sustain gap, amplified by scarce heals: shaman had
`healing_strike` (heal 10), guardian and weaver had **no attack-heal at all**
(the `core_recovery`/`data_stitch` heals in `abilities.yaml` are DEAD content —
combat uses only the `attacks:` list from `classes.yaml`, never `starter_abilities`).
So the tuner's global multipliers balanced the *mean* while the per-class spread hit
50pt on hard.

**Fix = give the two heal-less classes a small attack-heal via the existing
`healing:` field (zero new combat code), scaled inversely to their other sustain:**
- `frost_nova` (weaver, cd3): `healing: 4` — weaver already has top damage, so it
  needs the *least* per-heal. Thematic: nova siphons the frozen process.
- `shield_bash` (guardian, cd3): `healing: 3` — guardian already has top HP (120) +
  top mitigation (0.5), so the *smallest* heal. Thematic: bash vents cycles back.
- `healing_strike` (shaman, cd3): unchanged at `healing: 10`.
- The bot uses these because each is the top off-cooldown attack when the class's
  big nuke is on cooldown (see `sim/bot.py` — pure expected-damage pick).

**Result (60 runs/cell), spread now 10-12pt (was 50):**
```
mode     guardian  weaver  shaman   spread
easy       100.0%   96.7%   96.7%     3pt
medium      90.0%   86.7%   78.3%    12pt   avg ~85% = 15% loss (user goal)
hard        73.3%   63.3%   66.7%    10pt   avg ~68%
```

**Live config now tuned + applied** (`data/difficulty.yaml`, header fixed):
```
easy   hp=0.85  dmg=0.8  xp=1.3
medium hp=0.95  dmg=0.8  xp=1.0
hard   hp=1.15  dmg=0.7  xp=0.85
```
`make check` green (67 passed, 1 xfail sudo-trial); `engine.validate` OK.

### Next project (spec later, NOT started): rooms + loot randomization
User wants a roguelike replayability layer — more rooms, randomized loot — but as
its own brainstorm/spec on TOP of this balanced baseline, not bolted onto the tuner.
Note the tension: randomization raises variance, which fights a tight tuned loss
band. Treat "tuned difficulty" (done) and "replayability variety" (next) as separate
goals. When starting, run it through `superpowers:brainstorming` fresh.

## 2026-07-06 (later) — heal-drop fidelity fix + weapon-pool baseline drift

Two findings during the rooms/loot work (`docs/ROOMS_LOOT_RANDOMIZATION_SPEC.md`):

1. **Heal drops now actually fire in-game.** Enemy `drops` were never awarded on kill
   (no code read them — only validation did), yet the sim MODELS them firing. Phase 2a
   wired `CommandHandler._on_enemy_defeated` → award into the room, so the live game now
   matches the sim's heal model (user chose "wire all drops"). This makes the real game
   slightly *easier* (heals it was supposed to have now drop) — toward the tuned target.

2. **The sim's weapon-progression model inflated the band after Phase 1.** `sim/simulator.py`
   `_class_weapons`/`_equip_for_stage` upgrade the sim player up the class's damage-sorted
   weapon list as they clear rooms. Phase 1 added epic (dmg 24–30) + legendary (44–46)
   weapons, so the sim now equips much stronger mid/late gear → measured band jumped from
   **medium ~85% / hard ~68%** to **medium ~97% / hard ~93%** (60 runs/cell).
   **Caveat: the sim equips these even though the real game can't reliably give them**
   (epic/legendary don't world-place; post-2a they only *drop* at ~12%). So 97/93 is an
   OPTIMISTIC upper bound, not the real difficulty.

**RESOLVED 2026-07-06 — weapon-fidelity fix + shaman redesign + re-tune.**

- **Sim fidelity fix:** `sim/simulator.py` `SIM_OBTAINABLE_RARITIES = {common, uncommon,
  rare, epic}`; `_class_weapons` filters to it. Legendary EXCLUDED (never world-places /
  post-win trophy — the phantom `zero_day_blade` that inflated the old tune). Epic is
  INCLUDED because it's now reliably obtained via a guaranteed capstone drop.
- **Capstone weapon:** `null_guardian.sys` (last pre-boss main-path enemy) gets a
  `loot_table` `epic chance 100`, so every class enters /core with a class-appropriate
  epic. This was needed because filtering out the phantom legendary exposed how brutal
  the rare-only baseline is (medium ~58%, shaman 27%).
- **Shaman redesign (user-driven):** shaman was the weakest identity — a healer whose low
  damage made fights drag (death on hard). Fixed by leaning into the healer fantasy:
  `base_health 100→120`, `base_damage 8→9`, `healing_strike 10→13`. Now a bulk+heal
  attrition tank. Verified: pure low-damage attrition does NOT auto-win (heal throughput
  < boss dps), so the HP buffer + moderate chip damage is what makes long fights winnable.
- **Other kit:** weaver `frost_nova 4→7`; guardian `shield_bash` net unchanged (3).
- **Re-tuned `difficulty.yaml`** (hand-set — the auto-tuner's internal target undershoots
  our band): easy dmg 0.9, medium dmg 0.86, hard dmg 0.76 (hp/xp unchanged).

**Final band (80 runs/cell):** medium avg ~88% (G89 W79 S98), hard avg ~72% (G59 W84 S73).
Averages on target; per-class spread wider (~19–25pt) than the old phantom-based 12pt.

**Known structural residual (deferred, NOT a bug):** guardian collapses on hard (59%)
because it has NO passive mitigation — its only mitigation is `shield_bash`'s one-turn 0.5
(cd3), so the tank falls off in hard's long fights. **Armor is unwired** (`take_damage`
is bare `health -= amount`). **Phase 2b (armor wiring)** gives guardian passive mitigation
and is the correct fix; do NOT paper over it with more heals. Shaman's medium dominance
(98%) is inherent to the bulky-healer identity on the easier mode — accepted.
`data/difficulty.proposed.yaml` holds a STALE auto-tuner proposal; the live values were
hand-set. See [[hfse-loot-randomization]].

## 2026-07-07 — armor wired; post-armor re-balance OPEN

Phase 2b (`docs/ROOMS_LOOT_PHASE2B_PLAN.md`) wired armor as capped % mitigation:
- `Player.take_damage` applies `min(ARMOR_MITIGATION_CAP, defense*ARMOR_DEFENSE_TO_PCT)%`,
  floor 1. Live constants: **cap 33, factor 1.5** — deliberately low factor + this cap so
  guardian's def-20/22 pieces (~30–33%) out-mitigate weaver/shaman def-15 (~22%).
- The sim now models armor progression (`sim.simulator._class_armor`/`_equip_for_stage`),
  gated by `SIM_OBTAINABLE_RARITIES`, so mitigation shows in the band.

**OPEN — post-armor per-class re-balance.** Landing the band with armor did NOT converge by
knob-twiddling. Findings:
- **The final boss `daemon_overlord` is the sole chokepoint** — essentially every sim death
  is that one fight. Classes differ only in how they survive it (DPS/sustain).
- Adding armor pushed the whole band to ~90–100%. Raising `enemy_damage` to compensate hits
  early game (pre-armor stages) and, crucially, **shifts which class collapses**: flat armor
  left guardian lowest; differentiating guardian (cap 33/f 1.5) then collapsed **shaman** on
  hard (25%). Two global enemy_damage knobs + per-class armor can't satisfy 6 cells against a
  single-chokepoint boss.
- This is the same **per-class-kit** problem earlier solved with attack-heals — not an
  enemy_damage tuning problem. The re-balance needs a per-class lever (kit/sustain/DPS vs the
  boss), possibly boss-specific tuning, NOT just `difficulty.yaml`.

**RESOLVED (2026-07-07) — re-balanced with armor.** Landed via two levers:
- **Shaman DPS nudge:** `base_damage 9 -> 10`. Shaman is the lowest-DPS class (longest boss
  fight = most hits) AND gets the least armor (~22% vs guardian ~30%); under boss pressure it
  collapsed first. +1 damage shortens its fight enough to survive.
- **`difficulty.yaml` re-tuned WITH armor:** medium enemy_damage 0.98, hard 0.93 (easy 0.9).
- Result @80 runs/cell: **hard G69/W76/S66 (avg ~70%, ~10pt spread), medium ~93%, easy ~100%.**
  Guardian repaired (58→69 hard), shaman repaired (25 mid-thrash→66), no class collapses.

**Caveat — the band is fragile.** The final boss `daemon_overlord` is the sole chokepoint, so
enemy_damage is hypersensitive there: 0.76→~98%, 0.88→~84%, 0.93→~70%, 1.0→~45%. There is no
wide stable plateau at any target. Medium lands ~93% (a touch easy vs the 85% goal) because
pushing it re-softens weaver (90 HP, the squishiest). **Robustly flattening the band needs a
STRUCTURAL fix — Phase 2c (per-zone enemy pools) to spread difficulty across more fights so no
single boss dominates**, and/or a boss redesign (lower per-hit damage, more consistent). Until
then this config is the best operating point. See [[hfse-loot-randomization]].

## 2026-07-07 (later) — Phase 2c: enemy pools + attrition; band re-tuned

`docs/ROOMS_LOOT_PHASE2C_PLAN.md` shipped. Enemies now roll from difficulty-tier pools
(tier 1/2/3, 6 each after +6 new mobs); main-path rooms declare `enemy_tier`+`enemy_count`
and draw distinct enemies per run (`src/enemy_pools.py`); the sim rolls a fresh set per run.

**Fragility partly fixed.** Pre-2c: ~100% of deaths were `daemon_overlord`. Post-2c the new
tier3 mobs (kernel_wight, orphan_reaper, deadlock_geist, segfault_revenant — dmg 20–22) now
claim deaths across every cell, so the run (not one boss) is the test. The boss is still the
plurality of hard deaths (~85%), but no longer the whole story.

**Re-tuned band (100 runs/cell):** easy ~97%, medium G91/W81/S92 (~88%), hard G61/W66/S60
(~62%, ~6pt spread). No class collapses; full enemy variety run-to-run.

**Tuning notes for next time:** 2c massively perturbed difficulty (initial post-2c hard was ~4%
because `dev_null_void` drew TWO boss-tier mobs before the boss). Levers used: `dev_null_void`
`enemy_count` 2→1 (two boss-tier tier3 mobs pre-boss was too spiky), `difficulty.yaml`
medium enemy_damage 0.93 / hard 0.85. The band is still boss-sensitive but less so than pre-2c.
To spread deaths further off the boss, weaken the tier3 mobs (dmg 20–22 ≈ boss) so count-2
tier3 rooms become survivable — deferred.

## Important gotchas / non-obvious facts

- **Live `data/difficulty.yaml` is stale** — it holds values tuned against the OLD
  inflated-heal sim (medium enemy_damage ~0.975). Do NOT trust it. The correct
  numbers come from a re-tune AFTER the class-kit decision above. Don't apply
  `difficulty.proposed.yaml` as-is (50pt hard spread).
- **`corruption_overlord.exe`** (warrior-tomb boss, dmg 30) is mechanically HARDER
  than the actual story final boss `daemon_overlord.sys` (dmg 20). It's optional
  (class-locked) content now, so out of the gauntlet — but the anticlimax remains
  if you ever surface it.
- **`stable_cache`** (heal 40) is defined in consumables but placed in zero rooms /
  drops — a dead item. `_HEAL_ITEMS` in the sim still lists it harmlessly.
- **`mirror_sector` / sudo-trial questline** is fully authored but unwired
  (`sudo_quest_active` never set). User chose LEAVE-AS-IS (xfail in
  `tests/test_content.py`). Not on the win path.
- **Tuner never writes live config** by design — writes `difficulty.proposed.yaml`.
  Human reviews + copies.
- Gate: `make check` (ruff + mypy strict on `engine/` + pytest + `engine.validate`).
  Sim/`src` are outside mypy/ruff scope. Last known: 67 passed, 1 xfailed.

## Re-run commands
```bash
python -m sim.playtest measure --mode all --class all --runs 60   # per class/mode
python -m sim.tune --mode all --runs 60                            # re-tune -> proposal
# per-class spread under the proposal: see the inline script pattern in this session
```
