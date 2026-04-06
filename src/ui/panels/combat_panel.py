"""
CombatPanel widget — sidebar panel showing enemy HP bars during combat,
or a dim "No enemies" message while exploring.
"""

from textual.widgets import Static

from src.ui.panels import create_health_bar


class CombatPanel(Static):
    """Sidebar panel that shows combat status or idle state."""

    def show_idle(self) -> None:
        """Render exploration (no combat) state."""
        self.update("[dim]No enemies nearby[/dim]")

    def refresh_combat(self, combat_view: dict, player_view: dict) -> None:
        """Render active combat with enemy name + HP bar."""
        if not combat_view:
            self.show_idle()
            return

        enemy_name = combat_view.get('enemy_name', 'Unknown Enemy')
        enemy_health = combat_view.get('enemy_health', 0)
        enemy_max_health = combat_view.get('enemy_max_health', 100)

        player_health = combat_view.get('player_health', 0)
        player_max_health = combat_view.get('player_max_health', 100)
        player_name = player_view.get('player_name', 'You') if player_view else 'You'

        enemy_bar = create_health_bar(enemy_health, enemy_max_health, 12)
        player_bar = create_health_bar(player_health, player_max_health, 12)

        lines = [
            f"[bold red]💀 {enemy_name.upper()}[/bold red]",
            f"HP: {enemy_health}/{enemy_max_health}",
            enemy_bar,
            "",
            f"[bold green]🛡️ {player_name.upper()}[/bold green]",
            f"HP: {player_health}/{player_max_health}",
            player_bar,
        ]

        self.update("\n".join(lines))
