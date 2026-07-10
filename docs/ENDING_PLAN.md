# Ending Sequence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cinematic finale — paced per-class epilogue + scene brightening + run-stats recap — and post-game "new game" that re-offers difficulty/class.

**Architecture:** `win_game()` stops printing and emits one `GAME_WON` event (sections + stats). TextualGameUI performs it (timer-chained reveal, skippable; SceneView backdrop brightens); HeadlessUI just logs the joined text. Run stats are two new counters on Player, saved as `runStats`.

**Tech Stack:** existing event bus, Textual timers, PIL ImageEnhance, pytest (headless via `engine.api.GameSession`).

## Global Constraints

- Save JSON keys camelCase (`runStats`); YAML/content untouched.
- `reduce_motion` setting: finale renders instantly (no timers, full-brightness scene).
- Old saves without `runStats` must load (default `{"kills": 0, "items_found": 0}`).
- Post-game `n` (victory AND death) must land in `waiting_for_difficulty`, not PLAYING.
- User runs all git commits — propose only. Tests via `python -m pytest` in venv.

---

### Task 1: Run-stats counters + save round-trip

**Files:**
- Modify: `src/player.py` (init ~line 25; to_dict/from_dict ~line 455 area)
- Modify: `src/command_handler.py` (`_award_enemy_drops` ~line 928)
- Modify: the take path — find with `grep -rn "Added \[white\]" src/` (TakeCommand)
- Test: `tests/test_run_stats.py`

**Interfaces:**
- Produces: `player.run_stats: dict` with keys `kills`, `items_found`; incremented on enemy defeat and successful take; serialized as `runStats` in the save payload; loads with defaults from old saves.

- [ ] **Step 1: Write the failing tests**

```python
"""Run stats: kill/item counters + save round-trip."""
import json

from engine.api import GameSession


def test_take_increments_items_found():
    s = GameSession()
    s.new_game("t", "guardian")
    s.world.item_locations["health_packet"] = s.player.current_room
    before = s.player.run_stats["items_found"]
    s.submit("take health_packet")
    assert s.player.run_stats["items_found"] == before + 1
    s.close()


def test_kill_increments_kills(tmp_path):
    s = GameSession()
    s.new_game("t", "guardian")
    s.player.total_damage = 9999
    s.world.enemy_locations["corrupt_process.bin"] = s.player.current_room
    s.submit("attack corrupt_process.bin")
    # one-tap kill resolves within the command
    assert s.player.run_stats["kills"] >= 1
    s.close()


def test_run_stats_save_round_trip(tmp_path):
    from src.player import Player
    p = Player(name="t", player_class="guardian")
    p.run_stats["kills"] = 7
    data = p.to_dict()
    assert data["runStats"]["kills"] == 7
    p2 = Player.from_dict(data)
    assert p2.run_stats == p.run_stats


def test_old_save_without_runstats_loads():
    from src.player import Player
    p = Player(name="t", player_class="guardian")
    data = p.to_dict()
    del data["runStats"]
    p2 = Player.from_dict(data)
    assert p2.run_stats == {"kills": 0, "items_found": 0}
```
NOTE: adjust `to_dict`/`from_dict` method names to whatever `src/player.py` actually
uses (check ~line 440-460: the loader reads `data.get("total_damage", ...)`); if
serialization lives in `src/save.py` instead, put the round-trip assertions on the
same seam save/load actually use. `enemy_locations` keying: verify with the existing
world code (memory: keyed BY ENEMY ID → room, like item_locations).

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_run_stats.py -q` → AttributeError: run_stats.

- [ ] **Step 3: Implement**

`src/player.py` `__init__`:
```python
        self.run_stats = {"kills": 0, "items_found": 0}  # lifetime-of-run counters
```
Serializer: add `"runStats": self.run_stats` to the save dict; loader:
```python
        player.run_stats = data.get("runStats", {"kills": 0, "items_found": 0})
```
`src/command_handler.py` `_award_enemy_drops` (top of method):
```python
        self.player.run_stats["kills"] = self.player.run_stats.get("kills", 0) + 1
```
Take path (immediately after the successful `add_to_inventory` + "Added …" write):
```python
        ctx.player.run_stats["items_found"] = ctx.player.run_stats.get("items_found", 0) + 1
```

- [ ] **Step 4: Verify** — new tests green, then `python -m pytest -q` full suite green.

- [ ] **Step 5: Commit (propose — do not run)**
```bash
git add src/player.py src/command_handler.py src/commands/ src/save.py tests/test_run_stats.py
git commit -m "feat(stats): track kills + items found per run; persist as runStats"
```

---

### Task 2: GAME_WON event + win_game refactor + headless passthrough

**Files:**
- Modify: `src/events.py` (add `GAME_WON = auto()` near GAME_OVER)
- Modify: `src/command_handler.py: win_game()` (~1212-1301)
- Modify: `engine/headless/ui.py` (subscribe + log)
- Test: `tests/test_game_won_event.py`

**Interfaces:**
- Produces: `GAME_WON` event, data `{"ending_id": str, "sections": list[str], "stats": dict}`; stats keys: `level, cycles, kills, items_found, difficulty, ending, player_name, player_class`.
- `win_game()` no longer writes the epilogue via `self.output`; it still sets `_game_won=True`, `story_flags["ending_chosen"]`, `_in_game_over_mode=True`.

- [ ] **Step 1: Write the failing test**

```python
"""GAME_WON: emitted with sections + stats; headless UI logs the text."""
from engine.api import GameSession
from src.events import EventType, event_bus


def test_win_game_emits_sections_and_stats():
    s = GameSession()
    s.new_game("t", "guardian")
    got = []
    def on_won(event):
        got.append(event.data)
    event_bus.subscribe(EventType.GAME_WON, on_won)
    try:
        s.engine.cmd_handler.win_game()
    finally:
        event_bus.unsubscribe(EventType.GAME_WON, on_won)
    assert len(got) == 1
    data = got[0]
    assert data["ending_id"] == "restore"
    assert len(data["sections"]) >= 3
    stats = data["stats"]
    for key in ("level", "cycles", "kills", "items_found", "difficulty", "ending", "player_name", "player_class"):
        assert key in stats
    s.close()


def test_headless_ui_receives_ending_text():
    s = GameSession()
    s.new_game("t", "guardian")
    s.ui.drain()
    s.engine.cmd_handler.win_game()
    text = "\n".join(str(x) for x in s.ui.drain())
    assert "THANK YOU FOR PLAYING" in text
    s.close()
```

- [ ] **Step 2: RED** — `python -m pytest tests/test_game_won_event.py -q` fails (no GAME_WON).

- [ ] **Step 3: Implement**

`src/events.py` (next to GAME_OVER):
```python
    GAME_WON = auto()
    # Data: {"ending_id": str, "sections": list[str], "stats": dict}
```

`win_game()` tail — replace the two `self.output.write(...)` calls with:
```python
        sections = [part.strip() for part in message.split("\n\n") if part.strip()]
        from src import difficulty
        stats = {
            "level": getattr(self.player, "level", 1),
            "cycles": getattr(self.player, "harvesting_cycles", 0),
            "kills": self.player.run_stats.get("kills", 0),
            "items_found": self.player.run_stats.get("items_found", 0),
            "difficulty": difficulty.current_mode(),
            "ending": choice,
            "player_name": getattr(self.player, "name", ""),
            "player_class": getattr(self.player, "player_class", ""),
        }
        event_bus.emit_event(
            EventType.GAME_WON,
            {"ending_id": choice, "sections": sections, "stats": stats},
            "CommandHandler",
        )
```
(keep `story_flags`, `_game_won`, `_in_game_over_mode` exactly as today).

`engine/headless/ui.py` — in `__init__`, subscribe; joined-text passthrough:
```python
        from src.events import EventType, event_bus
        event_bus.subscribe(EventType.GAME_WON, self._on_game_won)
```
```python
    def _on_game_won(self, event: Any) -> None:
        data = event.data or {}
        self.output_log.append("\n\n".join(data.get("sections", [])))
        self.output_log.append(f"[stats] {data.get('stats', {})}")
```
(match the file's typing style; add unsubscribe in its close/shutdown if one exists —
GameSession.close calls engine._cleanup; mirror whatever the class already does.)

- [ ] **Step 4: Verify** — new tests + `python -m pytest -q` full suite (watch for leaked GAME_WON subscribers across tests — unsubscribe in test, and HeadlessUI instances subscribe per-session; if the suite shows cross-test pollution, key the handler off instance state like the save-no-recursion test did).

- [ ] **Step 5: Commit (propose — do not run)**
```bash
git add src/events.py src/command_handler.py engine/headless/ui.py tests/test_game_won_event.py
git commit -m "feat(ending): GAME_WON event carries epilogue sections + run stats"
```

---

### Task 3: Post-game `n` routes through the pickers

**Files:**
- Modify: `src/game_engine.py` (~line 357 `elif action == "start_new_game":`)
- Test: `tests/test_new_game_after_end.py`

**Interfaces:**
- Consumes: existing `_start_new_game()` (cleanup + reload + `_show_difficulty_selection()`).
- Produces: `start_new_game` action → state `waiting_for_difficulty` (not PLAYING with a default guardian).

- [ ] **Step 1: Write the failing test**

```python
"""Post-game 'n' must re-offer difficulty + class, not restart as default guardian."""
from engine.api import GameSession
from src.state_manager import state_manager


def test_n_after_win_lands_in_difficulty_picker():
    s = GameSession()
    s.new_game("t", "shaman")
    s.engine.cmd_handler.win_game()
    s.submit("n")
    assert str(state_manager.current_state) == "waiting_for_difficulty"
    s.close()
```

- [ ] **Step 2: RED** — current flow lands in `playing`.

- [ ] **Step 3: Implement** — in `game_engine.py` action dispatch:
```python
        elif action == "start_new_game":
            logger.info("Player chose new game - full setup flow (difficulty/class)")
            state_manager.set_state(GameState.MENU, emit_event=False)
            event_bus.clear_history()
            self._start_new_game()
```
Delete `_restart_new_game` if nothing else calls it — `grep -n "_restart_new_game" src/`
shows two more callers (~418, ~445); re-point those to the same `_start_new_game`
flow ONLY if they are also player-facing restarts (F5 restart should also offer
pickers — check `restart_game`); otherwise leave them and keep `_restart_new_game`.

- [ ] **Step 4: Verify** — new test + full suite; also confirm death-screen `n` follows the same action string (it does — `_handle_game_over_choice('n')` returns `"start_new_game"`).

- [ ] **Step 5: Commit (propose — do not run)**
```bash
git add src/game_engine.py tests/test_new_game_after_end.py
git commit -m "feat(ending): post-game new run re-offers difficulty + class pickers"
```

---

### Task 4: SceneView finale beat

**Files:**
- Modify: `src/ui/panels/scene_view.py`

**Interfaces:**
- Produces: `SceneView.play_finale(reduce_motion: bool = False) -> None` — ends battle mode if active, border title `✨ SYSTEM CLEAN`, backdrop brightens 0.62→1.15 in 6 steps over ~3 s (instant under reduce_motion). Idempotent (second call harmless).

- [ ] **Step 1: Implement**

```python
    _FINALE_STEPS = 6
    _FINALE_SECONDS = 3.0

    def play_finale(self, reduce_motion: bool = False) -> None:
        """Victory beat: corruption lifts — the room backdrop brightens to clean."""
        self._stop_ticker()
        if self._bob_timer is not None:
            self._bob_timer.stop()
            self._bob_timer = None
        self._battle = None
        self.border_title = "✨ SYSTEM CLEAN"
        self.border_subtitle = ""
        if reduce_motion:
            self._render_finale(1.15)
            return
        for i in range(1, self._FINALE_STEPS + 1):
            factor = 0.62 + (1.15 - 0.62) * (i / self._FINALE_STEPS)
            self.set_timer(self._FINALE_SECONDS * i / self._FINALE_STEPS,
                           lambda f=factor: self._render_finale(f))

    def _render_finale(self, brightness: float) -> None:
        from PIL import ImageEnhance
        room = self._room or {}
        w_cells = max(20, self.content_size.width or 60)
        h_rows = self.content_size.height or 0
        if h_rows < MIN_SCENE_ROWS:
            self.update(Text.from_markup("[bold green]✨ The corruption lifts.[/bold green]"))
            return
        img_w, img_h = w_cells, h_rows * 2
        backdrop = self._store.get_backdrop(room.get("id", ""), room.get("zone", ""), img_w, img_h)
        bright = ImageEnhance.Brightness(backdrop).enhance(brightness / 0.62)
        self.update(to_renderable(bright))
```
(brightness normalized against the install-time 0.62 dim so 1.15 ≈ "cleaner than
ever"; generated gradients brighten the same way.)

- [ ] **Step 2: Verify** — `python -c "from src.ui.panels.scene_view import SceneView; print('ok')"` + scene tests still green.

- [ ] **Step 3: Commit (propose — do not run)**
```bash
git add src/ui/panels/scene_view.py
git commit -m "feat(scene): finale beat — backdrop brightens as corruption lifts"
```

---

### Task 5: UI finale orchestration (paced reveal + recap + skip)

**Files:**
- Modify: `src/ui/textual_ui.py`

**Interfaces:**
- Consumes: `GAME_WON` data (Task 2), `play_finale` (Task 4).
- Produces: `_on_game_won` handler registered in `_EVENT_HANDLERS`.

- [ ] **Step 1: Implement**

`_EVENT_HANDLERS` += `(EventType.GAME_WON, "_on_game_won")`.

```python
    _FINALE_SECTION_SECONDS = 2.5

    def _on_game_won(self, event):
        """Victory: scene brightens; epilogue arrives in beats; recap card last."""
        data = event.data or {}
        reduce_motion = bool(self._settings_manager.settings.get("reduce_motion", False))
        self._scene_view.play_finale(reduce_motion=reduce_motion)

        sections = list(data.get("sections", []))
        recap = self._build_recap(data.get("stats", {}))
        self._finale_queue = sections + [recap]
        self._finale_timers = []

        self._output_fresh = True
        if reduce_motion:
            for part in self._finale_queue:
                self.update_output(part)
            self._finale_queue = []
            return
        self.update_output(self._finale_queue.pop(0))
        for i, part in enumerate(self._finale_queue, 1):
            self._finale_timers.append(
                self.set_timer(self._FINALE_SECTION_SECONDS * i,
                               lambda p=part: self._finale_step(p))
            )

    def _finale_step(self, part: str) -> None:
        self.update_output(part)
        if part.startswith("── YOUR RUN"):
            self._finale_queue = []

    def _skip_finale(self) -> None:
        """Any key during the reveal: dump everything remaining at once."""
        if not getattr(self, "_finale_timers", None):
            return
        for t in self._finale_timers:
            t.stop()
        self._finale_timers = []
        for part in self._finale_queue:
            self.update_output(part)
        self._finale_queue = []

    @staticmethod
    def _build_recap(stats: dict) -> str:
        return (
            "── YOUR RUN ──────────────────────────\n"
            f"[bold]{stats.get('player_name', '?')}[/bold] · "
            f"{str(stats.get('player_class', '?')).title()} · "
            f"ending: [cyan]{str(stats.get('ending', '?')).upper()}[/cyan]\n"
            f"Level {stats.get('level', 1)} · {stats.get('cycles', 0)} cycles harvested\n"
            f"{stats.get('kills', 0)} enemies purged · {stats.get('items_found', 0)} items recovered\n"
            f"difficulty: {stats.get('difficulty', '?')}\n"
            "──────────────────────────────────────\n"
            "[green]n[/green] new run · [red]q[/red] quit"
        )
```
Skip hook: in `on_key`, before the menu handling, add:
```python
        if getattr(self, "_finale_timers", None):
            self._skip_finale()
            event.stop()
            return
```
Bookkeeping: track `self._finale_queue`/`self._finale_timers` so `_finale_step`
pops correctly — when implementing, keep queue/timer indices consistent (each timer
carries its own part; `_finale_queue` exists for the skip path; remove each part
from the queue as its timer fires: `self._finale_queue.remove(p)` guarded by
`if p in self._finale_queue`).

- [ ] **Step 2: Full gate + manual smoke**

```bash
python -m pytest -q && python -c "import main" && python -m engine.validate data
```
Manual (fast win): easy difficulty, `python main.py`, use dev/cheat route to /core
(sudo badge etc.) or temporarily buff: the quickest honest test — set easy, level a
bit, fight through /core. Verify: scene brightens to ✨ SYSTEM CLEAN · epilogue in
beats · any key skips · recap card correct numbers · `n` → difficulty cards →
class cards → name · reduce-motion shows everything instantly.

- [ ] **Step 3: Commit (propose — do not run)**
```bash
git add src/ui/textual_ui.py
git commit -m "feat(ending): paced finale — scene beat, epilogue reveal, run recap"
```
