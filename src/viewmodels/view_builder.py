#!/usr/bin/env python3
"""
View Builder - Converts backend objects into view models for the UI.

This is the only module that knows how to translate between backend data structures
and frontend view models, maintaining clean separation of concerns.
"""

from typing import List, Optional
import logging

from src.room_paths import ROOM_ID_TO_PATH
from src.viewmodels.view_models import (
    StatsView,
    InventoryItemView,
    InventoryView,
    RoomView,
    AttackView,
    CombatView,
    EnemyView
)

logger = logging.getLogger(__name__)

# ROOM_ID_TO_PATH now lives in src/room_paths.py (domain content). Re-exported
# above for existing importers.


class ViewBuilder:
    """Static methods to build view models from backend objects."""

    @staticmethod
    def build_stats_view(player) -> StatsView:
        """
        Build stats view from Player object.

        Args:
            player: Player object with health, damage, etc.

        Returns:
            StatsView with player statistics
        """
        try:
            # Use calculate_damage() to get total damage including weapon and status effects
            total_damage = player.calculate_damage() if hasattr(player, 'calculate_damage') else getattr(player, 'total_damage', 0)

            return StatsView(
                player_name=getattr(player, 'name', 'Unknown'),
                health=getattr(player, 'health', 0),
                max_health=getattr(player, 'max_health', 100),
                damage=total_damage,
                player_class=getattr(player, 'player_class', 'Unknown'),
                level=getattr(player, 'level', 1),
                cycles=getattr(player, 'harvesting_cycles', 0),
                cycles_to_next=getattr(player, 'cycles_to_next_level', 0),
            )
        except Exception as e:
            logger.error(f"Error building stats view: {e}", exc_info=True)
            # Return safe default
            return StatsView(
                player_name='Unknown',
                health=0,
                max_health=100,
                damage=0,
                player_class='Unknown'
            )

    @staticmethod
    def build_inventory_view(player) -> InventoryView:
        """
        Build inventory view from Player object.

        Args:
            player: Player object with inventory dict

        Returns:
            InventoryView with list of InventoryItemView objects
        """
        try:
            inventory = getattr(player, 'inventory', {})
            equipped_weapon = getattr(player, 'equipped_weapon', None)

            items = []
            for item_id, item_data in inventory.items():
                if not isinstance(item_data, dict):
                    continue

                items.append(InventoryItemView(
                    id=item_id,
                    name=item_data.get('name', item_id),
                    item_type=item_data.get('type', 'unknown'),
                    rarity=item_data.get('rarity', 'common'),
                    is_equipped=(item_id == equipped_weapon),
                    damage=item_data.get('damage'),
                    healing=item_data.get('healing')
                ))

            return InventoryView(items=items)
        except Exception as e:
            logger.error(f"Error building inventory view: {e}", exc_info=True)
            return InventoryView(items=[])

    @staticmethod
    def build_room_view(world, room_id: str) -> RoomView:
        """
        Build room view from GameWorld object.

        Args:
            world: GameWorld object
            room_id: ID of the room to build view for

        Returns:
            RoomView with room data
        """
        try:
            rooms = getattr(world, 'rooms', {})
            room_data = rooms.get(room_id, {})

            # Convert exit IDs to simple paths for the exits panel
            # Shows what the user needs to type (e.g., "/var").
            # Filter out hidden rooms — they only appear after `ls -a` discovery.
            exit_ids = room_data.exits
            exit_commands = []
            get_room_state = getattr(world, 'get_room_state', None)
            for exit_id in exit_ids:
                if get_room_state is not None:
                    state = get_room_state(exit_id) or {}
                    if state.get('hidden', False):
                        continue
                path = ROOM_ID_TO_PATH.get(exit_id, exit_id)
                exit_commands.append(path)

            # Enemies: keep (id, name) pairs so the scene can resolve sprites
            enemy_ids = [
                eid for eid in getattr(world, 'get_enemies_in_room', lambda r: [])(room_id)
                if eid in getattr(world, 'enemies', {})
            ]
            enemy_names = [getattr(world.enemies[eid], 'name', eid) for eid in enemy_ids]

            npc_ids = [
                nid for nid in getattr(world, 'get_npcs_in_room', lambda r: [])(room_id)
                if nid in getattr(world, 'npcs', {})
            ]
            npc_names = [world.npcs.get(nid, {}).get('name', nid) for nid in npc_ids]

            return RoomView(
                name=room_data.name or room_id,
                description=room_data.description or 'An unknown location.',
                id=room_id,
                zone=getattr(room_data, 'zone', '') or '',
                exits=exit_commands,
                enemies=enemy_names,
                npcs=npc_names,
                enemy_ids=enemy_ids,
                npc_ids=npc_ids,
            )
        except Exception as e:
            logger.error(f"Error building room view for {room_id}: {e}", exc_info=True)
            return RoomView(
                name=room_id,
                description='An unknown location.',
                exits=[]
            )

    @staticmethod
    def build_combat_view(player, enemy_data: dict, enemy_health: int,
                         combat_system) -> CombatView:
        """
        Build combat view from player, enemy, and combat system.

        Args:
            player: Player object
            enemy_data: Dict with enemy information
            enemy_health: Current enemy health
            combat_system: CombatSystem instance for attacks

        Returns:
            CombatView with all combat UI data
        """
        try:
            # Build attack list
            available_attacks = ViewBuilder.build_attack_list(player, combat_system)

            # Build usable items (consumables/spells in inventory)
            usable_items = []
            inventory = getattr(player, 'inventory', {})
            for item_id, item_data in inventory.items():
                if not isinstance(item_data, dict):
                    continue

                item_type = item_data.get('type', '')
                if item_type in ['consumable', 'spell']:
                    usable_items.append(InventoryItemView(
                        id=item_id,
                        name=item_data.get('name', item_id),
                        item_type=item_type,
                        rarity=item_data.get('rarity', 'common'),
                        is_equipped=False,
                        damage=item_data.get('damage'),
                        healing=item_data.get('healing')
                    ))

            return CombatView(
                enemy_name=enemy_data.get('name', 'Unknown Enemy'),
                enemy_health=enemy_health,
                enemy_max_health=enemy_data.get('health', enemy_health),
                player_health=getattr(player, 'health', 0),
                player_max_health=getattr(player, 'max_health', 100),
                available_attacks=available_attacks,
                usable_items=usable_items
            )
        except Exception as e:
            logger.error(f"Error building combat view: {e}", exc_info=True)
            # Return minimal combat view
            return CombatView(
                enemy_name='Unknown Enemy',
                enemy_health=enemy_health,
                enemy_max_health=enemy_health,
                player_health=getattr(player, 'health', 0),
                player_max_health=getattr(player, 'max_health', 100),
                available_attacks=[],
                usable_items=[]
            )

    @staticmethod
    def build_enemy_view(enemy_id: str, enemy_data: dict) -> EnemyView:
        """
        Build enemy view from enemy data.

        Args:
            enemy_id: Enemy identifier
            enemy_data: Dict with enemy information

        Returns:
            EnemyView with enemy display data
        """
        try:
            return EnemyView(
                id=enemy_id,
                name=enemy_data.get('name', enemy_id),
                health=enemy_data.get('health', 50),
                max_health=enemy_data.get('health', 50),
                damage=enemy_data.get('damage', 10),
                description=enemy_data.get('description', 'A hostile entity.')
            )
        except Exception as e:
            logger.error(f"Error building enemy view for {enemy_id}: {e}", exc_info=True)
            return EnemyView(
                id=enemy_id,
                name=enemy_id,
                health=50,
                max_health=50,
                damage=10,
                description='A hostile entity.'
            )

    @staticmethod
    def build_attack_list(player, combat_system) -> List[AttackView]:
        """
        Build list of available attacks with cooldown info.

        Args:
            player: Player object
            combat_system: CombatSystem instance

        Returns:
            List of AttackView objects
        """
        try:
            player_id = getattr(player, 'player_id', None)
            player_class = getattr(player, 'player_class', 'unknown')

            if not player_id:
                logger.warning("Player has no player_id, returning empty attack list")
                return []

            # Get available attacks from combat system
            spells = getattr(player, 'spells', [])

            available_attacks = combat_system.get_available_attacks(player, spells)

            attack_views = []
            # get_available_attacks returns a dict, so iterate over .values()
            for attack in available_attacks.values():
                if not isinstance(attack, dict):
                    logger.warning(f"Attack is not a dict: {type(attack)}")
                    continue

                attack_id = attack.get('id', '')
                # Cooldown info is already in the attack data from get_available_attacks()
                cooldown_remaining = attack.get('cooldown_remaining', 0)
                on_cooldown = attack.get('on_cooldown', False)

                attack_view = AttackView(
                    id=attack_id,
                    name=attack.get('name', attack_id),
                    bonus_damage=attack.get('bonus_damage', 0),
                    cooldown=attack.get('cooldown', 0),
                    cooldown_remaining=cooldown_remaining,
                    on_cooldown=on_cooldown,
                    accuracy=attack.get('accuracy', 100)
                )
                attack_views.append(attack_view)
            return attack_views
        except Exception as e:
            logger.error(f"Error building attack list: {e}", exc_info=True)
            return []
