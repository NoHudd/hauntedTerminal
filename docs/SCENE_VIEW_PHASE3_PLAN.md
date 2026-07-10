# Scene View Phase 3 (Art-Card Pickers) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full-screen horizontal art-card pickers for difficulty and class selection — ←/→ + number keys + Enter, pixel art per card with placeholder fallback.

**Architecture:** One generic `SelectionScreen(ModalScreen)` (heading + horizontal row of card widgets + hint line). textual_ui pushes it on `UI_STATE_CHANGED` → `waiting_for_difficulty` / `waiting_for_class` and pops it when the state moves on. Picking a card emits `COMMAND_ENTERED` with the card's number — **exactly what typing "1" does today, so the backend is untouched**. Card art from `assets/sprites/ui/` via the existing SpriteStore (auto-placeholder).

**Tech Stack:** Textual ModalScreen + CSS grid/horizontal layout, SpriteStore/rich-pixels, pytest.

## Global Constraints

- Zero backend change: `src/game_engine.py` selection handlers and state machine untouched. The picker is input sugar over the existing `COMMAND_ENTERED` "1"/"2"/"3" contract.
- Card ORDER must match the backend maps: class order = `load_class_data().keys()` order; difficulty order = `src.difficulty.MODES` order. Build cards FROM those sources, never hardcode order.
- Typed input still works (screen passes unhandled keys through? No — modal blocks; the number keys 1-3 ARE handled by the screen, Enter confirms; typing full words is no longer needed since the states only accept numbers anyway).
- Art keys: `ui/class_<id>.png`, `ui/difficulty_<mode>.png` (per ART_BRIEF). Placeholder fallback must render.
- Title screen: unchanged this phase (already a full-screen arrow menu); logo art slot deferred.
- User runs all git commits — propose only. Tests via `python -m pytest` in venv.

## Tasks

### Task 1: SelectionScreen widget (create `src/ui/screens/selection_screen.py`)

- `@dataclass(frozen=True) SelectionCard: command: str; title: str; subtitle: str; art_key: str; accent: str = "white"`
- `SelectionScreen(ModalScreen)`: `__init__(heading: str, cards: list[SelectionCard], on_pick: Callable[[SelectionCard], None])`
- Compose: centered Vertical → heading Static, Horizontal row of card Statics, hint Static (`←/→ choose · Enter confirm · 1-N direct`).
- Bindings: left/h = prev, right/l = next, enter = confirm, digits 1..len(cards) = pick directly.
- Selected card: CSS class `card-selected` (bright border, bold); others dim.
- Card body: `Group(to_renderable(SpriteStore.get_sprite("ui", art_key, 32, 32)), Text(title, bold+accent), Text(subtitle, dim))` centered.
- `on_pick(card)` called then screen dismissed by the CALLER (textual_ui pops on state change) — but also self-dismiss guard to avoid double-pop.
- Test `tests/test_selection_screen.py`: card dataclass, digit→index mapping helper `digit_to_index("2", n) -> 1 | None` (pure), and screen instantiates with cards.

### Task 2: Wire into textual_ui

- Card builders in `src/ui/textual_ui.py`:
  - `_difficulty_cards()` — order from `src.difficulty.MODES`; copy icon/desc from game_engine's `_DIFFICULTY_INFO` semantics (easy 🌱 forgiving / medium ⚖ intended / hard 💀 punishing); art_key `difficulty_<mode>`; commands "1"/"2"/"3" by position.
  - `_class_cards()` — order from `load_class_data().keys()`; title = class name; subtitle = short stats line from class data (hp/damage); art_key `class_<id>`; accent per class.
- `_on_ui_state_changed`: on `waiting_for_difficulty` / `waiting_for_class` → pop any open picker, push the right one; on any other state → pop picker if open. (Keep the `selection-mode` CSS toggle for name entry, which stays typed.)
- `on_pick` handler: `event_bus.emit_event(EventType.COMMAND_ENTERED, {"command": card.command, "game_state": state_manager.current_state}, "SelectionScreen")`.
- Track `self._picker: SelectionScreen | None` for pop management.
- Gate: full suite + import + manual smoke (new game → difficulty cards → class cards → name typed → game starts; invalid path impossible by construction).
