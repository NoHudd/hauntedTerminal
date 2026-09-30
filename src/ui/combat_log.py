"""Text for the combat output panel: the running log, or the attack list at the start."""
from __future__ import annotations

from typing import Any

import config.dev_config as dev_cfg
from engine.view_models import AttackView, StatsView
from src.move_info import effect_tags

# At or below this share of max HP the panel points at the heal move.
LOW_HP_FRACTION = 0.3

_ACTOR_FORMAT = {
    "player": ("green",  "👤"),
    "enemy":  ("red",    "👹"),
    "system": ("yellow", "⚡"),
}


def _format_entry(action: dict[str, Any]) -> str:
    actor = action.get('actor', 'system')
    message = action.get('message', 'Action performed')
    color, icon = _ACTOR_FORMAT.get(actor, ("white", "📋"))
    return f"[{color}]{icon} {message}[/{color}]"


def render_combat_output(
    combat_log: list[dict[str, Any]],
    player_view: StatsView | None,
    attacks: list[AttackView],
    player_hp: tuple[int, int] | None = None,
) -> str:
    """The combat panel's text: the attack list until the first blow, then the log.

    `player_hp` is (current, max) from the fight itself; the stats view can
    lag behind mid-combat, so it is only the fallback."""
    output_lines = []
    if player_hp is None and player_view is not None:
        player_hp = (player_view.health, player_view.max_health)
    hint = low_hp_hint(player_hp, attacks)

    if any(action.get("actor") in ("player", "enemy") for action in combat_log):
        # Mid-combat: show only outcomes. Controls live in the footer; the
        # attack list was shown at combat start. Keeps the log readable
        # instead of re-dumping the full controls block every turn.
        output_lines.append("[bold yellow]⚔ COMBAT LOG ⚔[/bold yellow]")
        output_lines.append("=" * 40)
        output_lines.extend(_format_entry(action) for action in combat_log[-10:])
        output_lines.append("=" * 40)
        output_lines.append(
            "[dim]Attacks: number keys in the footer · "
            "type 'use <item>' or 'flee'[/dim]"
        )
        if hint:
            output_lines.append(hint)
    else:
        # Before the first blow: introduce the fight and show attack options,
        # keeping system lines such as the enemy's opening taunt and tutorial hints.
        output_lines.extend([
            "[bold yellow]⚔ BATTLE STARTED ⚔[/bold yellow]",
            "=" * 40,
        ])
        output_lines.extend(_format_entry(action) for action in combat_log[-10:])
        output_lines.extend([
            "",
            "[dim]Selection Mode active — press 1-9 to attack, 0 to flee. "
            "TAB to type 'use <item>' instead.[/dim]",
            "",
            hotkey_display(player_view, attacks),
        ])
        if hint:
            output_lines.extend(["", hint])

    return "\n".join(output_lines)


def hotkey_display(player_view: StatsView | None, attacks: list[AttackView]) -> str:
    """Numbered attack list with damage, accuracy and cooldown for each hotkey."""
    if player_view is None:
        return "[dim]Attack options loading...[/dim]"

    hotkey_lines = ["[bold green]QUICK ATTACKS:[/bold green]"]
    base_damage = player_view.damage

    hotkey_num = 1
    for attack_data in attacks:
        if hotkey_num > 9:
            break

        attack_name = attack_data.name
        total_damage = base_damage + attack_data.bonus_damage
        accuracy = attack_data.accuracy
        cooldown = attack_data.cooldown
        # AttackView carries no attack type, so every row gets the plain bullet.
        type_icon = "•"
        cd_label = f"CD {cooldown}t" if cooldown > 0 else "no CD"
        # Healing and weakening are invisible in the damage number: name them.
        effects = "".join(
            f" · [green]{tag}[/green]"
            for tag in effect_tags(attack_data.healing, attack_data.weaken)
        )

        if not attack_data.on_cooldown:
            hotkey_lines.append(
                f"[cyan][{hotkey_num}][/cyan] {type_icon} {attack_name} — "
                f"[yellow]{total_damage} dmg[/yellow]{effects} "
                f"([dim]{accuracy}% hit · {cd_label}[/dim])"
            )
        else:
            hotkey_lines.append(
                f"[dim][{hotkey_num}] {type_icon} {attack_name} — "
                f"on cooldown ({attack_data.cooldown_remaining}t left)[/dim]"
            )
        hotkey_num += 1

    if hotkey_num == 1:
        hotkey_lines.append("[dim]No attacks available[/dim]")

    return "\n".join(hotkey_lines)


def low_hp_hint(player_hp: tuple[int, int] | None, attacks: list[AttackView]) -> str:
    """When HP is low, name the key that heals — a new player won't go looking.
    A hint, so the Settings "In-game hints" switch turns it off."""
    if not player_hp or not getattr(dev_cfg, "SHOW_HINTS", True):
        return ""
    hp, max_hp = player_hp
    if max_hp <= 0 or hp > max_hp * LOW_HP_FRACTION:
        return ""
    for key, attack in enumerate(attacks[:9], 1):
        if attack.healing <= 0:
            continue
        if attack.on_cooldown:
            turns = attack.cooldown_remaining
            when = f"ready in {turns} turn{'s' if turns != 1 else ''}"
        else:
            when = "ready now"
        return (
            f"[bold green]💚 Low HP! Press [{key}] {attack.name} to heal "
            f"{attack.healing} HP ({when}).[/bold green]"
        )
    return ""
