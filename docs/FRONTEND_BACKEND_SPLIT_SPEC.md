# Frontend / Backend Split — Spec (Strangler A, capstone)

**Date:** 2026-07-08
**Status:** Approved direction, not yet implemented.
**Why:** Final strangler step (REWRITE_PLAN Phase 4b, reframed). Make the core a clean
**backend** the **frontend** depends on — never the reverse — so a different frontend
(web / Discord) could sit on the same game logic later. C (safety) + B (typing) are done.

## Plain summary

Today the backend *owns* the frontend: `ImprovedGameEngine` imports and constructs
`TextualGameUI`, so `import game_engine` drags in Textual. We flip that: `main.py` becomes the
composition root that builds the TUI and injects it; the backend depends only on the
`UIProtocol` abstraction. Then we relocate the DTO layer (`view_builder`/`view_models`) out of
`src/ui/` (it's backend serialization, not frontend) so the dependency direction is honest.

## What's already clean (don't touch)

- **Event bus** carries all messages both ways (input UI→bus→engine; state engine→bus→UI).
- **`GameSession`** (`engine/api.py`) is the backend API and already injects a `HeadlessUI`
  via the existing `ui=` seam — proof the engine runs frontend-free.
- **Domain is Textual-free:** `command_handler`, `combat`, `game_output`, `engine/`,
  `view_builder`, `view_models` import no Textual (verified). The **only** Textual pull is
  `game_engine.py:25`.
- **`view_builder` is backend code:** the engine (and command_handler/combat/commands) call it
  to turn state into DTOs; the UI only renders the emitted dicts. It stays a **separate** pure
  unit (testable, single-responsibility) — we relocate it, we do **not** fold it into the engine.

## Constraints (global)

- **Zero gameplay change.** Same game, same screen.
- Backend (`src/` domain + `engine/`) must not import the concrete `TextualGameUI` after this.
- `sim/`+`src/` outside mypy/ruff; `engine/` mypy-strict.
- Gate: `python -m pytest` + `python -m engine.validate data` + `python -c "import main"` +
  the placement + `build_room_view` smokes. **Phase 1 additionally needs a live-TUI check that
  only the user can do** (see Verification).
- User does own commits (propose only). One commit per phase.

---

## Phase 1 — Ownership inversion (the actual split; USER verifies)

Make the backend stop constructing the concrete frontend; move that choice to `main.py`.

**`src/game_engine.py`:**
- Remove the top-level import `from src.ui.textual_ui import TextualGameUI` (line 25). Keep the
  `UIProtocol` / `UIError` imports (line 26) — those are the abstraction the backend *should*
  depend on. Keep the `ViewBuilder` import (line 31) for now — it's backend, relocated in Phase 2.
- `ImprovedGameEngine.__init__(..., ui)`: change `self.ui = ui or TextualGameUI()` (line 64) to
  `self.ui = ui` — the UI is **always injected**, never defaulted inside the backend.
- Extract the logging setup in `main()` (926-941) into a small `setup_logging()` function.
- Change `main()` → `main(ui)`: `setup_logging(); engine = ImprovedGameEngine(ui=ui); engine.run()`
  (line 942's no-arg `ImprovedGameEngine()` becomes `ImprovedGameEngine(ui=ui)`).

**`main.py` (root) — the composition root:**
```python
from src.ui.textual_ui import TextualGameUI   # frontend chosen HERE
from src.game_engine import main
...
main(TextualGameUI())
```
(Keep the existing dir-creation / debug.log handling.)

**Result:** `import src.game_engine` no longer pulls Textual; `GameSession` (HeadlessUI) and the
tests are unaffected (they already inject a UI); only `main.py` knows the concrete frontend.

### Phase 1 verification (split responsibility)
- **I verify (headless):** `python -m pytest` green; `python -m engine.validate data` OK;
  `python -c "import src.game_engine; import sys; assert 'textual' not in sys.modules"` proves
  importing the backend does **not** load Textual; `python -c "import main"` still wires; the
  placement + `build_room_view` smokes pass; a `GameSession` scripted run plays.
- **You verify (live — I cannot):** `python main.py` → the game launches, class-select renders,
  you play a few commands (move, look, a fight), panels update, save/quit works. If it launches
  and plays like before, Phase 1 is good. If not, report what broke and I fix before Phase 2.

**Commit only after your live check passes.**

---

## Phase 2 — Relocate the DTO layer (mechanical; I verify)

Move the backend serialization layer out of the frontend directory.

- Create `src/viewmodels/` (package) and move:
  - `src/ui/view_builder.py` → `src/viewmodels/view_builder.py`
  - `src/ui/view_models.py` → `src/viewmodels/view_models.py`
- Update **every** importer (verified list; re-grep to be exact):
  `src/command_handler.py:13`, `src/combat.py:7`, `src/game_engine.py:31`,
  `src/commands/navigation.py:18`, `src/commands/items.py:18`, `view_builder`'s own
  `from src.ui.view_models import …`, plus any `src/ui/panels/*` / `src/ui/textual_ui.py` /
  `tests/*` that import `view_models`/`view_builder`.
- Dependency direction after: frontend (`src/ui/`) imports DTOs from `src/viewmodels/`
  (backend), never the reverse.

### Phase 2 verification (fully mine)
`python -m pytest` green; `python -m engine.validate data` OK; `python -c "import main"` clean;
placement + `build_room_view` smokes pass; a grep confirms no `from src.ui.view_builder` /
`from src.ui.view_models` remain. (No live-TUI check needed — pure import moves.)

---

## Ordering note

Phase 1 (inversion) lands first per your call — it's the meaningful split and small (drop one
import, move construction to `main.py`), verified by your one live play. Phase 2 (relocation) is
cosmetic tidying that I fully verify. Doing 1 before 2 is fine: `view_builder` is Textual-clean,
so the inversion de-Textuals the backend even while `view_builder` still lives in `src/ui/`.

## Non-goals

- No reactive Textual `reactive`-binding rewrite (optional polish; not needed for the split).
- No folding `view_builder` into the engine (keeps it testable + single-responsibility).
- No change to combat, content, saves, or the event-bus protocol.
- No second frontend built now — just making one *possible* without engine changes.
