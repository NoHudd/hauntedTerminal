# Scene View Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pixel-art explore scene — layout restructure + PNG→terminal sprite pipeline with placeholder fallback + explore-mode SceneView replacing the room/entity strips.

**Architecture:** Compositing happens at the **PIL Image level** (paste sprite PNGs onto a backdrop image with alpha, at slot positions), then the merged image is converted ONCE to a Rich renderable via `rich-pixels` half-blocks. `src/scene/` holds the pure pieces (SpriteStore, compositor) — no Textual imports — so they unit-test headlessly. One new widget `SceneView` renders the result and owns the small-terminal collapse.

**Tech Stack:** Python, Pillow (image compositing), rich-pixels (image → half-block renderable), Textual 0.47.1 (pinned), pytest.

## Global Constraints

- `textual==0.47.1` pin must NOT change; `rich>=13.3.3` floor must NOT change.
- No game-logic changes: `src/commands/`, `src/combat.py`, `src/game_world.py` behavior untouched (only additive DTO fields in viewmodels).
- Asset convention (from spec): `assets/sprites/{classes,enemies,npcs,backdrops,backdrops/rooms,ui}/<id>.png`. Missing PNG → generated placeholder, never a crash.
- `src/` is outside mypy/ruff scope — match existing untyped-but-annotated style of `src/viewmodels/`.
- User runs all git commits — commit steps below are COMMANDS TO PROPOSE, never run `git commit` yourself.
- Run tests as `python -m pytest` inside `venv` (bare `pytest` fails: `No module named 'src'`).

## File map

| File | Role |
|---|---|
| `requirements.txt` (modify) | + `rich-pixels>=2.2`, `Pillow>=10` |
| `assets/sprites/…` (create dirs) | PNG drop zones + `README.md` for artists |
| `src/scene/__init__.py` (create) | package marker |
| `src/scene/sprite_store.py` (create) | PNG load / placeholder gen / cache / backdrop resolution |
| `src/scene/compositor.py` (create) | pure: backdrop + placed sprites → merged PIL image + caption slots |
| `src/ui/panels/scene_view.py` (create) | SceneView widget (explore mode, collapse mode) |
| `src/viewmodels/view_models.py` (modify) | `RoomView` += `id`, `zone`, `enemy_ids`, `npc_ids` |
| `src/viewmodels/view_builder.py` (modify) | fill the new fields |
| `src/ui/textual_ui.py` (modify) | layout swap: SceneView in, strips out; re-point 5 call sites |
| `src/ui/ui.css` (modify) | scene sizing, slimmer sidebar, intro-mode rules |
| Delete: `src/ui/panels/room_strip.py`, `entity_strip.py` | replaced by SceneView (collapse mode covers their job) |
| `tests/test_sprite_store.py`, `tests/test_compositor.py`, `tests/test_room_view_ids.py` (create) | unit tests |

---

### Task 1: Dependencies + compatibility spike

**Files:**
- Modify: `requirements.txt`
- Create: `assets/sprites/` directory tree

**Interfaces:**
- Produces: importable `rich_pixels.Pixels` + `PIL.Image` inside the project venv; `assets/sprites/{classes,enemies,npcs,backdrops,backdrops/rooms,ui}/` dirs exist.

- [ ] **Step 1: Install candidates in venv and spike compat with pinned rich/textual**

```bash
source venv/bin/activate
pip install "rich-pixels>=2.2" "Pillow>=10"
pip check
python -c "
from PIL import Image
from rich_pixels import Pixels
from rich.console import Console
img = Image.new('RGBA', (8, 8), (255, 0, 0, 255))
img.save('/tmp/spike.png')
p = Pixels.from_image_path('/tmp/spike.png')
Console().print(p)
import rich, textual
print('rich', rich.__version__, 'textual', textual.__version__)
"
```
Expected: red half-block square prints; `pip check` reports no broken requirements; textual still 0.47.1.
**If `pip check` fails or rich got upgraded past what textual 0.47.1 tolerates:** pin `rich-pixels==2.2.0` (older, rich>=12 compatible) and retry. If still broken, STOP — the spec's fallback (in-house ~80-line renderer) becomes a plan change; ask the user.

- [ ] **Step 2: Record deps**

Append to `requirements.txt` under the Textual block:

```
# Scene view (pixel-art sprites rendered as half-blocks) — docs/SCENE_VIEW_SPEC.md
rich-pixels>=2.2
Pillow>=10
```

- [ ] **Step 3: Create asset tree + artist README**

```bash
mkdir -p assets/sprites/classes assets/sprites/enemies assets/sprites/npcs \
         assets/sprites/backdrops/rooms assets/sprites/ui
```

Create `assets/sprites/README.md`:

```markdown
# Sprite assets

Drop PNGs here; the game picks them up by filename — no code changes.

| Folder | Filename | Example |
|---|---|---|
| `classes/` | `<class_id>.png` | `guardian.png` |
| `enemies/` | `<enemy_id>.png` (ids keep dots) | `corrupt_process.bin.png` |
| `npcs/` | `<npc_id>.png` | `oracle.db.png` |
| `backdrops/` | `<zone>.png` | `dangerous.png` |
| `backdrops/rooms/` | `<room_id>.png` (overrides the zone backdrop) | `var_dungeon.png` |
| `ui/` | menu art | `logo.png`, `class_guardian.png`, `difficulty_easy.png` |

Guidelines: RGBA PNG, transparent background for characters. Terminal cells are
1 px wide × 2 px tall, so art displays at half its pixel height in rows.
Characters: ~24×24 px. Backdrops: ~100×36 px (they get resized to fit).
Missing files are fine — the game draws a colored placeholder until art exists.
```

- [ ] **Step 4: Verify game still boots headless**

Run: `python -c "import main"`
Expected: no output, exit 0.

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add requirements.txt assets/
git commit -m "chore(scene): add rich-pixels + Pillow deps and sprite asset tree"
```

---

### Task 2: SpriteStore — PNG loading + placeholder fallback + cache

**Files:**
- Create: `src/scene/__init__.py` (empty)
- Create: `src/scene/sprite_store.py`
- Test: `tests/test_sprite_store.py`

**Interfaces:**
- Produces:
  - `SpriteStore(assets_root: Path = Path("assets/sprites"))`
  - `SpriteStore.get_sprite(kind: str, entity_id: str, max_w: int, max_h: int) -> PIL.Image.Image` — RGBA, fits within box, aspect kept; placeholder when no PNG.
  - `SpriteStore.has_art(kind: str, entity_id: str) -> bool`
  - module fn `to_renderable(img: PIL.Image.Image) -> rich_pixels.Pixels`
- `kind` ∈ `{"classes", "enemies", "npcs", "ui"}` (backdrops arrive in Task 3).

- [ ] **Step 1: Write the failing tests**

`tests/test_sprite_store.py`:

```python
"""SpriteStore: PNG resolution, placeholder fallback, caching."""
from pathlib import Path

from PIL import Image

from src.scene.sprite_store import SpriteStore, to_renderable


def _make_store(tmp_path: Path) -> SpriteStore:
    for sub in ("classes", "enemies", "npcs", "ui"):
        (tmp_path / sub).mkdir()
    return SpriteStore(assets_root=tmp_path)


def test_loads_existing_png(tmp_path):
    store = _make_store(tmp_path)  # creates the kind dirs first
    img = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
    img.save(tmp_path / "enemies" / "corrupt_process.bin.png")
    sprite = store.get_sprite("enemies", "corrupt_process.bin", 24, 24)
    assert sprite.size[0] <= 24 and sprite.size[1] <= 24
    assert store.has_art("enemies", "corrupt_process.bin")


def test_missing_png_returns_placeholder(tmp_path):
    store = _make_store(tmp_path)
    sprite = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    assert sprite.size == (24, 24)
    assert not store.has_art("enemies", "ghost.tmp")


def test_placeholder_deterministic_and_distinct(tmp_path):
    store = _make_store(tmp_path)
    a1 = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    a2 = SpriteStore(assets_root=tmp_path).get_sprite("enemies", "ghost.tmp", 24, 24)
    b = store.get_sprite("enemies", "other.bin", 24, 24)
    assert list(a1.getdata()) == list(a2.getdata())      # same id → same pixels
    assert list(a1.getdata()) != list(b.getdata())        # different id → different tint


def test_oversized_png_is_scaled_down(tmp_path):
    store = _make_store(tmp_path)  # creates the kind dirs first
    Image.new("RGBA", (64, 32), (0, 0, 255, 255)).save(tmp_path / "npcs" / "oracle.db.png")
    sprite = store.get_sprite("npcs", "oracle.db", 20, 20)
    assert sprite.size == (20, 10)  # aspect kept, fits box


def test_cache_returns_same_object(tmp_path):
    store = _make_store(tmp_path)
    s1 = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    s2 = store.get_sprite("enemies", "ghost.tmp", 24, 24)
    assert s1 is s2


def test_to_renderable_produces_pixels(tmp_path):
    store = _make_store(tmp_path)
    sprite = store.get_sprite("enemies", "ghost.tmp", 8, 8)
    from rich_pixels import Pixels
    assert isinstance(to_renderable(sprite), Pixels)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sprite_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.scene'`.

- [ ] **Step 3: Implement**

`src/scene/__init__.py`: empty file.

`src/scene/sprite_store.py`:

```python
"""
SpriteStore — resolves entity ids to PIL images.

Convention: assets/sprites/<kind>/<entity_id>.png. Missing art falls back to a
deterministic generated placeholder (tinted block + initial) so every entity
renders from day one. Pure PIL — no Textual imports (headless-testable).
"""
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw
from rich_pixels import Pixels

_PLACEHOLDER_ALPHA = 230


def to_renderable(img: Image.Image) -> Pixels:
    """Convert a PIL image to a Rich renderable (2 px per terminal cell)."""
    return Pixels.from_image(img)


def _placeholder_color(entity_id: str) -> tuple[int, int, int]:
    """Deterministic mid-brightness tint from the id hash."""
    digest = hashlib.md5(entity_id.encode()).digest()
    # Keep channels in 60..200 so it's visible on dark and light themes
    return tuple(60 + (b % 141) for b in digest[:3])


def _make_placeholder(entity_id: str, w: int, h: int) -> Image.Image:
    color = _placeholder_color(entity_id)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled block with a 1px darker border — obvious "art goes here"
    dark = tuple(max(0, c - 50) for c in color)
    draw.rectangle([1, 1, w - 2, h - 2], fill=(*color, _PLACEHOLDER_ALPHA), outline=(*dark, 255))
    initial = (entity_id[:1] or "?").upper()
    draw.text((w // 2 - 3, h // 2 - 5), initial, fill=(*dark, 255))
    return img


class SpriteStore:
    """Loads and caches sprites; generates placeholders for missing art."""

    def __init__(self, assets_root: Path = Path("assets/sprites")):
        self._root = Path(assets_root)
        self._cache: dict[tuple, Image.Image] = {}

    def _png_path(self, kind: str, entity_id: str) -> Path:
        return self._root / kind / f"{entity_id}.png"

    def has_art(self, kind: str, entity_id: str) -> bool:
        return self._png_path(kind, entity_id).is_file()

    def get_sprite(self, kind: str, entity_id: str, max_w: int, max_h: int) -> Image.Image:
        key = (kind, entity_id, max_w, max_h)
        if key in self._cache:
            return self._cache[key]

        path = self._png_path(kind, entity_id)
        if path.is_file():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_w, max_h), Image.NEAREST)  # pixel art: no smoothing
        else:
            img = _make_placeholder(entity_id, max_w, max_h)

        self._cache[key] = img
        return img
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sprite_store.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add src/scene/ tests/test_sprite_store.py
git commit -m "feat(scene): SpriteStore — PNG resolution with deterministic placeholder fallback"
```

---

### Task 3: Backdrop resolution (room override → zone → generated)

**Files:**
- Modify: `src/scene/sprite_store.py`
- Test: `tests/test_sprite_store.py` (append)

**Interfaces:**
- Produces: `SpriteStore.get_backdrop(room_id: str, zone: str, w: int, h: int) -> PIL.Image.Image` — exact size `(w, h)` RGBA, resolution order `backdrops/rooms/<room_id>.png` → `backdrops/<zone>.png` → generated zone-tinted gradient.

- [ ] **Step 1: Write the failing tests (append to `tests/test_sprite_store.py`)**

```python
def _make_backdrop_store(tmp_path):
    (tmp_path / "backdrops" / "rooms").mkdir(parents=True)
    return SpriteStore(assets_root=tmp_path)


def test_backdrop_room_override_beats_zone(tmp_path):
    store = _make_backdrop_store(tmp_path)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(tmp_path / "backdrops" / "dangerous.png")
    Image.new("RGBA", (10, 10), (0, 0, 255, 255)).save(tmp_path / "backdrops" / "rooms" / "var_dungeon.png")
    bd = store.get_backdrop("var_dungeon", "dangerous", 40, 20)
    assert bd.size == (40, 20)
    assert bd.getpixel((20, 10))[2] > bd.getpixel((20, 10))[0]  # blue (room) won


def test_backdrop_zone_fallback(tmp_path):
    store = _make_backdrop_store(tmp_path)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(tmp_path / "backdrops" / "dangerous.png")
    bd = store.get_backdrop("no_such_room", "dangerous", 40, 20)
    assert bd.getpixel((20, 10))[0] == 255  # red (zone) used


def test_backdrop_generated_when_no_art(tmp_path):
    store = _make_backdrop_store(tmp_path)
    bd = store.get_backdrop("mystery", "quantum", 40, 20)
    assert bd.size == (40, 20)
    # deterministic per zone
    bd2 = SpriteStore(assets_root=tmp_path).get_backdrop("mystery", "quantum", 40, 20)
    assert list(bd.getdata()) == list(bd2.getdata())
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_sprite_store.py -v -k backdrop`
Expected: FAIL — `AttributeError: 'SpriteStore' object has no attribute 'get_backdrop'`.

- [ ] **Step 3: Implement (append to `SpriteStore` in `src/scene/sprite_store.py`)**

```python
    def get_backdrop(self, room_id: str, zone: str, w: int, h: int) -> Image.Image:
        key = ("backdrop", room_id, zone, w, h)
        if key in self._cache:
            return self._cache[key]

        room_png = self._root / "backdrops" / "rooms" / f"{room_id}.png"
        zone_png = self._root / "backdrops" / f"{zone}.png"
        if room_png.is_file():
            img = Image.open(room_png).convert("RGBA").resize((w, h), Image.NEAREST)
        elif zone_png.is_file():
            img = Image.open(zone_png).convert("RGBA").resize((w, h), Image.NEAREST)
        else:
            img = self._generated_backdrop(zone, w, h)

        self._cache[key] = img
        return img

    @staticmethod
    def _generated_backdrop(zone: str, w: int, h: int) -> Image.Image:
        """Dim vertical gradient tinted by zone hash — dark enough to sit behind sprites."""
        base = _placeholder_color(f"zone:{zone}")
        img = Image.new("RGBA", (w, h))
        px = img.load()
        for y in range(h):
            fade = 0.25 + 0.35 * (y / max(1, h - 1))   # darker sky, lighter floor
            row = tuple(int(c * fade) for c in base)
            for x in range(w):
                px[x, y] = (*row, 255)
        return img
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_sprite_store.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add src/scene/sprite_store.py tests/test_sprite_store.py
git commit -m "feat(scene): backdrop resolution — room override, zone art, generated gradient"
```

---

### Task 4: Compositor — pure scene assembly

**Files:**
- Create: `src/scene/compositor.py`
- Test: `tests/test_compositor.py`

**Interfaces:**
- Consumes: PIL images from `SpriteStore` (Tasks 2–3).
- Produces:
  - `@dataclass(frozen=True) Placed: image: Image.Image; name: str; kind: str` (`kind` ∈ `"npc" | "enemy"`)
  - `compose_explore(backdrop: Image.Image, entities: list[Placed]) -> tuple[Image.Image, str]` — merged image (same size as backdrop, sprites bottom-aligned: NPCs on left half, enemies on right half, ≤3 each) + a Rich-markup caption line naming who's present in slot order (empty string when no entities).

- [ ] **Step 1: Write the failing tests**

`tests/test_compositor.py`:

```python
"""Compositor: pure image assembly for the explore scene."""
from PIL import Image

from src.scene.compositor import Placed, compose_explore


def _sprite(color):
    return Image.new("RGBA", (10, 10), color)


def _backdrop():
    return Image.new("RGBA", (100, 30), (5, 5, 5, 255))


def test_empty_room_returns_backdrop_and_no_caption():
    bd = _backdrop()
    img, caption = compose_explore(bd, [])
    assert img.size == bd.size
    assert caption == ""


def test_npc_left_enemy_right():
    npc = Placed(_sprite((0, 255, 0, 255)), "Oracle", "npc")
    enemy = Placed(_sprite((255, 0, 0, 255)), "Daemon", "enemy")
    img, caption = compose_explore(_backdrop(), [npc, enemy])
    # green pixels only in left half, red only in right half (bottom rows)
    left = img.crop((0, 20, 50, 30))
    right = img.crop((50, 20, 100, 30))
    assert any(p[1] == 255 for p in left.getdata())
    assert not any(p[0] == 255 and p[1] == 0 for p in left.getdata())
    assert any(p[0] == 255 and p[1] == 0 for p in right.getdata())


def test_caption_names_all_entities():
    entities = [
        Placed(_sprite((0, 255, 0, 255)), "Oracle", "npc"),
        Placed(_sprite((255, 0, 0, 255)), "Daemon", "enemy"),
    ]
    _, caption = compose_explore(_backdrop(), entities)
    assert "Oracle" in caption and "Daemon" in caption


def test_caps_at_three_per_side():
    enemies = [Placed(_sprite((255, 0, 0, 255)), f"E{i}", "enemy") for i in range(5)]
    _, caption = compose_explore(_backdrop(), enemies)
    assert caption.count("E") == 3 or "+2" in caption  # 3 drawn, overflow noted
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_compositor.py -v`
Expected: FAIL — `ModuleNotFoundError` for `src.scene.compositor`.

- [ ] **Step 3: Implement**

`src/scene/compositor.py`:

```python
"""
Compositor — pure functions that assemble the scene image.

Takes PIL images (from SpriteStore) and merges them onto a backdrop with alpha.
NPCs occupy the left half, enemies the right half, up to 3 each, bottom-aligned.
Returns the merged image plus a Rich-markup caption line. No Textual imports.
"""
from dataclasses import dataclass

from PIL import Image

MAX_PER_SIDE = 3
_FLOOR_MARGIN = 1  # px above the bottom edge


@dataclass(frozen=True)
class Placed:
    """One entity ready for placement."""
    image: Image.Image
    name: str
    kind: str  # "npc" | "enemy"


def _slot_xs(half_start: int, half_width: int, count: int) -> list[int]:
    """Center-points for `count` sprites evenly spread across one half."""
    step = half_width // (count + 1)
    return [half_start + step * (i + 1) for i in range(count)]


def compose_explore(backdrop: Image.Image, entities: list[Placed]) -> tuple[Image.Image, str]:
    img = backdrop.copy()
    w, h = img.size

    npcs = [e for e in entities if e.kind == "npc"][:MAX_PER_SIDE]
    enemies = [e for e in entities if e.kind == "enemy"][:MAX_PER_SIDE]
    overflow = len(entities) - len(npcs) - len(enemies)

    for group, half_start in ((npcs, 0), (enemies, w // 2)):
        xs = _slot_xs(half_start, w // 2, len(group))
        for placed, cx in zip(group, xs):
            sw, sh = placed.image.size
            x = max(0, min(w - sw, cx - sw // 2))
            y = max(0, h - sh - _FLOOR_MARGIN)
            img.paste(placed.image, (x, y), placed.image)

    chips = [f"[bold magenta]👤 {e.name}[/bold magenta]" for e in npcs]
    chips += [f"[bold red]💀 {e.name}[/bold red]" for e in enemies]
    if overflow > 0:
        chips.append(f"[dim]+{overflow} more[/dim]")
    caption = "   ".join(chips)
    return img, caption
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_compositor.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add src/scene/compositor.py tests/test_compositor.py
git commit -m "feat(scene): compositor — pure explore-scene assembly with slotting + caption"
```

---

### Task 5: RoomView DTO gap — ids + zone for sprite lookup

**Files:**
- Modify: `src/viewmodels/view_models.py:59-69` (RoomView)
- Modify: `src/viewmodels/view_builder.py:104-162` (build_room_view)
- Test: `tests/test_room_view_ids.py`

**Interfaces:**
- Produces: `RoomView` gains `id: str = ""`, `zone: str = ""`, `enemy_ids: List[str]`, `npc_ids: List[str]` (all defaulted — old constructors keep working). `build_room_view` fills them; `enemy_ids[i]` pairs with `enemies[i]` (same order), likewise npcs.

- [ ] **Step 1: Write the failing test**

`tests/test_room_view_ids.py`:

```python
"""RoomView carries entity ids + zone so the scene can resolve sprite files."""
from src.viewmodels.view_builder import ViewBuilder


class _FakeRoom:
    name = "The Graveyard"
    description = "Foggy."
    exits = []
    zone = "safe"


class _FakeEnemy:
    def __init__(self, name):
        self.name = name


class _FakeWorld:
    rooms = {"home_grove": _FakeRoom()}
    enemies = {"lost_inode.tmp": _FakeEnemy("Lost Inode")}
    npcs = {"oracle.db": {"name": "The Oracle"}}

    def get_enemies_in_room(self, room_id):
        return ["lost_inode.tmp"]

    def get_npcs_in_room(self, room_id):
        return ["oracle.db"]


def test_room_view_includes_ids_and_zone():
    view = ViewBuilder.build_room_view(_FakeWorld(), "home_grove")
    assert view.id == "home_grove"
    assert view.zone == "safe"
    assert view.enemy_ids == ["lost_inode.tmp"]
    assert view.npc_ids == ["oracle.db"]
    assert view.enemies == ["Lost Inode"]      # names still intact, same order
    assert view.npcs == ["The Oracle"]
    d = view.to_dict()
    assert d["enemy_ids"] == ["lost_inode.tmp"] and d["zone"] == "safe"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_room_view_ids.py -v`
Expected: FAIL — `AttributeError: 'RoomView' object has no attribute 'id'` (or zone).

- [ ] **Step 3: Implement**

In `src/viewmodels/view_models.py`, replace the `RoomView` field block:

```python
@dataclass(frozen=True)
class RoomView:
    """Room display data."""
    name: str
    description: str
    id: str = ""
    zone: str = ""
    exits: List[str] = field(default_factory=list)
    enemies: List[str] = field(default_factory=list)      # display names
    npcs: List[str] = field(default_factory=list)         # display names
    enemy_ids: List[str] = field(default_factory=list)    # same order as enemies
    npc_ids: List[str] = field(default_factory=list)      # same order as npcs
```
(`to_dict` already uses `asdict` — no change.)

In `src/viewmodels/view_builder.py` `build_room_view`, keep name/exit logic; rebuild the
enemy/npc blocks so names and ids stay paired, and pass the new fields:

```python
            # Enemies: keep (id, name) pairs so the scene can resolve sprites
            enemy_ids = [
                eid for eid in getattr(world, 'get_enemies_in_room', lambda r: [])(room_id)
                if eid in getattr(world, 'enemies', {})
            ]
            enemy_names = [getattr(world.enemies[eid], 'name', eid) for eid in enemy_ids]

            npc_ids = [
                nid for nid in getattr(world, 'get_npcs_in_room', lambda r: [])(room_id)
                if nid in getattr(world, 'npcs', {})
            ]
            npc_names = [world.npcs.get(nid, {}).get('name', nid) for nid in npc_ids]

            return RoomView(
                name=room_data.name or room_id,
                description=room_data.description or 'An unknown location.',
                id=room_id,
                zone=getattr(room_data, 'zone', '') or '',
                exits=exit_commands,
                enemies=enemy_names,
                npcs=npc_names,
                enemy_ids=enemy_ids,
                npc_ids=npc_ids,
            )
```
(The exception-path `RoomView(...)` at the bottom needs no change — new fields default.)

- [ ] **Step 4: Run new test + full suite (additive DTO change must not ripple)**

Run: `python -m pytest tests/test_room_view_ids.py -v && python -m pytest -q`
Expected: new test passes; full suite same count as before + 1.

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add src/viewmodels/ tests/test_room_view_ids.py
git commit -m "feat(viewmodels): RoomView carries id/zone/entity-ids for scene sprite lookup"
```

---

### Task 6: SceneView widget + layout restructure

**Files:**
- Create: `src/ui/panels/scene_view.py`
- Modify: `src/ui/textual_ui.py` (compose ~114-128, on_mount ~130-143, `_on_room_entered` ~279-296, plus strip call sites at ~662, ~727-728, ~922-923)
- Modify: `src/ui/ui.css`
- Delete: `src/ui/panels/room_strip.py`, `src/ui/panels/entity_strip.py`
- Modify: `src/ui/panels/__init__.py` (if it re-exports strips — check)

**Interfaces:**
- Consumes: `SpriteStore.get_sprite`, `SpriteStore.get_backdrop` (Tasks 2–3), `compose_explore`/`Placed` (Task 4), room dict with `id`/`zone`/`*_ids` (Task 5).
- Produces:
  - `SceneView(Static)` with `show_explore(room: dict) -> None`, `show_loading() -> None`.
  - Collapse behavior: below `MIN_SCENE_ROWS = 10` app rows for the scene, renders the old one-line strip text instead of art (RoomStrip/EntityStrip funeral).

- [ ] **Step 1: Implement the widget**

`src/ui/panels/scene_view.py`:

```python
"""
SceneView — the picture window. Explore mode: zone backdrop + NPC/enemy sprites.
Collapses to a one-line room strip when the terminal is too short for art.
Rendering pipeline: SpriteStore (PIL) → compositor (PIL) → rich-pixels → Rich Group.
"""
from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from src.scene.compositor import Placed, compose_explore
from src.scene.sprite_store import SpriteStore, to_renderable

MIN_SCENE_ROWS = 10        # below this, fall back to strip text
SPRITE_MAX_PX = 24         # character sprites fit a 24×24 px box


class SceneView(Static):
    """Explore-mode scene panel. Battle mode arrives in Phase 2."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._store = SpriteStore()
        self._room: dict | None = None

    # -- public API (called by TextualGameUI) --------------------------------

    def show_explore(self, room: dict) -> None:
        self._room = room
        self._render_scene()

    def show_loading(self) -> None:
        self._room = None
        self.border_title = "…"
        self.update(Text("Loading...", style="dim"))

    # -- internals ------------------------------------------------------------

    def on_resize(self) -> None:
        if self._room is not None:
            self._render_scene()

    def _render_scene(self) -> None:
        room = self._room or {}
        name = room.get("name", "")
        exits = room.get("exits", [])
        self.border_title = f"🏠 {name}"
        self.border_subtitle = "  ".join(f"→ {e}" for e in exits) or "no exits"

        w_cells = max(20, self.content_size.width or 60)
        h_rows = self.content_size.height or 0
        if h_rows < MIN_SCENE_ROWS:
            self.update(self._strip_fallback(room))
            return

        # 1 cell = 1 px wide × 2 px tall; reserve 1 row for the caption line
        img_w, img_h = w_cells, (h_rows - 1) * 2
        backdrop = self._store.get_backdrop(room.get("id", ""), room.get("zone", ""), img_w, img_h)

        entities = [
            Placed(self._store.get_sprite("npcs", nid, SPRITE_MAX_PX, SPRITE_MAX_PX), nname, "npc")
            for nid, nname in zip(room.get("npc_ids", []), room.get("npcs", []))
        ] + [
            Placed(self._store.get_sprite("enemies", eid, SPRITE_MAX_PX, SPRITE_MAX_PX), ename, "enemy")
            for eid, ename in zip(room.get("enemy_ids", []), room.get("enemies", []))
        ]

        img, caption = compose_explore(backdrop, entities)
        parts = [to_renderable(img)]
        parts.append(Text.from_markup(caption) if caption else Text(""))
        self.update(Group(*parts))

    @staticmethod
    def _strip_fallback(room: dict) -> Text:
        """One-line summary for short terminals (the old strips' job)."""
        bits = []
        for n in room.get("npcs", []):
            bits.append(f"[bold magenta]👤 {n}[/bold magenta]")
        for n in room.get("enemies", []):
            bits.append(f"[bold red]💀 {n}[/bold red]")
        present = ("   " + "  ".join(bits)) if bits else ""
        return Text.from_markup(f"[dim]scene needs a taller terminal[/dim]{present}")
```

- [ ] **Step 2: Swap the layout in `src/ui/textual_ui.py`**

Imports: remove `RoomStrip`/`EntityStrip` imports, add:
```python
from src.ui.panels.scene_view import SceneView
```

`compose()` — replace the two strip yields:
```python
        with Horizontal():
            with Vertical(id="main-area"):
                yield SceneView(id="scene-view")
                with VerticalScroll(id="output-panel"):
                    yield Static(self.output_content, id="output-display")
            with Container(id="sidebar"):
                yield InventoryPanel(id="inventory-panel")
                yield StatsPanel(id="stats-panel")
                yield CombatPanel(id="combat-panel")
```

`on_mount()` — replace the strip lookups:
```python
            self._scene_view = self.query_one("#scene-view", SceneView)
```

`_on_room_entered` — replace both strip refresh lines with:
```python
            self._scene_view.show_explore(self._room_view)
```

Other call sites (grep `_room_strip`/`_entity_strip`; currently ~662, ~727-728, ~922-923):
- Sites that pass a fresh room view dict → `self._scene_view.show_explore(<that dict>)`.
- The `refresh_room("Loading...", [])` + `refresh_entities([], [])` pair → `self._scene_view.show_loading()`.
Then delete the strip files and any `__init__.py` re-exports:
```bash
git rm src/ui/panels/room_strip.py src/ui/panels/entity_strip.py
grep -rn "RoomStrip\|EntityStrip\|room_strip\|entity_strip" src/ tests/
```
Expected grep: no hits left.

- [ ] **Step 3: CSS**

In `src/ui/ui.css` — replace the strip block and adjust proportions:

```css
/* =============================================================================
   SCENE VIEW (replaces room/entity strips) — docs/SCENE_VIEW_SPEC.md
   ============================================================================= */

#scene-view {
    height: 45%;
    min-height: 3;
    border: round $primary;
    padding: 0 1;
}
```
And update every `.intro-mode` strip rule:
```css
.intro-mode #scene-view { display: none; }
```
(remove the `#room-strip` / `#entity-strip` intro rules). Keep `#main-area` at `3fr` /
sidebar `1fr` — sidebar already slims visually because the combat panel goes in Phase 2;
do NOT resize the sidebar in this phase.

- [ ] **Step 4: Verify — suite + boot + manual smoke**

```bash
python -m pytest -q
python -c "import main"
python -m engine.validate data
```
Expected: suite green (same count), import OK, validate OK.
Then ask the user to run `python main.py` and check: title intro unaffected; entering a
room shows backdrop + placeholder blocks for NPC/enemies; caption names them; shrinking
the terminal window collapses the scene to the one-line fallback; log viewer +
save/load still fine.

- [ ] **Step 5: Commit (propose to user — do not run)**

```bash
git add -A src/ui/ src/scene/
git commit -m "feat(ui): SceneView explore scene replaces room/entity strips"
```

---

### Task 7: Full gate + doc touch

**Files:**
- Modify: `CLAUDE.md` (repo tree snippet: add `assets/` + `src/scene/` lines)

- [ ] **Step 1: Full quality gate**

```bash
make check
```
Expected: ruff + mypy (engine) + pytest + validate all green. (`src/scene/` is inside
`src/`, so outside mypy/ruff scope — expected.)

- [ ] **Step 2: Update CLAUDE.md repo map**

In the "Where things live" tree, after `data/`:
```
assets/        # pixel-art PNGs (sprites, backdrops) — assets/sprites/README.md
```
and under the `src/` lines:
```
  scene/       # PNG→terminal sprite pipeline (SpriteStore, compositor)
```

- [ ] **Step 3: Commit (propose to user — do not run)**

```bash
git add CLAUDE.md
git commit -m "docs: note assets/ and src/scene/ in repo map"
```
(Note: root CLAUDE.md is git-excluded via .git/info/exclude — if so, this commit is a
no-op; skip it.)
