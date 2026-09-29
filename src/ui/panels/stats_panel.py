"""
StatsPanel widget — renders player stats in the sidebar.
"""

from __future__ import annotations

from textual.widgets import Static

from src.ui.panels import class_icon, create_health_bar
from src.viewmodels.view_models import CombatView, StatsView


class StatsPanel(Static):
    """Sidebar panel that displays player stats."""

    def update_stats(self, player_view: StatsView | None) -> None:
        """Render exploration-mode stats."""
        if player_view is None:
            return

        stats_lines = []

        player_name = player_view.player_name
        player_class = player_view.player_class
        stats_lines.append(
            f"[bold green]{class_icon(player_class)}  {player_name.upper()}[/bold green]"
        )
        stats_lines.append(f"Class: {player_class.title()}")

        level = player_view.level
        cycles = player_view.cycles
        to_next = player_view.cycles_to_next
        if to_next:
            stats_lines.append(f"[yellow]Lvl {level}[/] [dim]· {cycles}/{to_next} cycles[/]")
        else:
            stats_lines.append(f"[yellow]Lvl {level}[/]")

        health = player_view.health
        max_health = player_view.max_health

        if max_health > 0:
            health_percent = health / max_health
            health_color = (
                "red" if health_percent < 0.3 else ("yellow" if health_percent < 0.7 else "green")
            )
            health_bar = self._create_health_bar(health, max_health, health_color, bar_length=12)
            stats_lines.extend([
                "",
                f"[{health_color}]HP: {health}/{max_health}[/]",
                health_bar,
            ])

        damage = player_view.damage
        stats_lines.extend([
            "",
            f"[cyan]Attack: {damage}[/]",
        ])
        defense_pct = player_view.defense_pct
        if defense_pct:
            stats_lines.append(f"[cyan]Defense: -{defense_pct}% dmg taken[/]")

        self.update("\n".join(stats_lines))

    def refresh_combat(self, player_view: StatsView | None, combat_view: CombatView | None) -> None:
        """Render combat-mode stats."""
        if player_view is None:
            return

        stats_lines = []

        player_name = player_view.player_name
        player_class = player_view.player_class
        stats_lines.append(
            f"[bold green]{class_icon(player_class)}  {player_name.upper()}[/bold green]"
        )
        stats_lines.append(f"Class: {player_class.title()}")

        level = player_view.level
        cycles = player_view.cycles
        to_next = player_view.cycles_to_next
        if to_next:
            stats_lines.append(f"[yellow]Lvl {level}[/] [dim]· {cycles}/{to_next} cycles[/]")
        else:
            stats_lines.append(f"[yellow]Lvl {level}[/]")

        if combat_view is not None:
            health = combat_view.player_health
            max_health = combat_view.player_max_health

            if max_health > 0:
                health_percent = health / max_health
                health_color = (
                    "red" if health_percent < 0.3 else ("yellow" if health_percent < 0.7 else "green")
                )
                enhanced_health_bar = create_health_bar(health, max_health, 10)

                health_status = ""
                if health_percent <= 0.15:
                    health_status = " [red blink]CRITICAL[/red blink]"
                elif health_percent <= 0.3:
                    health_status = " [red]LOW[/red]"
                elif health_percent >= 1.0:
                    health_status = " [green]FULL[/green]"

                stats_lines.extend([
                    "",
                    f"[{health_color}]HP: {health}/{max_health}[/]{health_status}",
                    enhanced_health_bar,
                ])

        base_attack = player_view.damage
        stats_lines.extend([
            "",
            f"[cyan]Base ATK: {base_attack}[/]",
        ])
        defense_pct = player_view.defense_pct
        if defense_pct:
            stats_lines.append(f"[cyan]Defense: -{defense_pct}% dmg taken[/]")

        self.update("\n".join(stats_lines))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_health_bar(self, current: int, maximum: int, color: str, bar_length: int = 10) -> str:
        """Create an ASCII health bar with customizable length."""
        if maximum <= 0:
            empty_bar = "▒" * bar_length
            return f"[gray]{empty_bar}[/gray]"

        filled = int((current / maximum) * bar_length)
        empty = bar_length - filled
        bar = "█" * filled + "▒" * empty
        return f"[{color}]{bar}[/{color}]"
