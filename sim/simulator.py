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
# The real game is stingy with healing: exactly ONE guaranteed health_packet on
# the main path (home_grove), plus probabilistic drops from a couple of enemies.
# There is no restock or shop. We model that faithfully instead of gifting heals,
# because heal scarcity — not enemy stats — is the game's real difficulty lever.
STARTING_HEALS = 1     # the one guaranteed home_grove packet
MAX_TURNS = 200        # safety cap against an unwinnable stalemate loop

# The sim equips only weapons a real player can realistically obtain. common/uncommon/
# rare are world-placed; epic is reliably obtained via the guaranteed capstone drop from
# null_guardian.sys (the last pre-boss main-path enemy) — see its loot_table. Legendary
# is EXCLUDED: it never world-places and is only a post-win boss trophy, so equipping it
# (as the old tune did with zero_day_blade dmg 50) overstated player power and inflated
# the tuned band. Modeling epic-capstone-late but no legendary matches real obtainability.
SIM_OBTAINABLE_RARITIES = {"common", "uncommon", "rare", "epic"}

# Consumable ids that restore HP, with the amount (from data/items/consumables.yaml).
_HEAL_ITEMS = {"health_packet": 30, "stable_cache": 40}


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
            weapons = yaml.safe_load(fh) or {}
    except Exception:
        return ()
    usable = []
    for wid, wdata in weapons.items():
        if str(wdata.get("rarity", "common")).lower() not in SIM_OBTAINABLE_RARITIES:
            continue
        allowed = wdata.get("allowed_classes", [])
        if not allowed or class_id in allowed:
            usable.append((wid, wdata.get("damage", 0)))
    usable.sort(key=lambda pair: pair[1])
    return tuple(usable)


def _armor_data(armor_id: str) -> dict | None:
    try:
        with open("data/items/armor.yaml") as fh:
            return (yaml.safe_load(fh) or {}).get(armor_id)
    except Exception:
        return None


def _class_armor(class_id: str) -> tuple[tuple[str, int], ...]:
    """(armor_id, defense) obtainable by the class, ascending by defense.

    Models armor progression the same way as weapons, gated to obtainable
    rarities so the sim doesn't equip gear the real game can't hand out.
    """
    try:
        with open("data/items/armor.yaml") as fh:
            armor = yaml.safe_load(fh) or {}
    except Exception:
        return ()
    usable = []
    for aid, adata in armor.items():
        if str(adata.get("rarity", "common")).lower() not in SIM_OBTAINABLE_RARITIES:
            continue
        allowed = adata.get("allowed_classes", [])
        if not allowed or class_id in allowed:
            usable.append((aid, adata.get("defense", 0)))
    usable.sort(key=lambda pair: pair[1])
    return tuple(usable)


def _equip_for_stage(player: Player, class_id: str, cleared: int, total: int) -> None:
    """Upgrade the equipped weapon and armor to match progress through the gauntlet."""
    weapons = _class_weapons(class_id)
    if weapons:
        tier = min((cleared * len(weapons)) // max(1, total), len(weapons) - 1)
        weapon_id, _ = weapons[tier]
        if weapon_id != player.equipped_weapon:
            weapon = load_weapon_data(weapon_id)
            if weapon:
                player.add_to_inventory(weapon_id, weapon)
                player.equip_weapon(weapon_id)

    armor = _class_armor(class_id)
    if armor:
        a_tier = min((cleared * len(armor)) // max(1, total), len(armor) - 1)
        armor_id, _ = armor[a_tier]
        if armor_id != player.equipped_armor:
            adata = _armor_data(armor_id)
            if adata:
                player.add_to_inventory(armor_id, adata)
                player.equip_armor(armor_id)


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
        # Loot heals only if this enemy actually drops one and the roll hits —
        # faithful to the real (stingy) drop economy, not a free per-fight heal.
        for drop in enemy.get("drops", []) or []:
            if drop.get("item") in _HEAL_ITEMS and rng.random() * 100 < drop.get("chance", 0):
                player._sim_heals += 1  # type: ignore[attr-defined]

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

    results: list[RunResult] = []
    for i in range(runs):
        rng.seed(seed + i)
        # Roll a fresh enemy set per run so the measurement reflects the pool
        # distribution, not one fixed draw.
        enemy_ids = main_path_enemy_ids()
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
