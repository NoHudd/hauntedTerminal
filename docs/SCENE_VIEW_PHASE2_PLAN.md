# Scene View Phase 2 (Battle Scene) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pokemon-style battle mode in SceneView — sprites + nameplates/HP bars in the scene, code-driven effects (lunge, flash, HP drain, faint, pop numbers) — and delete the now-redundant combat sidebar panel.

**Architecture:** Battle frame = Rich Group of three parts: enemy nameplate (Text row) / composed PIL image (enemy sprite top-right, player sprite bottom-left on the room backdrop) / player nameplate (Text row). Effects are pure timeline math in `src/scene/effects.py`; `SceneView` drives them with a ~10 fps `set_interval` ticker that runs ONLY while an effect or HP animation is active. Game logic untouched — all wiring is re-pointing existing `textual_ui` combat handlers from CombatPanel to SceneView.

**Tech Stack:** Pillow (compositing + white-flash tint), rich-pixels (render), Textual timers, pytest.

## Global Constraints

- No game-logic changes: `src/combat.py`, `src/command_handler.py`, event payloads untouched.
- `textual==8.2.8` pin unchanged; no new dependencies.
- Effects respect the existing `reduce_motion` setting: skip animation, snap to end state.
- Existing combat behavior stays: attack list/hints still arrive in the output panel; stats panel still shows `refresh_combat`; `combat-active` CSS styling of other panels stays.
- User runs all git commits — commit steps are COMMANDS TO PROPOSE, never run `git commit`.
- Tests via `python -m pytest` in venv.

## Deviations from the spec's effects table (deliberate, user to confirm)

- **Screen-edge shake** on player hit: NOT re-implemented — the existing red border
  flash (`panel-update` class in `_show_floating_number`) already covers "you got hit"
  feedback and is kept.
- **Faint slide-out** on enemy defeat: deferred — `COMBAT_ENDED` restores the explore
  scene immediately; a slide needs a delay hook into that flow. Candidate for a
  follow-up alongside sprite frame animation.
- **Heal green pulse on sprite**: delivered as the `💚 +N` nameplate pop instead of a
  sprite tint (same slot as damage pops; one mechanism, both directions).

## File map

| File | Role |
|---|---|
| `src/scene/effects.py` (create) | pure timeline math: FxState, lunge offset, flash on/off, HP interpolation |
| `src/scene/compositor.py` (modify) | + `compose_battle`, `whiten`, `hp_bar`, `nameplate` |
| `src/ui/panels/scene_view.py` (modify) | battle mode: show_battle / update_battle / play_effect / end_battle + ticker |
| `src/ui/textual_ui.py` (modify) | re-point 6 combat call sites; remove CombatPanel |
| `src/ui/ui.css` (modify) | sidebar grid 3→2 rows; drop `#combat-panel` rules |
| Delete: `src/ui/panels/combat_panel.py` | replaced by in-scene nameplates |
| `tests/test_effects.py`, `tests/test_compositor_battle.py` (create) | unit tests |

---

### Task 1: Effects — pure timeline math

**Files:**
- Create: `src/scene/effects.py`
- Test: `tests/test_effects.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) FxState: player_dx: int = 0; enemy_dx: int = 0; player_flash: bool = False; enemy_flash: bool = False` (dx in px toward the opponent)
  - `lunge_offset(t: float, duration: float = 0.3, max_px: int = 6) -> int` — triangle: 0 at t≤0, max at duration/2, 0 at t≥duration
  - `flash_on(t: float, duration: float = 0.3) -> bool` — True/False alternating every 0.1 s while t within [0, duration), False after
  - `approach(current: float, target: float, dt: float, seconds: float = 0.4) -> float` — moves current toward target so the whole distance closes in `seconds`; clamps at target (HP-drain interpolation)

- [ ] **Step 1: Write the failing tests**

`tests/test_effects.py`:

```python
"""Effects: pure timeline math for battle animation."""
from src.scene.effects import FxState, approach, flash_on, lunge_offset


def test_lunge_starts_and_ends_at_zero():
    assert lunge_offset(0.0) == 0
    assert lunge_offset(0.3) == 0
    assert lunge_offset(1.0) == 0  # long after: settled


def test_lunge_peaks_mid():
    assert lunge_offset(0.15) == 6
    assert 0 < lunge_offset(0.08) <= 6


def test_flash_alternates_then_stops():
    assert flash_on(0.0) is True
    assert flash_on(0.1) is False
    assert flash_on(0.2) is True
    assert flash_on(0.3) is False   # duration reached
    assert flash_on(5.0) is False


def test_approach_closes_distance_and_clamps():
    v = approach(100.0, 60.0, dt=0.2, seconds=0.4)
    assert v == 80.0                 # half the distance in half the time
    assert approach(61.0, 60.0, dt=1.0) == 60.0   # clamps at target
    assert approach(60.0, 60.0, dt=0.1) == 60.0   # no-op at target


def test_fxstate_defaults():
    fx = FxState()
    assert fx.player_dx == 0 and fx.enemy_dx == 0
    assert fx.player_flash is False and fx.enemy_flash is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_effects.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.scene.effects'`.

- [ ] **Step 3: Implement**

`src/scene/effects.py`:

```python
"""
Effects — pure timeline math for battle animation.

No Textual, no PIL: given a time t since the effect started, return where a
sprite should be / whether it should flash. SceneView owns the clock and calls
these every tick. All durations in seconds.
"""
from dataclasses import dataclass

LUNGE_SECONDS = 0.3
FLASH_SECONDS = 0.3
FLASH_PERIOD = 0.1   # on/off toggle interval
HP_DRAIN_SECONDS = 0.4


@dataclass(frozen=True)
class FxState:
    """Per-frame effect offsets applied by the compositor. dx = px toward opponent."""
    player_dx: int = 0
    enemy_dx: int = 0
    player_flash: bool = False
    enemy_flash: bool = False


def lunge_offset(t: float, duration: float = LUNGE_SECONDS, max_px: int = 6) -> int:
    """Triangle wave: dash toward the opponent and snap back."""
    if t <= 0 or t >= duration:
        return 0
    half = duration / 2
    frac = t / half if t < half else (duration - t) / half
    return round(max_px * frac)


def flash_on(t: float, duration: float = FLASH_SECONDS) -> bool:
    """Blink: on for FLASH_PERIOD, off for FLASH_PERIOD, while t < duration."""
    if t < 0 or t >= duration:
        return False
    return int(t / FLASH_PERIOD) % 2 == 0


def approach(current: float, target: float, dt: float, seconds: float = HP_DRAIN_SECONDS) -> float:
    """Move `current` toward `target`, covering the full gap in `seconds`."""
    if current == target:
        return target
    step = abs(current - target) * min(1.0, dt / seconds) if seconds > 0 else abs(current - target)
    # Guarantee progress even for tiny gaps so we terminate.
    step = max(step, 1.0 * dt / max(seconds, dt))
    if current > target:
        return max(target, current - step)
    return min(target, current + step)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_effects.py -q`
Expected: 5 passed.

NOTE: `test_approach_closes_distance_and_clamps` expects exactly 80.0 for
(100→60, dt 0.2/0.4). With the min-step guard the value is `100 - max(20, 0.5) = 80.0`
— exact. If float noise appears, compare with `pytest.approx`.

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add src/scene/effects.py tests/test_effects.py
git commit -m "feat(scene): effect timeline math — lunge, flash, HP-drain interpolation"
```

---

### Task 2: Compositor battle assembly — sprites, flash tint, HP bar, nameplate

**Files:**
- Modify: `src/scene/compositor.py`
- Test: `tests/test_compositor_battle.py`

**Interfaces:**
- Consumes: `FxState` (Task 1).
- Produces (all in `src/scene/compositor.py`):
  - `whiten(img: Image.Image) -> Image.Image` — white-flash version, alpha preserved
  - `compose_battle(backdrop: Image.Image, player_img: Image.Image, enemy_img: Image.Image, fx: FxState) -> Image.Image` — enemy top-right (moves LEFT by `fx.enemy_dx`), player bottom-left (moves RIGHT by `fx.player_dx`); flashing fighter drawn whitened
  - `hp_bar(hp: int, max_hp: int, width: int = 12) -> str` — Rich markup `▉`/`░` bar, green > 50 %, yellow > 25 %, red otherwise; hp clamped to [0, max_hp]
  - `nameplate(name: str, hp: int, max_hp: int, icon: str = "", pop: str = "") -> str` — one markup line: `{icon} {NAME}  HP {hp}/{max_hp} {bar} {pop}`

- [ ] **Step 1: Write the failing tests**

`tests/test_compositor_battle.py`:

```python
"""Compositor battle mode: placement, flash tint, HP bars, nameplates."""
from PIL import Image

from src.scene.compositor import compose_battle, hp_bar, nameplate, whiten
from src.scene.effects import FxState


def _backdrop():
    return Image.new("RGBA", (100, 40), (5, 5, 5, 255))


def _sprite(color):
    return Image.new("RGBA", (10, 10), color)


def test_enemy_top_right_player_bottom_left():
    img = compose_battle(_backdrop(), _sprite((0, 255, 0, 255)), _sprite((255, 0, 0, 255)), FxState())
    # red (enemy) somewhere in the top-right quadrant
    tr = img.crop((50, 0, 100, 20))
    assert any(p[0] == 255 and p[1] == 0 for p in tr.getdata())
    # green (player) somewhere in the bottom-left quadrant
    bl = img.crop((0, 20, 50, 40))
    assert any(p[1] == 255 and p[0] == 0 for p in bl.getdata())


def test_lunge_moves_player_right():
    still = compose_battle(_backdrop(), _sprite((0, 255, 0, 255)), _sprite((255, 0, 0, 255)), FxState())
    lunged = compose_battle(_backdrop(), _sprite((0, 255, 0, 255)), _sprite((255, 0, 0, 255)), FxState(player_dx=6))
    def leftmost_green(im):
        px = list(im.getdata())
        w = im.size[0]
        return min(i % w for i, p in enumerate(px) if p[1] == 255 and p[0] == 0)
    assert leftmost_green(lunged) == leftmost_green(still) + 6


def test_flash_whitens_enemy():
    flashed = compose_battle(_backdrop(), _sprite((0, 255, 0, 255)), _sprite((120, 0, 0, 255)), FxState(enemy_flash=True))
    tr = flashed.crop((50, 0, 100, 20))
    assert any(p[0] > 200 and p[1] > 200 and p[2] > 200 for p in tr.getdata())


def test_whiten_preserves_alpha():
    img = Image.new("RGBA", (4, 4), (10, 10, 10, 0))  # fully transparent
    assert all(p[3] == 0 for p in whiten(img).getdata())


def test_hp_bar_proportions_and_color():
    full = hp_bar(100, 100, width=10)
    assert full.count("▉") == 10 and "green" in full
    half = hp_bar(50, 100, width=10)
    assert half.count("▉") == 5
    low = hp_bar(10, 100, width=10)
    assert "red" in low
    assert hp_bar(-5, 100, width=10).count("▉") == 0   # clamped


def test_nameplate_contains_everything():
    line = nameplate("daemon.exe", 34, 50, icon="💀", pop="[red]-12![/red]")
    assert "DAEMON.EXE" in line and "34/50" in line and "-12!" in line and "💀" in line
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_compositor_battle.py -q`
Expected: FAIL — `ImportError: cannot import name 'compose_battle'`.

- [ ] **Step 3: Implement (append to `src/scene/compositor.py`)**

```python
# --- battle mode -------------------------------------------------------------

_BATTLE_MARGIN = 2  # px from the arena edges


def whiten(img: Image.Image) -> Image.Image:
    """White-flash version of a sprite; transparent pixels stay transparent."""
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    out = Image.blend(img.convert("RGBA"), white, 0.8)
    out.putalpha(img.getchannel("A"))
    return out


def compose_battle(
    backdrop: Image.Image,
    player_img: Image.Image,
    enemy_img: Image.Image,
    fx: "FxState",
) -> Image.Image:
    """Pokemon framing: enemy top-right, player bottom-left. dx moves toward opponent."""
    img = backdrop.copy()
    w, h = img.size

    enemy = whiten(enemy_img) if fx.enemy_flash else enemy_img
    player = whiten(player_img) if fx.player_flash else player_img

    ew, eh = enemy.size
    ex = max(0, w - ew - _BATTLE_MARGIN - fx.enemy_dx)   # enemy lunges LEFT
    ey = _BATTLE_MARGIN
    img.paste(enemy, (ex, ey), enemy)

    pw, ph = player.size
    px_ = min(w - pw, _BATTLE_MARGIN + fx.player_dx)     # player lunges RIGHT
    py = max(0, h - ph - _BATTLE_MARGIN)
    img.paste(player, (px_, py), player)
    return img


def hp_bar(hp: int, max_hp: int, width: int = 12) -> str:
    """Rich-markup HP bar, colored by remaining fraction."""
    max_hp = max(1, max_hp)
    hp = max(0, min(hp, max_hp))
    frac = hp / max_hp
    filled = round(width * frac)
    color = "green" if frac > 0.5 else ("yellow" if frac > 0.25 else "red")
    return f"[{color}]{'▉' * filled}[/{color}][dim]{'░' * (width - filled)}[/dim]"


def nameplate(name: str, hp: int, max_hp: int, icon: str = "", pop: str = "") -> str:
    """One-line fighter nameplate for above/below the arena image."""
    lead = f"{icon} " if icon else ""
    tail = f"  {pop}" if pop else ""
    return f"[bold]{lead}{name.upper()}[/bold]  HP {hp}/{max_hp} {hp_bar(hp, max_hp)}{tail}"
```

Also add the import at the top of `compositor.py` (type-only, avoids cycles at runtime — effects imports nothing from compositor, so a plain import is fine):

```python
from src.scene.effects import FxState
```
(then drop the string quotes on `fx: FxState` in `compose_battle` — quoted form above is only for reading order in this plan).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_compositor_battle.py tests/test_compositor.py -q`
Expected: 10 passed (6 new + 4 existing explore tests untouched).

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add src/scene/compositor.py tests/test_compositor_battle.py
git commit -m "feat(scene): battle compositing — Pokemon framing, flash tint, HP bars, nameplates"
```

---

### Task 3: SceneView battle mode + effect ticker

**Files:**
- Modify: `src/ui/panels/scene_view.py`

**Interfaces:**
- Consumes: `compose_battle`, `hp_bar`, `nameplate`, `whiten` (Task 2); `FxState`, `lunge_offset`, `flash_on`, `approach`, `LUNGE_SECONDS`, `FLASH_SECONDS` (Task 1).
- Produces (called by `textual_ui` in Task 4):
  - `show_battle(combat_view: dict, player_view: dict, reduce_motion: bool = False) -> None`
  - `update_battle(combat_view: dict) -> None` — new HP targets; drain animates (or snaps under reduce_motion)
  - `play_effect(kind: str, actor: str, amount: int) -> None` — kind `"damage"|"heal"`; pop text + lunge/flash
  - `end_battle() -> None` — returns to the cached explore scene (or loading text if none)

- [ ] **Step 1: Implement**

Extend `src/ui/panels/scene_view.py`. New imports at top:

```python
import time

from src.scene.effects import (
    FLASH_SECONDS,
    LUNGE_SECONDS,
    FxState,
    approach,
    flash_on,
    lunge_offset,
)
from src.scene.compositor import compose_battle, nameplate
```
(keep the existing `Placed, compose_explore` import line as-is)

New class attributes / methods inside `SceneView` (add `self._battle = None`,
`self._ticker = None` to `__init__`):

```python
    _TICK_SECONDS = 0.1
    _POP_SECONDS = 0.7
    _CLASS_ICONS = {"guardian": "🛡", "weaver": "✨", "shaman": "🌿"}

    # -- battle mode ----------------------------------------------------------

    def show_battle(self, combat_view: dict, player_view: dict, reduce_motion: bool = False) -> None:
        """Enter battle mode. Called once per combat (COMBAT_STARTED)."""
        self._battle = {
            "view": combat_view,
            "player_name": player_view.get("player_name", "You"),
            "player_class": player_view.get("player_class", ""),
            "reduce_motion": reduce_motion,
            # displayed HP floats — drained smoothly toward the view's targets
            "shown_player_hp": float(combat_view.get("player_health", 0)),
            "shown_enemy_hp": float(combat_view.get("enemy_health", 0)),
            "fx_kind": None,      # "damage" | "heal"
            "fx_actor": None,     # "player" | "enemy"
            "fx_started": 0.0,
            "pop_text": "",
            "pop_target": "",     # "player" | "enemy"
            "pop_until": 0.0,
            "last_tick": time.monotonic(),
        }
        self.border_title = "⚔ BATTLE"
        self.border_subtitle = ""
        self._render_battle(FxState())

    def update_battle(self, combat_view: dict) -> None:
        """Per-turn frame update (COMBAT_FRAME_UPDATED): new HP targets."""
        if not self._battle:
            return
        self._battle["view"] = combat_view
        if self._battle["reduce_motion"]:
            self._battle["shown_player_hp"] = float(combat_view.get("player_health", 0))
            self._battle["shown_enemy_hp"] = float(combat_view.get("enemy_health", 0))
            self._render_battle(FxState())
        else:
            self._ensure_ticker()

    def play_effect(self, kind: str, actor: str, amount: int) -> None:
        """Damage/heal feedback: lunge + flash + pop number (COMBAT_ACTION_RESULT)."""
        if not self._battle:
            return
        b = self._battle
        # Pop target mirrors the old combat panel: damage pops over the victim,
        # heal pops over the actor.
        if kind == "damage":
            target = "enemy" if actor == "player" else "player"
            b["pop_text"] = f"[bold red]💥 -{amount}[/bold red]"
        else:
            target = "player" if actor == "player" else "enemy"
            b["pop_text"] = f"[bold green]💚 +{amount}[/bold green]"
        b["pop_target"] = target
        now = time.monotonic()
        b["pop_until"] = now + self._POP_SECONDS
        b["fx_kind"] = kind
        b["fx_actor"] = actor
        b["fx_started"] = now
        if b["reduce_motion"]:
            self._render_battle(FxState())
            self.set_timer(self._POP_SECONDS, self._clear_pop)
        else:
            self._ensure_ticker()

    def end_battle(self) -> None:
        """Leave battle mode; restore the explore scene (COMBAT_ENDED / game over)."""
        self._stop_ticker()
        self._battle = None
        if self._room is not None:
            self._render_scene()
        else:
            self.show_loading()

    # -- battle internals -------------------------------------------------------

    def _clear_pop(self) -> None:
        if self._battle:
            self._battle["pop_text"] = ""
            self._render_battle(FxState())

    def _ensure_ticker(self) -> None:
        if self._ticker is None:
            self._battle["last_tick"] = time.monotonic()
            self._ticker = self.set_interval(self._TICK_SECONDS, self._tick_battle)

    def _stop_ticker(self) -> None:
        if self._ticker is not None:
            self._ticker.stop()
            self._ticker = None

    def _tick_battle(self) -> None:
        b = self._battle
        if not b:
            self._stop_ticker()
            return
        now = time.monotonic()
        dt = now - b["last_tick"]
        b["last_tick"] = now
        view = b["view"]

        # HP drain toward targets
        b["shown_player_hp"] = approach(b["shown_player_hp"], float(view.get("player_health", 0)), dt)
        b["shown_enemy_hp"] = approach(b["shown_enemy_hp"], float(view.get("enemy_health", 0)), dt)

        # Active lunge/flash
        fx = FxState()
        if b["fx_kind"]:
            t = now - b["fx_started"]
            if b["fx_kind"] == "damage":
                if b["fx_actor"] == "player":
                    fx = FxState(player_dx=lunge_offset(t), enemy_flash=flash_on(t))
                else:
                    fx = FxState(enemy_dx=lunge_offset(t), player_flash=flash_on(t))
            if t >= max(LUNGE_SECONDS, FLASH_SECONDS):
                b["fx_kind"] = None

        # Expire the pop
        if b["pop_text"] and now >= b["pop_until"]:
            b["pop_text"] = ""

        self._render_battle(fx)

        # Idle again? stop burning CPU.
        hp_settled = (
            b["shown_player_hp"] == float(view.get("player_health", 0))
            and b["shown_enemy_hp"] == float(view.get("enemy_health", 0))
        )
        if hp_settled and not b["fx_kind"] and not b["pop_text"]:
            self._stop_ticker()

    def _render_battle(self, fx: FxState) -> None:
        b = self._battle
        if not b:
            return
        view = b["view"]
        room = self._room or {}

        w_cells = max(20, self.content_size.width or 60)
        h_rows = self.content_size.height or 0
        if h_rows < MIN_SCENE_ROWS:
            self.update(Text.from_markup(
                f"[bold red]⚔ {view.get('enemy_name', '?')}[/bold red] "
                f"{int(b['shown_enemy_hp'])}/{view.get('enemy_max_health', 0)}"
                f"  vs  [bold green]{b['player_name']}[/bold green] "
                f"{int(b['shown_player_hp'])}/{view.get('player_max_health', 0)}"
            ))
            return

        # Two text rows (nameplates) + image
        img_w, img_h = w_cells, (h_rows - 2) * 2
        backdrop = self._store.get_backdrop(room.get("id", ""), room.get("zone", ""), img_w, img_h)
        enemy_img = self._store.get_sprite("enemies", view.get("enemy_id", view.get("enemy_name", "?")), SPRITE_MAX_PX, SPRITE_MAX_PX)
        player_img = self._store.get_sprite("classes", b["player_class"], SPRITE_MAX_PX, SPRITE_MAX_PX)

        arena = compose_battle(backdrop, player_img, enemy_img, fx)

        pop = b["pop_text"]  # expiry is handled by the ticker / _clear_pop
        enemy_line = nameplate(
            view.get("enemy_name", "?"), int(b["shown_enemy_hp"]), view.get("enemy_max_health", 1),
            icon="💀", pop=pop if b["pop_target"] == "enemy" else "",
        )
        player_line = nameplate(
            b["player_name"], int(b["shown_player_hp"]), view.get("player_max_health", 1),
            icon=self._CLASS_ICONS.get(b["player_class"], "🧙"), pop=pop if b["pop_target"] == "player" else "",
        )
        self.update(Group(
            Text.from_markup(enemy_line),
            to_renderable(arena),
            Text.from_markup(player_line),
        ))
```

Also guard the explore path: in `on_resize`, re-render battle when in battle:

```python
    def on_resize(self) -> None:
        if self._battle is not None:
            self._render_battle(FxState())
        elif self._room is not None:
            self._render_scene()
```

NOTE — `enemy_id` in `CombatView`: the view dict has `enemy_name` but check
`src/viewmodels/view_models.py:89` (`CombatView`) for an id field. If it lacks one,
add `enemy_id: str = ""` to `CombatView` and fill it in `build_combat_view`
(`src/viewmodels/view_builder.py:165`, callers pass `enemy_data`; the caller in
`src/command_handler.py` knows the enemy id — pass it through). Same additive-default
pattern as Phase 1's RoomView change. The sprite lookup falls back to a placeholder
on any id mismatch, so this cannot crash — but without the real id, custom enemy art
would not show in battle.

- [ ] **Step 2: Verify import + explore regression**

Run: `python -m pytest tests/test_sprite_store.py tests/test_compositor.py tests/test_compositor_battle.py tests/test_effects.py -q && python -c "from src.ui.panels.scene_view import SceneView; print('ok')"`
Expected: all pass, `ok`.

- [ ] **Step 3: Commit (propose to user — do not run)**

```bash
git add src/ui/panels/scene_view.py src/viewmodels/
git commit -m "feat(scene): battle mode in SceneView — nameplates, HP drain, lunge/flash effects"
```

---

### Task 4: Re-point textual_ui; delete CombatPanel

**Files:**
- Modify: `src/ui/textual_ui.py` (call sites: import ~31, compose ~124, on_mount ~134+140, `_update_combat_panels` ~738-743, `_show_combat_ui` ~715, `_hide_combat_ui` ~725, `_show_floating_number` ~900-905, `_update_all_panels_to_defaults` ~926, `display_game_over` area ~231)
- Modify: `src/ui/ui.css` (sidebar grid, `#combat-panel` rules)
- Delete: `src/ui/panels/combat_panel.py`

**Interfaces:**
- Consumes: `show_battle` / `update_battle` / `play_effect` / `end_battle` (Task 3).

- [ ] **Step 1: textual_ui changes**

1. Delete `from src.ui.panels.combat_panel import CombatPanel` (line ~31).
2. `compose()`: delete `yield CombatPanel(id="combat-panel")`.
3. `on_mount()`: delete `self._combat_panel = ...` and `self._combat_panel.border_title = "⚔ Combat"`.
4. `_show_combat_ui()` becomes:
```python
    def _show_combat_ui(self):
        """Show combat UI: battle scene + combat styling."""
        self.add_class("combat-active")
        self._scene_view.show_battle(
            self._combat_view,
            self._player_view or {},
            reduce_motion=bool(self._settings_manager.settings.get("reduce_motion", False)),
        )
        self._update_combat_panels()
```
5. `_hide_combat_ui()`: replace `self._combat_panel.show_idle()` with `self._scene_view.end_battle()`.
6. `_update_combat_panels()`: replace `self._combat_panel.refresh_combat(...)` with `self._scene_view.update_battle(self._combat_view)` (keep the stats-panel line).
7. `_show_floating_number()`: replace the combat-panel pop block with:
```python
        try:
            self._scene_view.play_effect(effect_type, actor, amount)
        except Exception as e:
            logger.debug(f"Damage pop failed: {e}")
```
   (drop the `set_timer(0.7, ...)` — SceneView expires its own pop; keep the border-flash lines below it.)
8. `_update_all_panels_to_defaults()`: delete the `self._combat_panel.show_idle()` line.
9. `display_game_over()` (~line 231 `remove_class("combat-active")` block): replace `self._combat_panel.show_idle()` with `self._scene_view.end_battle()`.

Then:
```bash
rm src/ui/panels/combat_panel.py
grep -rn "combat_panel\|CombatPanel\|combat-panel" src/ tests/
```
Expected grep: only `src/ui/ui.css` hits remain (handled next step).

- [ ] **Step 2: CSS**

In `src/ui/ui.css`:
- `#sidebar` grid: `grid-rows: 1fr 1fr 1fr;` → `grid-rows: 1fr 1fr;`
- Delete the `#combat-panel { ... }` and `.combat-active #combat-panel { ... }` blocks.
- Keep every other `.combat-active` rule (stats/output/inventory/input styling stays).

Verify: `grep -n "combat-panel" src/ui/ui.css` → no hits.

- [ ] **Step 3: Full gate**

```bash
python -m pytest -q
python -c "import main"
python -m engine.validate data
```
Expected: suite green, IMPORT OK, validate OK.

- [ ] **Step 4: Manual smoke (ask the user)**

`python main.py` → start a run → walk into an enemy room → battle starts:
- scene flips to ⚔ BATTLE: enemy sprite top-right with 💀 nameplate + HP bar, player bottom-left with class icon nameplate
- attack → player sprite lunges right, enemy flashes white, `💥 -N` pops on the enemy line, enemy HP bar drains smoothly
- get hit → your sprite flashes, `💥 -N` on your line
- use a heal item → `💚 +N` on your line, bar refills
- win → scene returns to the room view; sidebar shows only Inventory + Stats
- Settings → reduce motion ON → effects snap instead of animating

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add -A src/ui/
git commit -m "feat(ui): battle scene replaces combat panel — sidebar slims to inventory+stats"
```
