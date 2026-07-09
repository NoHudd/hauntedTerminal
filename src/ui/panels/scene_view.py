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
