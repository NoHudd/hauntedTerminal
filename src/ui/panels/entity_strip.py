"""
EntityStrip widget — always-visible bar showing entities present in the current room.
Collapses (display: none) when no entities are present.
"""

from textual.widgets import Static


class EntityStrip(Static):
    """Strip below RoomStrip that shows NPCs and enemies present in the room."""

    def refresh_entities(self, enemies: list[str], npcs: list[str]) -> None:
        """Update entity chips. Hides self when no entities present."""
        if not enemies and not npcs:
            self.display = False
            return

        self.display = True
        chips = []

        for name in enemies:
            chips.append(f"[bold red]💀 {name}[/bold red]")

        for name in npcs:
            chips.append(f"[bold magenta]👤 {name}[/bold magenta]")

        content = "[dim]PRESENT:[/dim]  " + "   ".join(chips)
        self.update(content)
