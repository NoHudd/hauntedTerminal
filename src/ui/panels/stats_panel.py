"""
StatsPanel widget — renders player stats in the sidebar.
"""

from textual.widgets import Static

from src.ui.panels import class_icon, create_health_bar


class StatsPanel(Static):
    """Sidebar panel that displays player stats."""

    def update_stats(self, player_view: dict) -> None:
        """Render exploration-mode stats from a StatsView dict."""
        if not player_view:
            return

        stats_lines = []

        player_name = player_view.get('player_name', 'Unknown')
        player_class = player_view.get('player_class', 'Unknown')
        stats_lines.append(
            f"[bold green]{class_icon(player_class)}  {player_name.upper()}[/bold green]"
        )
        stats_lines.append(f"Class: {player_class.title()}")

        level = player_view.get('level', 1)
        cycles = player_view.get('cycles', 0)
        to_next = player_view.get('cycles_to_next', 0)
        if to_next:
            stats_lines.append(f"[yellow]Lvl {level}[/] [dim]· {cycles}/{to_next} cycles[/]")
        else:
            stats_lines.append(f"[yellow]Lvl {level}[/]")

        health = player_view.get('health', 0)
        max_health = player_view.get('max_health', 100)

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

        damage = player_view.get('damage', 0)
        stats_lines.extend([
            "",
            f"[cyan]Attack: {damage}[/]",
        ])
        defense_pct = player_view.get('defense_pct', 0)
        if defense_pct:
            stats_lines.append(f"[cyan]Defense: -{defense_pct}% dmg taken[/]")

        self.update("\n".join(stats_lines))

    def refresh_combat(self, player_view: dict, combat_view: dict) -> None:
        """Render combat-mode stats."""
        if not player_view:
            return

        stats_lines = []

        player_name = player_view.get('player_name', 'Unknown')
        player_class = player_view.get('player_class', 'Unknown')
        stats_lines.append(
            f"[bold green]{class_icon(player_class)}  {player_name.upper()}[/bold green]"
        )
        stats_lines.append(f"Class: {player_class.title()}")

        level = player_view.get('level', 1)
        cycles = player_view.get('cycles', 0)
        to_next = player_view.get('cycles_to_next', 0)
        if to_next:
            stats_lines.append(f"[yellow]Lvl {level}[/] [dim]· {cycles}/{to_next} cycles[/]")
        else:
            stats_lines.append(f"[yellow]Lvl {level}[/]")

        if combat_view:
            health = combat_view.get('player_health', 0)
            max_health = combat_view.get('player_max_health', 100)

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

        base_attack = player_view.get('damage', 0)
        stats_lines.extend([
            "",
            f"[cyan]Base ATK: {base_attack}[/]",
        ])
        defense_pct = player_view.get('defense_pct', 0)
        if defense_pct:
            stats_lines.append(f"[cyan]Defense: -{defense_pct}% dmg taken[/]")

        self.update("\n".join(stats_lines))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_health_bar(self, current, maximum, color, bar_length=10) -> str:
        """Create an ASCII health bar with customizable length."""
        if maximum <= 0:
            empty_bar = "▒" * bar_length
            return f"[gray]{empty_bar}[/gray]"

        filled = int((current / maximum) * bar_length)
        empty = bar_length - filled
        bar = "█" * filled + "▒" * empty
        return f"[{color}]{bar}[/{color}]"
