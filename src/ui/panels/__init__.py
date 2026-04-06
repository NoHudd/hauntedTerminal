"""UI panels package."""


def create_health_bar(current: int, maximum: int, length: int = 12) -> str:
    """Create an enhanced health bar with gradient styling."""
    if maximum <= 0:
        return "[dim]▒▒▒▒▒▒▒▒▒▒▒▒[/dim]"

    health_percent = current / maximum
    filled_length = int(health_percent * length)
    empty_length = length - filled_length

    if health_percent > 0.7:
        bar_color = "green"
        bar_char = "█"
    elif health_percent > 0.4:
        bar_color = "yellow"
        bar_char = "▓"
    elif health_percent > 0.15:
        bar_color = "red"
        bar_char = "▒"
    else:
        bar_color = "red blink"
        bar_char = "░"

    filled_bar = bar_char * filled_length
    empty_bar = "░" * empty_length

    return f"[{bar_color}]{filled_bar}[/{bar_color}][dim]{empty_bar}[/dim]"
