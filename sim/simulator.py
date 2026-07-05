"""Run the combat gauntlet with the optimal bot and aggregate outcomes.

Uses the real combat primitives (`combat_system.perform_attack`,
`player.take_damage`, difficulty-scaled enemies via `world.get_enemy`) so the
measured difficulty reflects the actual game. Loot is modeled simply (starter
weapon + a heal stock that restocks per fight) to isolate the combat-balance
levers we tune; see docs/DIFFICULTY_SIM_DESIGN.md.
"""
from __future__ import annotations

import functools
import statistics
from dataclasses import dataclass

import yaml

from src import difficulty, rng
from src.combat import combat_system
from src.data_loader import load_class_data, load_enemy_data, load_room_data, load_weapon_data
from src.game_world import GameWorld
from src.player import Player

from sim import bot
from sim.gauntlet import main_path_enemy_ids

HEAL_AMOUNT = 30       # a health_packet's player_heal
STARTING_HEALS = 3     # heals carried at run start
HEAL_PER_FIGHT = 1     # heals looted after each won fight
MAX_TURNS = 200        # safety cap against an unwinnable stalemate loop


@dataclass
class RunResult:
    won: bool
    died_to: str | None
    cleared: int          # enemies defeated
    level: int
    ending_hp_ratio: float


def _build_world() -> GameWorld:
    """Minimal world used only for difficulty/class-scaled enemy lookup."""
    return GameWorld(
        load_room_data(), {}, load_enemy_data(), {}, initialize_state=False
    )


@functools.lru_cache(maxsize=None)
def _class_weapons(class_id: str) -> tuple[tuple[str, int], ...]:
    """(weapon_id, damage) usable by the class, ascending by damage.

    Models weapon progression: a real player upgrades from the starter to
    rarer, stronger weapons as they explore.
    """
    try:
        with open("data/items/weapons.yaml") as fh:
            weapons = (yaml.safe_load(fh) or {}).get("weapons", {})
    except Exception:
        return ()
    usable = []
    for wid, wdata in weapons.items():
        allowed = wdata.get("allowed_classes", [])
        if not allowed or class_id in allowed:
            usable.append((wid, wdata.get("damage", 0)))
    usable.sort(key=lambda pair: pair[1])
    return tuple(usable)


def _equip_for_stage(player: Player, class_id: str, cleared: int, total: int) -> None:
    """Upgrade the equipped weapon to match progress through the gauntlet."""
    weapons = _class_weapons(class_id)
    if not weapons:
        return
    tier = min((cleared * len(weapons)) // max(1, total), len(weapons) - 1)
    weapon_id, _ = weapons[tier]
    if weapon_id == player.equipped_weapon:
        return
    weapon = load_weapon_data(weapon_id)
    if weapon:
        player.add_to_inventory(weapon_id, weapon)
        player.equip_weapon(weapon_id)


def _build_player(class_id: str) -> Player:
    player = Player("SimBot", class_id)
    combat_system.initialize_cooldowns(player.player_id)
    classes = load_class_data()
    weapon_id = classes.get(class_id, {}).get("starter_weapon")
    if weapon_id:
        weapon = load_weapon_data(weapon_id)
        if weapon:
            player.add_to_inventory(weapon_id, weapon)
            player.equip_weapon(weapon_id)
    player._sim_heals = STARTING_HEALS  # type: ignore[attr-defined]
    return player


def _fight(player: Player, enemy: dict) -> bool:
    """Resolve one fight to the death. Returns True if the player survives."""
    enemy_hp = enemy.get("health", 1)
    enemy_damage = enemy.get("damage", 0)
    pending_reduction = 0.0

    turns = 0
    while enemy_hp > 0 and player.is_alive() and turns < MAX_TURNS:
        turns += 1
        attacks = combat_system.get_available_attacks(player, getattr(player, "spells", []))
        hp_ratio = player.health / max(1, player.max_health)
        heals = getattr(player, "_sim_heals", 0)
        action, attack_id = bot.choose_action(
            player.calculate_damage(), hp_ratio, attacks, heals > 0
        )

        if action == "heal":
            player.heal(HEAL_AMOUNT)
            player._sim_heals -= 1  # type: ignore[attr-defined]
        else:
            result = combat_system.perform_attack(player, attack_id)
            enemy_hp -= result.get("damage", 0)
            if result.get("healing_amount"):
                player.heal(result["healing_amount"])
            pending_reduction = result.get("enemy_damage_reduction", 0) or 0.0

        combat_system.update_cooldowns(player)
        if enemy_hp <= 0:
            break

        # Enemy turn (basic attack; buffs from the player's last action mitigate).
        dealt = max(0, round(enemy_damage * (1 - pending_reduction)))
        player.take_damage(dealt)
        pending_reduction = 0.0

    return player.is_alive() and enemy_hp <= 0


def run_gauntlet(class_id: str, world: GameWorld, enemy_ids: list[str]) -> RunResult:
    player = _build_player(class_id)
    total = len(enemy_ids)
    cleared = 0
    for enemy_id in enemy_ids:
        enemy = world.get_enemy(enemy_id, class_id)
        if not enemy:
            continue
        _equip_for_stage(player, class_id, cleared, total)  # loot progression
        if not _fight(player, enemy):
            return RunResult(
                False, enemy_id, cleared, player.level,
                player.health / max(1, player.max_health),
            )
        cleared += 1
        base = enemy.get("harvesting_cycles", 50)
        if enemy.get("boss_room") or enemy.get("boss_enemy"):
            base *= 3
        player.harvest_cycles(difficulty.scale_xp(base))
        player._sim_heals += HEAL_PER_FIGHT  # type: ignore[attr-defined]

    return RunResult(
        True, None, cleared, player.level, player.health / max(1, player.max_health)
    )


@dataclass
class Measurement:
    mode: str
    player_class: str
    runs: int
    win_rate: float
    avg_cleared: float
    avg_ending_hp: float            # over wins
    deaths_by_enemy: dict[str, int]


def measure(class_id: str, mode: str, runs: int = 200, seed: int = 0) -> Measurement:
    difficulty.set_mode(mode)
    world = _build_world()
    enemy_ids = main_path_enemy_ids()

    results: list[RunResult] = []
    for i in range(runs):
        rng.seed(seed + i)
        results.append(run_gauntlet(class_id, world, enemy_ids))

    wins = [r for r in results if r.won]
    deaths: dict[str, int] = {}
    for r in results:
        if not r.won and r.died_to:
            deaths[r.died_to] = deaths.get(r.died_to, 0) + 1

    return Measurement(
        mode=mode,
        player_class=class_id,
        runs=runs,
        win_rate=len(wins) / runs if runs else 0.0,
        avg_cleared=statistics.fmean(r.cleared for r in results) if results else 0.0,
        avg_ending_hp=statistics.fmean(r.ending_hp_ratio for r in wins) if wins else 0.0,
        deaths_by_enemy=dict(sorted(deaths.items(), key=lambda kv: -kv[1])),
    )
