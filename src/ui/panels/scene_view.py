"""
SceneView — the picture window. Explore mode: zone backdrop + NPC/enemy sprites.
Collapses to a one-line room strip when the terminal is too short for art.
Rendering pipeline: SpriteStore (PIL) → compositor (PIL) → rich-pixels → Rich Group.
"""
import time

from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from src.scene.compositor import Placed, compose_battle, compose_explore, nameplate
from src.scene.effects import (
    FLASH_SECONDS,
    LUNGE_SECONDS,
    FxState,
    approach,
    flash_on,
    lunge_offset,
)
from src.scene.sprite_store import SpriteStore, to_renderable

MIN_SCENE_ROWS = 10        # below this, fall back to strip text
SPRITE_MAX_PX = 24         # character sprites fit a 24×24 px box


class SceneView(Static):
    """Explore-mode scene panel. Battle mode arrives in Phase 2."""

    _TICK_SECONDS = 0.05   # 20 fps, but only while an effect/drain is active
    _POP_SECONDS = 0.7
    _CLASS_ICONS = {"guardian": "🛡", "weaver": "✨", "shaman": "🌿"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._store = SpriteStore()
        self._room: dict | None = None
        self._battle: dict | None = None
        self._ticker = None

    # -- public API (called by TextualGameUI) --------------------------------

    def show_explore(self, room: dict) -> None:
        self._room = room
        self._render_scene()

    def show_loading(self) -> None:
        self._room = None
        self.border_title = "…"
        self.update(Text("Loading...", style="dim"))

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
            # Render the impact frame NOW (flash on, lunge starting) — waiting for
            # the first ticker tick lands mid-blink and the hit reads as invisible.
            if kind == "damage":
                if actor == "player":
                    self._render_battle(FxState(player_dx=lunge_offset(0.01), enemy_flash=True))
                else:
                    self._render_battle(FxState(enemy_dx=lunge_offset(0.01), player_flash=True))
            else:
                self._render_battle(FxState())
            self._ensure_ticker()

    def end_battle(self) -> None:
        """Leave battle mode; restore the explore scene (COMBAT_ENDED / game over)."""
        self._stop_ticker()
        self._battle = None
        if self._room is not None:
            self._render_scene()
        else:
            self.show_loading()

    # -- battle internals -----------------------------------------------------

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
        enemy_img = self._store.get_sprite(
            "enemies", view.get("enemy_id") or view.get("enemy_name", "?"),
            SPRITE_MAX_PX, SPRITE_MAX_PX,
        )
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

    # -- internals ------------------------------------------------------------

    def on_resize(self) -> None:
        if self._battle is not None:
            self._render_battle(FxState())
        elif self._room is not None:
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
