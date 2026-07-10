# Frontend / Backend Split — Implementation Plan (Strangler A, capstone)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Backend stops owning the frontend — `main.py` becomes the composition root that injects the TUI — then relocate the DTO layer out of `src/ui/`. Two phases, two commits.

**Architecture:** Phase 1 inverts ownership (backend no longer imports/constructs `TextualGameUI`; depends only on `UIProtocol`). Phase 2 moves `view_builder`/`view_models` (backend serialization) to `src/viewmodels/`.

**Tech Stack:** Python 3.11, Textual, pytest.

## Global Constraints

- **Zero gameplay change.** Same game, same screen.
- After Phase 1: `import src.game_engine` must NOT load Textual (verified via `sys.modules`).
- Confirmed clean: domain (`command_handler`/`combat`), `view_builder`, `ui_interface` import no
  Textual; the only Textual pull is `game_engine.py:25`.
- Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"` + the
  placement + `build_room_view` smokes. **Phase 1 also needs a live `python main.py` check the
  USER runs** (I cannot).
- User does own commits (propose; never run `git commit`). One commit per phase; **Phase 1
  commit only after the user's live check passes.**
- Spec: `docs/FRONTEND_BACKEND_SPLIT_SPEC.md`.

## File Structure

| File | Phase | Change |
|---|---|---|
| `src/game_engine.py` | 1 | drop concrete-TUI import (25); `self.ui = ui`; `main(ui)` |
| `main.py` | 1 | build `TextualGameUI`, inject via `main(ui)` |
| `src/viewmodels/` (new) | 2 | home for `view_builder.py` + `view_models.py` |
| importers of view_builder/view_models | 2 | repoint to `src.viewmodels` |

---

## Phase 1 — Ownership inversion (USER verifies live)

### Task 1: Move UI construction to the composition root

**Files:** `src/game_engine.py`, `main.py`

- [ ] **Step 1: Remove the concrete-TUI import (game_engine.py:25)**

Delete the line:
```python
from src.ui.textual_ui import TextualGameUI
```
(Keep line 26 `from src.ui.ui_interface import UIProtocol, UIError, UIInitializationError` — the
backend depends on the abstraction. Keep line 31 `ViewBuilder` — relocated in Phase 2.)

- [ ] **Step 2: Inject the UI (no in-backend default) — game_engine.py:64**

```python
        self.ui = ui
```
(was `self.ui = ui or TextualGameUI()`. Signature stays `def __init__(self, ui: Optional[UIProtocol] = None)`;
the UI is now always supplied by the composition root / `GameSession` / tests.)

- [ ] **Step 3: `main()` takes the UI — game_engine.py:926-943**

Change the signature and the engine construction:
```python
def main(ui):
    """Entry point: caller supplies the concrete UI (composition root)."""
    # Setup logging - only to file, not to console (to avoid UI interference)
    from config.dev_config import DEBUG_LOG_FILE
    root_logger = logging.getLogger()
    root_logger.handlers = []
    file_handler = logging.FileHandler(DEBUG_LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    try:
        engine = ImprovedGameEngine(ui=ui)
        engine.run()
```
(Only the `def main():`→`def main(ui):` and `ImprovedGameEngine()`→`ImprovedGameEngine(ui=ui)`
lines change; the rest of `main`'s body — KeyboardInterrupt handling etc. — is unchanged.)

- [ ] **Step 4: `main.py` (root) becomes the composition root**

Add the frontend import and pass it in. Change the existing `from src.game_engine import main`
call site so the tail reads:
```python
    from src.ui.textual_ui import TextualGameUI
    from src.game_engine import main
    main(TextualGameUI())
```
(Keep the existing `os.makedirs(...)` and debug.log/combat.log handling above it.)

- [ ] **Step 5: Verify (headless — mine)**

```bash
source venv/bin/activate
python -c "import src.game_engine, sys; assert 'textual' not in sys.modules, 'backend still pulls Textual'; print('BACKEND TEXTUAL-FREE')"
python -m pytest 2>&1 | tail -3
python -m engine.validate data 2>&1 | tail -1
python -c "import main; print('IMPORT main OK')"
python - <<'EOF'
from engine.api import GameSession
s = GameSession(); out = s.new_game("T","guardian")
assert out; print("GAMESESSION HEADLESS OK"); s.close()
EOF
```
Expected: `BACKEND TEXTUAL-FREE`; suite green (118 passed, 1 xfailed); validate OK; `IMPORT main OK`;
`GAMESESSION HEADLESS OK`.

- [ ] **Step 6: Verify (live — USER runs; I cannot)**

Hand to the user:
> Run `python main.py`. Confirm: the game launches, class-select renders, you can move
> (`cd`/`ls`), look at a room, start + resolve a fight, and the Stats/Inventory/Combat panels
> update. Save/quit works. If it plays like before → Phase 1 good. If anything is off, tell me
> what and I fix before committing.

- [ ] **Step 7: Commit — ONLY after the user's live check passes (propose)**

```bash
git add src/game_engine.py main.py
git commit -m "refactor(arch): invert UI ownership — main.py is the composition root (strangler A)

game_engine no longer imports or constructs TextualGameUI; the UI is injected. main.py
builds the concrete TUI and passes it into main(ui). Backend now depends only on UIProtocol,
so importing src.game_engine no longer loads Textual. GameSession (HeadlessUI) and tests are
unaffected — they already inject a UI. Live TUI verified by hand."
```

---

## Phase 2 — Relocate the DTO layer (I verify fully)

### Task 2: Move view_builder/view_models to a backend package

**Files:** create `src/viewmodels/`; move 2 files; update all importers.

- [ ] **Step 1: Create the package and move the files**

```bash
cd /Users/duhonyoung/Documents/HFSE-updated
mkdir -p src/viewmodels
touch src/viewmodels/__init__.py
git mv src/ui/view_builder.py src/viewmodels/view_builder.py 2>/dev/null || mv src/ui/view_builder.py src/viewmodels/view_builder.py
git mv src/ui/view_models.py  src/viewmodels/view_models.py  2>/dev/null || mv src/ui/view_models.py  src/viewmodels/view_models.py
```

- [ ] **Step 2: Fix view_builder's own import of view_models**

In `src/viewmodels/view_builder.py`, change `from src.ui.view_models import (…)` →
`from src.viewmodels.view_models import (…)`.

- [ ] **Step 3: Repoint every external importer**

Update these (verified list) from `src.ui.view_builder` / `src.ui.view_models` to
`src.viewmodels.view_builder` / `src.viewmodels.view_models`:
- `src/command_handler.py:13`
- `src/combat.py:7`
- `src/game_engine.py:31`
- `src/commands/navigation.py:18`
- `src/commands/items.py:18`

Then re-grep for any remaining/unlisted importers (panels, textual_ui, tests) and fix them too:
```bash
grep -rn "src\.ui\.view_builder\|src\.ui\.view_models" src/ tests/
```
Update each hit; the grep must come back empty.

- [ ] **Step 4: Verify (fully mine)**

```bash
source venv/bin/activate
grep -rn "src\.ui\.view_builder\|src\.ui\.view_models" src/ tests/ || echo "NO OLD DTO IMPORTS"
python -m pytest 2>&1 | tail -3
python -c "import main; print('IMPORT main OK')"
python -m engine.validate data 2>&1 | tail -1
python - <<'EOF'
from engine.api import GameSession
import src.viewmodels.view_builder as vb
s = GameSession(); s.new_game("T","guardian")
w = s.engine.cmd_handler.world
fn = getattr(vb.ViewBuilder, "build_room_view", None) or vb.build_room_view
for rid in ("home_grove","var_dungeon","core"):
    assert fn(w, rid); 
print("VIEW_BUILDER (relocated) OK"); s.close()
EOF
```
Expected: `NO OLD DTO IMPORTS`; suite green; `IMPORT main OK`; validate OK; `VIEW_BUILDER (relocated) OK`.

- [ ] **Step 5: Commit (propose)**

```bash
git add src/viewmodels/ src/ui/ src/command_handler.py src/combat.py src/game_engine.py \
        src/commands/navigation.py src/commands/items.py
git commit -m "refactor(arch): relocate DTO layer to src/viewmodels (strangler A)

view_builder + view_models are backend serialization (the engine + command_handler + combat
call them; the UI only renders emitted dicts). Moved out of src/ui/ into src/viewmodels/ so
the dependency direction is honest: frontend depends on backend DTOs, never the reverse.
Pure import moves; no behavior change."
```

---

## Self-Review

**Spec coverage:** Phase 1 inversion (T1: import drop, inject, main(ui), composition root) +
split verification (headless mine / live yours). Phase 2 relocation (T2: move + repoint all
importers + re-grep). All spec points covered.

**Placeholder scan:** none — every step shows final code/commands. Step 6 is an explicit
human-verify handoff, not a placeholder.

**Consistency:** `main(ui)` signature matches root `main.py` call; `self.ui = ui`; backend
Textual-free assertion in Step 5; DTO import paths consistent (`src.viewmodels.*`).
