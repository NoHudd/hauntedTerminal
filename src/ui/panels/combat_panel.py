"""
CombatPanel widget — sidebar panel showing enemy HP bars during combat,
or a dim "No enemies" message while exploring.
"""

from textual.widgets import Static

from src.ui.panels import class_icon, create_health_bar


class CombatPanel(Static):
    """Sidebar panel that shows combat status or idle state."""

    def show_idle(self) -> None:
        """Render exploration (no combat) state and clear cached combat view
        so a late damage-pop timer can't resurrect the stale panel."""
        self._last_combat_view = {}
        self._last_player_view = {}
        self._pop_text = ""
        self._pop_target = ""
        self.update("[dim]No enemies nearby[/dim]")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_combat_view: dict = {}
        self._last_player_view: dict = {}
        self._pop_text: str = ""
        self._pop_target: str = ""

    def refresh_combat(self, combat_view: dict, player_view: dict) -> None:
        """Render active combat with enemy name + HP bar."""
        if not combat_view:
            self.show_idle()
            return

        # Cache for re-render after damage pop clears.
        self._last_combat_view = combat_view
        self._last_player_view = player_view or {}

        enemy_name = combat_view.get('enemy_name', 'Unknown Enemy')
        enemy_health = combat_view.get('enemy_health', 0)
        enemy_max_health = combat_view.get('enemy_max_health', 100)

        player_health = combat_view.get('player_health', 0)
        player_max_health = combat_view.get('player_max_health', 100)
        player_name = player_view.get('player_name', 'You') if player_view else 'You'
        player_class = player_view.get('player_class', '') if player_view else ''

        enemy_bar = create_health_bar(enemy_health, enemy_max_health, 12)
        player_bar = create_health_bar(player_health, player_max_health, 12)

        lines = [
            f"[bold red]💀  {enemy_name.upper()}[/bold red]",
            f"HP: {enemy_health}/{enemy_max_health}",
            enemy_bar,
        ]
        if self._pop_text and self._pop_target == "enemy":
            lines.append(self._pop_text)
        lines.append("")
        lines.append(f"[bold green]{class_icon(player_class)}  {player_name.upper()}[/bold green]")
        lines.append(f"HP: {player_health}/{player_max_health}")
        lines.append(player_bar)
        if self._pop_text and self._pop_target == "player":
            lines.append(self._pop_text)

        self.update("\n".join(lines))

    def show_damage_pop(self, amount: int, actor: str, kind: str = "damage") -> None:
        """Show a brief floating number over the target. Caller schedules clear via timer."""
        if kind == "damage":
            # An attack pops over the victim: player attacks -> over enemy, and vice-versa.
            target = "enemy" if actor == "player" else "player"
        else:
            # A heal/buff pops over the one affected — the actor themselves — so a
            # self-heal shows "💚 +N" over the player (where they're watching HP),
            # not over the enemy.
            target = "player" if actor == "player" else "enemy"
        symbol = "-" if kind == "damage" else "+"
        color = "bold red" if kind == "damage" else "bold green"
        icon = "💥" if kind == "damage" else "💚"
        self._pop_text = f"[{color}]{icon} {symbol}{amount}[/{color}]"
        self._pop_target = target
        self.refresh_combat(self._last_combat_view, self._last_player_view)

    def clear_damage_pop(self) -> None:
        self._pop_text = ""
        self._pop_target = ""
        if self._last_combat_view:
            self.refresh_combat(self._last_combat_view, self._last_player_view)
