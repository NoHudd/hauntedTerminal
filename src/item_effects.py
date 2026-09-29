"""What using, reading or equipping an item does to the player and world."""
from src import rng
from utils.debug_tools import debug_log

# Human-readable descriptions for story flags shown in journal/autosave feedback.
STORY_FLAG_TITLES = {
    "identity_retrieved":   "Identity Retrieved",
    "typo_discovered":      "The Creator's Typo",
    "manual_recovered":     "The Ancient Manual",
    "bovine_prophecy":      "The Bovine Prophecy",
    "moo_heard":            "The Sacred Moo",
    "corruption_witnessed": "The Clicking Disk",
    "sudo_trial_complete":  "Sudo Trial Complete",
    "mirror_confronted":    "Mirror Confronted",
    "sudo_quest_active":    "Sudo Quest Active",
    "bovine_encountered":   "Bovine Sanctuary Found",
    "milk_claimed":         "Milk of Motherboard Claimed",
    "ending_chosen":        "Ending Chosen",
}

STORY_FLAG_DESCRIPTIONS = {
    "identity_retrieved":  "You read your own .bash_profile and remembered who you were.",
    "typo_discovered":     "The system_err.log revealed: the apocalypse was caused by a typo.",
    "manual_recovered":    "An old man page taught you the Creators' commands, and that ls -a sees the hidden.",
    "bovine_prophecy":     "A dusty log foretold a Great One in the games no one plays.",
    "moo_heard":           "You read .moo and summoned the Great ASCII Bovine.",
    "corruption_witnessed": "A corrupted README showed you what the corruption does to files.",
    "sudo_trial_complete": "You proved worthy of sudo privileges.",
    "mirror_confronted":   "You faced your reflection in the Mirror Sector.",
    "sudo_quest_active":   "The sudo quest is in progress.",
    "bovine_encountered":  "You entered the hidden Bovine Sanctuary.",
    "milk_claimed":        "You claimed the legendary Milk of Motherboard.",
    "ending_chosen":       "You chose your ending.",
}


def class_restriction_text(item):
    """Get the class restriction text for display in error messages."""
    for field in ("class_restriction", "allowed_classes"):
        val = getattr(item, field)
        if val:
            return " or ".join(val) if isinstance(val, list) else str(val)
    return "unknown"


class ItemEffects:
    """Applies item effects. start_encounter begins combat with whatever is in
    the current room; it is the command handler's check_for_enemies."""

    def __init__(self, player, world, output, bus, room_aliases, flow, start_encounter):
        self.player = player
        self.world = world
        self.output = output
        self.bus = bus
        self.room_aliases = room_aliases
        self.flow = flow
        self._start_encounter = start_encounter

    def use_key(self, item_id, item):
        """Handle the use of a key item"""
        unlocks = item.unlocks
        if not unlocks:
            self.output.write(f"You examine [green]{item_id}[/green], but it doesn't seem to unlock anything here.")
            return

        # Check if the key unlocks a room in the current location.
        # Normalize path-format entries ("/opt/mage_tower") to room IDs ("opt_mage_tower")
        # via room_aliases so YAML paths and room IDs are interchangeable.
        current_room_id = self.player.current_room
        exits = self.world.get_exits(current_room_id)
        resolved_unlocks = [self.room_aliases.get(r.lower(), r) for r in unlocks]

        unlocked_something = False
        for room_to_unlock in resolved_unlocks:
            if room_to_unlock in exits:
                self.world.unlock_room(room_to_unlock)
                self.output.write(f"[yellow]You hear a click. The path to {room_to_unlock} is now open.[/yellow]")
                unlocked_something = True

        if not unlocked_something:
            self.output.write(f"You can't find a lock that [green]{item_id}[/green] fits here.")

    def show_damage_change(self, old_damage: int, new_damage: int):
        """Display damage comparison after equipping a weapon."""
        delta = new_damage - old_damage
        if delta > 0:
            self.output.write(f"[green]Your total damage increased by {delta} (from {old_damage} to {new_damage}).[/green]")
        elif delta < 0:
            self.output.write(f"[red]Your total damage decreased by {abs(delta)} (from {old_damage} to {new_damage}).[/red]")
        else:
            self.output.write(f"[yellow]Your total damage remains at {new_damage}.[/yellow]")

    def read_lore(self, item_id, item):
        """Handle reading a lore item"""
        content = item.content or "This file appears to be empty or corrupted."
        name = item.name
        self.output.write(f"[bold cyan]── {name} ──[/bold cyan]\n{content}")
        if item.on_read is not None:
            self.execute_effect(item.on_read)
        self.trigger_story_flag(item)

    def trigger_story_flag(self, item) -> bool:
        """Set the item's story_flag, show feedback, auto-save. Returns True if a new
        story beat fired (so callers can hold the room re-list a beat)."""
        flag = item.story_flag
        if not flag:
            return False
        if self.player.get_story_flag(flag):
            return False

        self.player.set_story_flag(flag, True)
        title = STORY_FLAG_TITLES.get(flag, flag.replace("_", " ").title())
        self.output.write(
            f"\n[bold magenta]✦ Memory restored: {title} ✦[/bold magenta]\n"
            f"[dim]Saving progress...[/dim]"
        )

        # Auto-save: story beats act as save points.
        try:
            from src.save import save_manager
            world_state = self.world.get_state()
            save_manager.save_game(self.player, world_state)
            self.output.write("[dim green]✓ Progress saved.[/dim green]")
        except Exception as e:
            debug_log(f"Auto-save after story flag {flag} failed: {e}")
            self.output.write(f"[dim yellow]⚠ Auto-save failed: {e}[/dim yellow]")
        return True

    def use_consumable(self, item_id, item):
        """Handle using a consumable item. Returns False if item had no effect (e.g. heal at full HP)."""
        item_name = item.name
        combat_effects = item.combat_effects
        on_use_effects = item.on_use
        special_effects = item.special_effects

        # Show the on_use message if present
        message = on_use_effects.get("message") if isinstance(on_use_effects, dict) else None

        # Guard: if this item only heals and the player is already at full health, refuse use.
        only_heals = "player_heal" in combat_effects and not any(
            k in combat_effects for k in ("player_heal_over_time", "player_mana_restore")
        ) and not special_effects
        if only_heals and self.player.health >= self.player.max_health:
            self.output.write(f"[yellow]Your health is already full. The {item_name} was not consumed.[/yellow]")
            return False

        # Apply combat_effects (the canonical effect block for consumables)
        healed = 0
        if "player_heal" in combat_effects:
            healed = self.player.heal(combat_effects["player_heal"])

        if "player_heal_over_time" in combat_effects:
            hot_amount = combat_effects["player_heal_over_time"]
            duration = combat_effects.get("duration_turns", 3)
            self.player.add_status_effect(
                f"{item_id}_hot",
                {"type": "heal_over_time", "heal_per_turn": hot_amount // duration, "name": item_name},
                duration
            )
            if not message:
                self.output.write(f"You used [green]{item_name}[/green]. Healing {hot_amount} HP over {duration} turns.")

        if "player_mana_restore" in combat_effects:
            amount = combat_effects["player_mana_restore"]
            if hasattr(self.player, "restore_mana"):
                self.player.restore_mana(amount)
            if not message:
                self.output.write(f"You used [green]{item_name}[/green]. Restored {amount} mana.")

        # Apply special_effects (e.g. permanent stat boost for sudo_seed)
        for effect in special_effects:
            if effect.get("type") == "permanent_stat_boost":
                stat = effect.get("stat")
                value = effect.get("value", 0)
                if stat == "strength" and hasattr(self.player, "increase_damage"):
                    self.player.increase_damage(value)
                elif stat == "health" and hasattr(self.player, "increase_max_health"):
                    self.player.increase_max_health(value)

        # Show message or fallback
        if message:
            heal_suffix = f" ([green]+{healed} HP[/green])" if healed else ""
            self.output.write(f"{message}{heal_suffix}")
        elif not combat_effects and not special_effects:
            self.output.write(f"You used [green]{item_name}[/green].")

        # Legacy on_use heal field (fallback for any old-format items)
        if "heal" in on_use_effects and not healed:
            healed = self.player.heal(on_use_effects["heal"])
            self.output.write(f"You used [green]{item_name}[/green] and restored {healed} health.")

        # Process status effects from on_use block
        for effect_key, effect_value in (on_use_effects.items() if isinstance(on_use_effects, dict) else []):
            if effect_key in ("heal", "message"):
                continue
            debug_log(f"Processing additional effect: {effect_key} from consumable {item_id}")
            if effect_key == "status_effect":
                effect_data = effect_value
                effect_id = effect_data.get("id", item_id + "_effect")
                effect_name = effect_data.get("name", "Unknown Effect")
                effect_duration = effect_data.get("duration", 3)
                debug_log(f"Applying status effect {effect_id} ({effect_name}) for {effect_duration} turns")
                self.player.add_status_effect(effect_id, effect_data, effect_duration)
                self.output.write(f"[magenta]You gained the '{effect_name}' effect for {effect_duration} turns![/magenta]")


    def use_upgrade(self, item_id, item):
        """Handle using an upgrade item"""
        # Process permanent stat boosts
        effects = item.effects

        # Health boosts
        if "permanent_health" in effects:
            amount = effects["permanent_health"]
            new_max = self.player.increase_max_health(amount)
            self.output.write(f"[bold]── Character Improvement ──[/bold]\n[green]Your maximum health permanently increased by {amount} to {new_max}![/green]")

        # Damage boosts
        if "permanent_damage" in effects:
            amount = effects["permanent_damage"]
            new_damage = self.player.increase_damage(amount)
            self.output.write(f"[bold]── Character Improvement ──[/bold]\n[green]Your base damage permanently increased by {amount} to {new_damage}![/green]")

        # Process on_use effects if any
        if item.on_use:
            self.execute_effect(item.on_use)

    def learn_spell(self, item_id, item):
        """Handle using a spell item"""
        # Learn the spell
        if self.player.learn_spell(item):
            spell_name = item.name
            self.output.write(f"[bold]── Spell Learned ──[/bold]\n[green]You learned the {spell_name} spell![/green]")

            # Apply any immediate status effects if defined
            if item.status_effect is not None:
                effect_data = item.status_effect
                effect_id = effect_data.get("id", item_id + "_effect")
                effect_name = effect_data.get("name", spell_name + " Effect")
                effect_duration = effect_data.get("duration", 3)  # Default 3 turns

                # Add the status effect
                self.player.add_status_effect(effect_id, effect_data, effect_duration)
                self.output.write(f"[bold]── Status Effect ──[/bold]\n[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]")
        else:
            self.output.error("[red]You don't have the ability to learn this spell.[/red]")

    def execute_effect(self, effect):
        """Execute a special effect from an item or event."""
        if not isinstance(effect, dict):
            self.output.write(f"[italic]{effect}[/italic]")
            return

        if "message" in effect:
            self.output.write(f"[italic cyan]{effect['message']}[/italic]")

        if "story_flag" in effect:
            # Learning something can open a path: a hidden room may declare a
            # `discovery_requirement`, and `ls -a` only reveals it once the
            # corresponding flag is set. This is the quiet setter — lore reads
            # use trigger_story_flag, which also announces and auto-saves.
            flag = effect["story_flag"]
            if not self.player.get_story_flag(flag):
                self.player.set_story_flag(flag, True)
                debug_log(f"Story flag '{flag}' set by effect")

        if "heal" in effect:
            amount = effect["heal"]
            self.player.heal(amount)
            self.output.write(f"[green]You gained {amount} health![/green]")

        if "damage" in effect:
            amount = effect["damage"]
            self.player.take_damage(amount)
            self.output.write(f"[red]You took {amount} damage![/red]")
            if not self.player.is_alive():
                self.flow.game_over()

        if "add_status_effect" in effect:
            status_data = effect["add_status_effect"]
            effect_id = status_data.get("id", "effect_" + str(rng.randint(1000, 9999)))
            effect_name = status_data.get("name", "Effect")
            effect_duration = status_data.get("duration", 3)
            self.player.add_status_effect(effect_id, status_data, effect_duration)
            self.output.write(f"[magenta]You gained the {effect_name} effect for {effect_duration} turns![/magenta]")

        if "add_item" in effect:
            item_id = effect["add_item"]
            item = self.world.get_item(item_id)
            if item:
                self.player.add_to_inventory(item_id, item)
                self.output.write(f"[green]You obtained {item.name}![/green]")

        if "remove_item" in effect:
            item_id = effect["remove_item"]
            if self.player.has_item(item_id):
                item_name = self.player.inventory[item_id].name
                self.player.remove_from_inventory(item_id)
                self.output.write(f"[yellow]You lost {item_name}![/yellow]")

        if "unlock" in effect:
            room_id = effect["unlock"]
            self.world.unlock_room(room_id)
            self.output.write(f"[yellow]A path to {room_id} has been unlocked![/yellow]")

        if "spawn_enemy" in effect:
            enemy_id = effect["spawn_enemy"]
            room_id = effect.get("in_room", self.player.current_room)
            enemy = self.world.get_enemy(enemy_id, self.player.player_class)
            if enemy:
                self.world.enemy_locations[enemy_id] = room_id
                if room_id == self.player.current_room:
                    self.output.write(f"[bold red]{enemy.name} has appeared![/bold red]")
                    self._start_encounter()
