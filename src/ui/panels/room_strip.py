"""
RoomStrip widget — always-visible bar showing current room name and exits.
"""

from textual.widgets import Static


class RoomStrip(Static):
    """Top strip that displays the current room name (left) and exits (right)."""

    def refresh_room(self, room_name: str, exits: list[str]) -> None:
        """Update the strip with current room and exits."""
        name_part = f"[bold]🏠 {room_name}[/bold]"

        if exits:
            exits_text = "  ·  ".join(f"[cyan]{e}[/cyan]" for e in exits)
            content = f"{name_part}   exits: {exits_text}"
        else:
            content = f"{name_part}   [dim]no exits[/dim]"

        self.update(content)
