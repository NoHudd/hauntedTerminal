"""Enemy loot: authored drops plus rarity-weighted gear tables."""
from src import rng


class LootService:
    """Rolls and places a defeated enemy's loot, at most once per enemy per run."""

    def __init__(self, world, player, output, relist_room):
        self.world = world
        self.player = player
        self.output = output
        self._relist_room = relist_room
        # Enemy ids whose loot has already been awarded this run. remove_enemy_from_room
        # re-emits ENEMY_DEFEATED, so this guards against double-rolling loot.
        self.awarded: set[str] = set()

    def award_once(self, enemy_id, room_id):
        """Award enemy_id's loot into room_id unless it was already awarded."""
        if enemy_id in self.awarded:
            return []
        self.awarded.add(enemy_id)
        return self.award_enemy_drops(enemy_id, room_id)

    def award_enemy_drops(self, enemy_id, room_id):
        """Place an enemy's drops into room_id. Returns the dropped item ids.

        Existing `drops` (heals/keys/badges) are activated here — the difficulty
        tune already assumes these fire. Gear `loot_table` is added in Task 2.
        """
        # get_enemy dumps the typed Enemy model to a plain dict (self.world.enemies
        # holds models); reading the raw model with .get() crashes and aborts the
        # ENEMY_DEFEATED handler before removal, leaving the enemy to be re-fought.
        enemy = self.world.get_enemy(enemy_id)
        if not enemy:
            return []

        self.player.run_stats["kills"] = self.player.run_stats.get("kills", 0) + 1

        dropped = []
        for drop in enemy.get("drops", []) or []:
            item_id = drop.get("item")
            if item_id and rng.random() * 100 < drop.get("chance", 0):
                self.world.add_item_to_room(item_id, room_id)
                dropped.append(item_id)

        gear_id = self.roll_loot_table(enemy.get("loot_table", []) or [])
        if gear_id:
            self.world.add_item_to_room(gear_id, room_id)
            dropped.append(gear_id)

        if dropped:
            names = ", ".join((self.world.get_item(i) or {}).get("name", i) for i in dropped)
            self.output.write(f"[bold yellow]The defeated enemy dropped: {names}[/bold yellow]")
            self._relist_room()
        return dropped

    def roll_loot_table(self, table):
        """Roll a rarity-weighted gear table. Rolls entries in order; returns the
        first hit's item id (at most one gear drop per kill), or None."""
        for entry in table or []:
            rarity = entry.get("rarity")
            if rarity and rng.random() * 100 < entry.get("chance", 0):
                item_id = self.random_gear_of_rarity(rarity)
                if item_id:
                    return item_id
        return None

    def random_gear_of_rarity(self, rarity):
        """A class-appropriate, not-yet-placed weapon/armor of this rarity, or None.
        Gear only — never a consumable — so drop tables can't inflate the heal economy."""
        target = str(rarity).lower()
        candidates = []
        for iid in self.world.items:
            data = self.world.get_item(iid)  # dict via boundary
            if (data.get("type") in ("weapon", "armor")
                    and str(data.get("rarity", "")).lower() == target
                    and self.player.can_use_item(data)
                    and iid not in self.world.item_locations):
                candidates.append(iid)
        return rng.choice(candidates) if candidates else None
