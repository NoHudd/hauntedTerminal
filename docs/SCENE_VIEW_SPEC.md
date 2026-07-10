# Scene View — Spec

Pokemon-style visual scene inside the Textual TUI. Pixel-art sprites for battle and
exploration, rendered in the terminal. Stays a terminal game — the command line remains
the primary interaction; the scene is presentation only.

## Goals

1. A big **scene viewport** that shows *who is here*: room backdrop + NPC/enemy sprites
   while exploring; player-vs-enemy Pokemon framing during battle.
2. An **asset pipeline where artists never touch code**: drop a PNG in a folder, it
   appears in game. Missing art auto-falls-back to a generated placeholder.
3. **Battle feel** without hand-drawn animation: code-driven effects (lunge, hit flash,
   shake, HP drain, faint slide) on static sprites.
4. **Full-screen selection screens** (title / difficulty / class) — vertical choice
   lists with pixel art, no dead sidebar.

## Non-goals (v1)

- Sprite frame animation (idle loops, attack poses). The asset format anticipates it
  (see Asset conventions) but v1 renders one static sprite per entity.
- Per-room backdrops for all 18 rooms. Backdrops are per **zone** (8 zones + default);
  a per-room override slot exists for later.
- Any game-logic change. This is a pure frontend feature on top of the existing event
  bus + view-builder DTOs. `src/commands/`, `src/combat.py`, world state: untouched.

## Decisions locked during design

| Question | Decision |
|---|---|
| Art format | **Pixel-art PNGs**, rendered as colored half-block characters (2 px per terminal cell) via `rich-pixels` + `Pillow` |
| Sidebar | **Hybrid**: combat panel dies (nameplates + HP bars move into the scene); inventory + stats stay in a slimmer sidebar |
| Explore scene | **Backdrop + characters**: zone backdrop, NPC/enemy sprites composited on top, item markers |
| Animation | **Effects-only v1**: procedural effects on static sprites; frame animation deferred |
| Selection screens | Full-screen, vertical option lists, pixel art per option |

## Layout

### Explore
```
┌ header ───────────────────────────────────────────┐
│ ┌─ scene: /var/cache_shrine ────────┬─ sidebar ─┐ │
│ │ ▓▓ zone backdrop ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ 📦 Inv    │ │
│ │   [npc sprite]      [enemy sprite]│ 📊 Stats  │ │
│ │   oracle.db          daemon.exe   │           │ │
│ │        ✦ item marker              │           │ │
│ ├─ output (scroll, smaller) ────────┴───────────┤ │
│ │ > ls                                          │ │
│ ├────────────────────────────────────────────────┤ │
│ │ input                                          │ │
└─┴────────────────────────────────────────────────┴─┘
```

### Battle
```
│ ┌─ scene ───────────────────────────┬─ sidebar ─┐
│ │            daemon.exe  ▉▉▉▉▉░░░░  │ 📦 Inv    │
│ │                 [enemy sprite]    │ 📊 Stats  │
│ │  [player sprite]                  │           │
│ │  Kai · Lvl 3  ▉▉▉▉▉▉▉▉░░          │           │
│ ├─ output ──────────────────────────┴───────────┤
```
Enemy top-right, player bottom-left, nameplate + HP bar adjacent to each — classic
Pokemon framing. The `⚔ Combat` sidebar panel is **removed** (its info lives in the
scene). Combat attack list/hints continue to arrive in the output panel as today.

### Selection screens (title / difficulty / class)
Full-screen Textual `Screen`s — no sidebar, no scene/output split. Options are
**tall card boxes laid out side by side across the screen**, each card carrying art
tailored to the option (Guardian card → shield sprite, Weaver → threads, Shaman →
totem; difficulty cards themed likewise, e.g. easy/medium/hard icons):
```
┌──────────────────────────────────────────────────────────┐
│                   H F S E  (logo art)                     │
│                                                           │
│  ┏━━━━━━━━━━━━━┓  ┌─────────────┐  ┌─────────────┐        │
│  ┃             ┃  │             │  │             │        │
│  ┃ [🛡 shield  ┃  │ [thread     │  │ [totem      │        │
│  ┃   art]      ┃  │   art]      │  │   art]      │        │
│  ┃             ┃  │             │  │             │        │
│  ┃  GUARDIAN   ┃  │   WEAVER    │  │   SHAMAN    │        │
│  ┃ Tank — high ┃  │             │  │             │        │
│  ┃ HP, armor   ┃  │             │  │             │        │
│  ┗━━━━━━━━━━━━━┛  └─────────────┘  └─────────────┘        │
│        ▲ highlighted                                      │
│         ←/→ select · Enter confirm                        │
└──────────────────────────────────────────────────────────┘
```
Left/right arrow + number-key selection; highlighted card gets emphasis (bright
border, expanded description text inside its card). **Both the class screen and the
difficulty screen use this same horizontal 3-card layout** (difficulty: EASY /
MEDIUM / HARD cards with themed icons) — one generic picker screen, two configs. Card art comes from `assets/sprites/ui/` by convention
(`class_guardian.png`, `difficulty_easy.png`, …) with the same placeholder fallback
as everything else. Replaces the current typewriter-text menus rendered in the output
panel. Difficulty stays pick-once-at-start (per the difficulty-picker spec).

### Small terminals
Below a minimum size (scene needs ~16 rows), the scene collapses to a one-line strip
(current `RoomStrip` behavior) and the output panel regains the space. No crash, no
squished art.

## Architecture

New package `src/scene/` (backend-free, pure presentation helpers) + one new widget.

```
assets/sprites/            ← NEW, top-level; PNGs, committed to repo
  classes/guardian.png …
  enemies/corrupt_process.bin.png …
  npcs/oracle.db.png …
  backdrops/core.png …     ← keyed by zone
  backdrops/rooms/<room_id>.png   ← optional per-room override (wins over zone)
  ui/logo.png, ui/difficulty_easy.png …

src/scene/
  sprite_store.py   ← load PNG → Rich renderable (half-blocks); cache; placeholder gen
  compositor.py     ← pure: (backdrop, sprites, nameplates, effect offsets) → frame
  effects.py        ← effect timeline definitions (lunge, flash, shake, drain, faint)

src/ui/panels/scene_view.py  ← SceneView widget: explore/battle modes, subscribes to
                               nothing itself — textual_ui pushes DTOs into it (same
                               pattern as stats/inventory panels)
src/ui/screens/selection_screen.py ← generic full-screen vertical picker w/ art
```

### SpriteStore
- `get_sprite(kind, entity_id, max_cells_w, max_cells_h) -> RichRenderable`
- Resolution order: exact PNG by id → generated placeholder.
- Placeholder = deterministic tinted silhouette block + entity initial, colored by a
  hash of the id — so unfinished art is obvious but not ugly, and every entity renders
  from day one.
- Caches decoded renderables; PNGs are tiny (≤ 64×64 px), negligible memory.
- Wraps `rich-pixels` (new deps: `rich-pixels`, `Pillow` in requirements.txt).

### Compositor
Pure function, unit-testable without Textual:
`compose_explore(backdrop, entities: list[Placed]) -> frame` and
`compose_battle(player: Fighter, enemy: Fighter, fx: FxState) -> frame`.
`Fighter = (sprite, name, level, hp, max_hp)` — built from existing `EnemyView` /
`StatsView` DTOs. Handles slotting (up to ~3 NPC + ~3 enemy positions in explore),
nameplate rendering, HP-bar drawing, applying per-sprite x/y offsets + tint from
effects.

### Effects (v1, all procedural)
| Trigger (existing event) | Effect |
|---|---|
| player attack | player sprite lunges +2 cells toward enemy, snap back |
| enemy takes damage | enemy sprite white-flash 2 frames + damage number pop |
| player takes damage | player flash + screen-edge shake 1 cell |
| HP change | HP bar drains/heals smoothly over ~0.4 s |
| enemy defeated | enemy sprite slides down + fades, nameplate greys |
| heal | green pulse on player sprite |

Driven by `set_timer` ticks in `SceneView` (~10 fps only while an effect is active;
idle scene renders once, no loop). `reduce_motion` setting: effects skip to end state.

### Data flow (no new events needed for explore/battle)
- `ROOM_ENTERED` / room refresh → textual_ui already receives room data → pushes a
  scene DTO into `SceneView.show_explore(...)`.
- `COMBAT_STARTED` / damage / `ENEMY_DEFEATED` / stats-changed → already handled by
  textual_ui for the combat panel → re-pointed at `SceneView.show_battle(...)` /
  `SceneView.play_effect(...)`.
- **DTO gap to close:** `RoomView` carries enemy/npc *names* only; scene needs *ids*
  for sprite lookup. Add `enemy_ids: list[str]`, `npc_ids: list[str]` to `RoomView`
  (view_builder fills them). `EnemyView` already has `id`. Player sprite key =
  class id from `StatsView` (add `class_id` if only display name exists).

## Phasing (each ships alone)

1. **Phase 1 — layout + pipeline + explore scene.** Deps, `src/scene/`, placeholder
   generation, layout restructure (scene replaces room/entity strips, output shrinks,
   sidebar slims), explore compositing, small-terminal collapse.
2. **Phase 2 — battle scene.** Battle mode, nameplates/HP in scene, effects engine,
   delete `combat_panel.py`, re-point its event handlers.
3. **Phase 3 — selection screens.** Generic full-screen picker screen, apply to
   title / difficulty / class flows, UI art slots.

## Testing

- `sprite_store`: convention resolution (exact hit, room-override beats zone,
  placeholder fallback), cache hit, deterministic placeholder for same id.
- `compositor`: pure-function tests — given fighters/entities + fx offsets, assert
  frame contents (nameplate text, HP bar proportions, sprite placement slots).
- `effects`: timeline math (offset at t) as pure functions.
- Widget/layout: smoke test that app composes with new layout (existing pattern).
- Existing suite must stay green; `engine.validate` untouched (no content change).

## Risks

- **Terminal color depth**: half-block art needs truecolor; most modern terminals fine.
  Rich auto-downsamples to 256 colors — art degrades gracefully, no code needed.
- **Textual 0.47 pin**: `rich-pixels` targets Rich (works in Textual). Verify pin
  compatibility during Phase 1 task 1; fallback is a ~80-line in-house half-block
  renderer with the same SpriteStore interface.
- **Layout regressions**: intro/typewriter and combat-hint screens assume current
  output panel — Phase 1 must re-test intro, save/load, and log viewer flows.
