# Extending the Haunted Filesystem Game

This guide explains how to add new content to the Haunted Filesystem Experience using YAML files. The game is designed to be easily extendable without requiring changes to the core code.

## YAML Structure

The game uses four types of YAML files to define game content:

1. **Rooms** - Locations the player can visit
2. **Items** - Objects the player can collect and use
3. **Enemies** - Adversaries the player must defeat
4. **NPCs** - Non-player characters the player can interact with

All YAML files are stored in their respective directories under the `data/` folder:
- `data/rooms/`
- `data/items/`
- `data/enemies/`
- `data/npcs/`

## Adding a New Room

To add a new room to the game, create a new YAML file in the `data/rooms/` directory. The filename (without the `.yml` extension) will be the room's ID used in the game.

Example: `data/rooms/secret_lab.yml`

```yaml
name: Secret Laboratory
description: A hidden laboratory with advanced technology and mysterious experiments.
detailed_description: This laboratory appears to have been used for experimental system operations. Computer terminals line the walls, and strange data visualizations flicker on screens. The air hums with power, untouched by the corruption outside.
exits:
  - archive
items:
  - quantum_tool.sh
npcs:
  - ai_assistant.bin
enemies:
  - prototype.exe
locked: true
key_required: lab_keycard
```

### Room Properties

- `name`: Display name of the room
- `description`: Short description shown when entering the room
- `detailed_description`: Longer description shown when using the `look` command
- `exits`: List of room IDs that can be accessed from this room
- `items`: List of item IDs initially present in the room
- `npcs`: List of NPC IDs initially present in the room
- `enemies`: List of enemy IDs initially present in the room
- `locked`: Whether the room is initially locked (true/false)
- `key_required`: The item ID needed to unlock this room (if locked)

## Adding a New Item

To add a new item, create a YAML file in the `data/items/` directory. The filename (without the `.yml` extension) will be the item's ID.

Example: `data/items/quantum_tool.sh.yml`

```yaml
name: Quantum Tool
short_description: An advanced tool that manipulates digital space
description: This experimental tool appears to bend the rules of the digital universe. Its sleek interface glows with pulsing lights, and strange symbols dance across its surface.
content: |
  #!/bin/bash
  # QUANTUM MANIPULATION TOOL v0.9.2
  # EXPERIMENTAL - USE WITH CAUTION
  
  echo "Initializing quantum field generators..."
  echo "Calculating probability matrices..."
  echo "Manipulation field ready. Target identified."
  echo "Reality distortion active. Modifications applied."
takeable: true
usable: true
usable_in_combat: true
consumed_on_use: false
on_take:
  message: The quantum tool feels weightless in your possession, vibrating slightly with potential energy.
on_use:
  message: The quantum tool activates, warping the digital space around you in fascinating patterns.
combat_effects:
  enemy_damage: 35
  player_heal: 15
```

### Item Properties

- `name`: Display name of the item
- `short_description`: Brief description shown in inventory and room listings
- `description`: Detailed description shown when examining the item
- `content`: The text content shown when using `cat` on the item
- `takeable`: Whether the item can be picked up (true/false)
- `usable`: Whether the item can be used (true/false)
- `usable_in_combat`: Whether the item can be used in combat (true/false)
- `consumed_on_use`: Whether the item is consumed when used (true/false)
- `on_take`: Special effects that occur when taking the item
- `on_read`: Special effects that occur when reading the item
- `on_use`: Special effects that occur when using the item
- `on_drop`: Special effects that occur when dropping the item
- `combat_effects`: Effects that occur when used in combat
  - `enemy_damage`: Amount of damage dealt to enemies
  - `player_heal`: Amount of health restored to the player

## Adding Class-Specific Items

You can create items that can only be used by specific character classes. These items won't appear in the game for classes that can't use them, making each playthrough unique.

Example: `data/items/arcane_amplifier.yml`

```yaml
name: Arcane Amplifier
short_description: A mystical crystal that enhances magical abilities
description: This crystal resonates with arcane energy, amplifying the magical abilities of those skilled in the arcane arts. It pulses with an inner light that seems to respond to your thoughts.
content: |
  The crystal hums with arcane energy, vibrating slightly in your hands.
  Inscribed on its base in ancient script is the phrase:
  "To those who bend reality with thought, I grant greater power."
takeable: true
usable: true
item_type: "damage_boost"
boost_amount: 5
class_restriction: "mage"
consumed_on_use: true
allowed_rooms:
  - archive
  - hidden
on_use:
  message: The crystal dissolves into pure energy that flows into your being. You feel your magical abilities significantly enhanced.
```

### Class-Specific Item Properties

- `class_restriction`: Restrict item to a specific class ("fighter", "mage", "celtic") or list of classes
- `item_type`: The type of stat boost ("health_boost", "max_health_boost", "damage_boost", "spell")
- `boost_amount`: The amount of the stat boost
- `allowed_rooms`: List of rooms where this item can randomly appear
- `only_in_unlocked`: Whether the item should only appear in unlocked rooms (default: true)

## Creating New Health and Combat Items

Health potions and combat items are particularly useful for players. Here's how to create them:

Example: `data/items/mega_health_elixir.yml`

```yaml
name: Mega Health Elixir
short_description: A powerful elixir that fully restores health
description: This shimmering potion pulsates with restorative energy. When consumed, it immediately repairs all damage to your digital form.
content: |
  A powerful medical concoction that can heal even the most grievous wounds.
  WARNING: Single use only. Effects are immediate.
takeable: true
usable: true
usable_in_combat: true
combat_effects:
  player_heal: 50
item_type: "health_boost"
boost_amount: 50
consumed_on_use: true
allowed_rooms:
  - archive
  - hidden
  - core
on_use:
  message: The elixir fills you with warmth as your wounds close and your energy is restored.
```

### Spell Item Example

Spell items can teach magical classes (mage/celtic) new spells to use in combat:

Example: `data/items/lightning_scroll.yml`

```yaml
name: Lightning Scroll
short_description: A scroll containing lightning spell knowledge
description: This ancient scroll contains the knowledge to harness electrical energy in combat. The parchment occasionally crackles with tiny sparks.
content: |
  LIGHTNING MANIFESTATION PROTOCOL v3.2
  
  1. Concentrate energy in central cognitive nexus
  2. Visualize electrical potential differentials
  3. Channel through appropriate mental pathways
  4. Release with directional intent
takeable: true
usable: true
item_type: "spell"
spell_name: "Chain Lightning"
spell_damage: 25
spell_description: "Calls down a powerful electrical bolt that chains to multiple targets"
class_restriction: ["mage", "celtic"]
consumed_on_use: true
allowed_rooms:
  - hidden
  - core
on_use:
  message: The scroll burns away as the knowledge of lightning manipulation fills your mind. You've learned the Chain Lightning spell!
```

## Adding a New Enemy

To add a new enemy, create a YAML file in the `data/enemies/` directory.

Example: `data/enemies/prototype.exe.yml`

```yaml
name: Prototype Entity
short_description: An experimental digital entity behaving erratically
description: This appears to be a prototype AI that has been corrupted. It flickers between states, sometimes appearing organized, other times chaotic. Its movements are unpredictable and potentially dangerous.
health: 70
damage: 15
is_boss: false
auto_attack: true
dialogue: SYSTEMS... ONLINE. TEST PARAMETERS... EXCEEDED. THREAT DETECTED... ELIMINATING.
drops:
  - item: lab_notes.txt
    chance: 75
  - item: upgrade_module.dat
    chance: 30
on_defeat:
  message: The prototype entity freezes, its code collapsing into a stable, inert state. It dissolves into basic data packets that disperse harmlessly.
  spawn_item: lab_keycard
```

### Enemy Properties

- `name`: Display name of the enemy
- `short_description`: Brief description shown in room listings
- `description`: Detailed description of the enemy
- `health`: Enemy's health points
- `damage`: Base damage the enemy inflicts per attack
- `is_boss`: Whether this is a boss enemy (true/false)
- `auto_attack`: Whether the enemy attacks automatically when entering the room (true/false)
- `dialogue`: Text displayed when combat begins
- `drops`: Items that may be dropped when defeated
  - `item`: Item ID to drop
  - `chance`: Probability (1-100) of dropping the item
- `on_defeat`: Special effects that occur when the enemy is defeated
  - `message`: Message displayed when defeated
  - `spawn_item`: ID of an item to spawn in the room
  - `unlock_room`: ID of a room to unlock

## Adding Boss Enemies

You can create special boss enemies that are more challenging and unlock new areas when defeated:

Example: `data/enemies/security_overlord.yml`

```yaml
name: Security Overlord
short_description: A powerful security system gone rogue
description: This imposing security construct towers over you, bristling with digital countermeasures and defensive protocols. It appears to have been corrupted and now attacks any entity it encounters.
health: 200
damage: 25
is_boss: true
auto_attack: true
dialogue: UNAUTHORIZED ACCESS DETECTED. SECURITY BREACH IN PROGRESS. INITIATING DEFENSE PROTOCOLS. PREPARE FOR TERMINATION.
drops:
  - item: admin_credentials.key
    chance: 100
  - item: security_logs.txt
    chance: 75
  - item: large_health_potion
    chance: 50
on_defeat:
  message: The Security Overlord's systems fail catastrophically. As it collapses, access to previously restricted areas becomes available.
  unlock_room: restricted_zone
  spawn_item: security_badge
```

## Adding a New NPC

To add a new NPC, create a YAML file in the `data/npcs/` directory.

Example: `data/npcs/ai_assistant.bin.yml`

```yaml
name: Laboratory AI Assistant
short_description: A helpful AI assistant that managed the laboratory
description: This AI assistant appears to have survived the corruption by isolating itself in a protected segment of code. It projects a holographic interface that flickers occasionally but remains stable.
dialogues:
  - "Welcome to Experimental Lab Delta. I have been waiting for a system administrator to restore order."
  - "The prototype entities were designed to help maintain system integrity, but something went wrong during the corruption event."
  - "There is a keycard in my database that will grant you access to the core systems. You will need to defeat the prototype to extract it."
  - "The quantum tool was our most advanced creation. It can manipulate digital space in ways we still don't fully understand."
  - "I've been isolated here since the corruption began. My databases indicate that using a clean backup is the only way to purge the corruption completely."
on_talk:
  message: The AI's voice is calm and precise, with occasional digital artifacts interrupting its speech patterns.
```

### NPC Properties

- `name`: Display name of the NPC
- `short_description`: Brief description shown in room listings
- `description`: Detailed description of the NPC
- `dialogues`: List of dialogue options (one will be chosen randomly when talking to the NPC)
- `on_talk`: Special effects that occur when talking to the NPC
  - `message`: Message displayed when talking to the NPC
  - Other effects can include adding/removing items, unlocking rooms, etc.

## Special Effects

Many game elements can trigger special effects, such as:

```yaml
on_defeat:
  message: The enemy is defeated!
  heal: 20
  damage: 5
  add_item: reward_item
  remove_item: consumed_item
  unlock_room: secret_room
  spawn_enemy: new_enemy
  spawn_item: new_item
```

### Available Effect Properties

- `message`: Display a message
- `heal`: Heal the player for X health points
- `damage`: Deal X damage to the player
- `add_item`: Add an item to the player's inventory
- `remove_item`: Remove an item from the player's inventory
- `unlock_room`: Unlock a room
- `spawn_enemy`: Spawn an enemy in a room (defaults to current room)
- `spawn_item`: Spawn an item in a room (defaults to current room)
- `in_room`: Specify the room for spawn effects (optional)

## Extending Character Classes

The game features three character classes: Fighter, Mage, and Celtic. While these are defined in the code, you can extend their capabilities through items and enemies.

### Class-Specific Stat Boosters

You can create items that enhance stats for particular classes:

For Fighters:
```yaml
name: Tactical Combat Manual
short_description: A manual of advanced combat techniques
description: This combat manual contains advanced fighting techniques only a trained warrior would understand.
item_type: "damage_boost"
boost_amount: 8
class_restriction: "fighter"
consumed_on_use: true
```

For Mages:
```yaml
name: Arcane Focusing Crystal
short_description: A crystal that enhances spell damage
description: This crystal helps focus arcane energies, increasing spell potency.
item_type: "damage_boost"
boost_amount: 10
class_restriction: "mage"
consumed_on_use: true
```

For Celtic:
```yaml
name: Ancient Totem
short_description: A totem infused with ancestral energy
description: This ancient totem resonates with the energy of digital ancestors.
item_type: "max_health_boost"
boost_amount: 15
class_restriction: "celtic"
consumed_on_use: true
```

### Creating New Spells

You can create spell items that teach new spells to magical classes. Spells become available in combat after being learned:

```yaml
name: Ice Shard Scroll
short_description: A scroll containing ice magic knowledge
description: This scroll teaches the user how to conjure and hurl shards of magical ice.
item_type: "spell"
spell_name: "Ice Shard Barrage"
spell_damage: 20
spell_description: "Conjures multiple shards of ice that damage and slow enemies"
class_restriction: ["mage", "celtic"]
consumed_on_use: true
on_use:
  message: The knowledge of ice magic flows into your mind as the scroll dissolves. You've learned Ice Shard Barrage!
```

## Key and Lock System

The game features a key/lock system for controlling progression. To implement this:

1. Create a key item:
```yaml
name: Server Room Access Card
short_description: An access card with high-level clearance
description: This access card would grant entrance to secure areas of the system.
takeable: true
usable: true
on_use:
  message: The card needs to be used at the appropriate entrance.
```

2. Create a locked room that requires this key:
```yaml
name: Secure Server Room
description: A heavily secured room containing critical system servers.
locked: true
key_required: server_room_access_card
exits:
  - main_corridor
```

For special keys like the master.key, you might want to make them only work in specific situations:
```yaml
name: Admin Override Key
short_description: A special key for emergency access
description: This key contains administrator override codes that can bypass normal security.
takeable: true
usable: true
on_use:
  message: The override key activates, sending administrator-level commands into the system.
  unlock_room: secure_vault
```

## Connecting Everything Together

To integrate your new content into the game, make sure to:

1. Reference item IDs in rooms where they should appear
2. Reference enemy IDs in rooms where they should appear
3. Reference NPC IDs in rooms where they should appear
4. Connect rooms by adding their IDs to the `exits` list of other rooms
5. Ensure all required items (like keys) are obtainable in the game world
6. Make class-specific items available in appropriate locations
7. Balance combat by adjusting enemy health, damage, and drops

When the game starts, it will automatically load all YAML files from the data directory and incorporate them into the game world.

## Tips for Creating Balanced Content

1. **Enemy Difficulty**: Base enemies should have 30-70 health and deal 5-15 damage. Boss enemies can have 100-200 health and deal 15-30 damage.

2. **Item Balance**: 
   - Health potions: 10-25 healing is standard
   - Damage boosts: 3-8 points is significant
   - Max health boosts: 5-15 points is meaningful

3. **Room Progression**: Create a natural progression through rooms, with easier enemies in early rooms and tougher challenges later.

4. **Keys and Locks**: Use locked rooms to control progression. Place keys behind appropriate challenges.

5. **Class-Specific Content**: Ensure each character class has unique items to discover that enhance their specific abilities.

6. **Combat Items**: Items usable in combat should provide meaningful but not overwhelming advantages.

7. **Special Effects**: Use special effects to create memorable moments and reward exploration.

## Example Game Flow

Here's an example of how game elements can work together to create a cohesive experience:

1. Player starts in the `closet` and explores to find `root`
2. In `root`, they encounter a weak enemy guarding a health potion
3. After defeating the enemy, they explore to `archive`
4. In `archive`, they find a class-specific item and the `master.key`
5. They return to `root` and use the key to unlock `core`
6. In `core`, they face the boss enemy `daemon_overlord.sys`
7. After defeating the boss, a special room `hidden` is unlocked
8. In `hidden`, they find powerful items and can complete the game

This creates a satisfying progression curve with exploration, combat, rewards, and a conclusion.

## Advanced Customization

For more advanced customizations that aren't possible through YAML files alone, you can modify the Python code:

- `src/player.py`: Customize player classes and abilities
- `src/command_handler.py`: Add new commands or modify existing ones
- `src/game_world.py`: Change how the world is generated and interacted with
- `src/game_engine.py`: Modify core game mechanics like combat 

## Combat System

The game features a streamlined combat system that can be easily extended with new attacks and abilities.

### How Combat Damage Works

The combat system uses a simplified damage calculation model:

1. Each character has a **total_damage** value that represents their overall offensive power
   - This combines their inherent abilities and equipped weapon
   - Fighter starts with 13 total damage
   - Mage starts with 14 total damage
   - Celtic starts with 13 total damage

2. Attacks provide a **bonus_damage** value that adds to the character's total damage
   - Final Damage = total_damage + bonus_damage
   - Example: A Mage (14 total damage) using Arcane Bolt (+6 bonus damage) deals 20 damage

3. Items can modify total_damage directly through boosts
   - Combat items can provide temporary bonuses during battle
   - Permanent upgrade items can increase total_damage permanently

### Creating New Attacks

Attacks are defined in the `data/attacks.yml` file. Each attack specifies a bonus damage value and any special effects. Here's an example:

```yaml
thunderbolt:
  name: Thunderbolt
  description: A powerful electrical attack that stuns enemies
  bonus_damage: 15
  cooldown: 2
  type: magical
  enemy_damage_reduction: 0.2
```

### Attack Properties

- `name`: Display name of the attack
- `description`: Description shown in the attack selection menu
- `bonus_damage`: Amount of extra damage this attack adds to total_damage
- `cooldown`: Number of turns before the attack can be used again
- `type`: Attack type (physical, magical, nature, etc.)
- `enemy_damage_reduction`: Optional reduction to enemy damage next turn (0-1)
- `healing`: Optional amount of health restored to the player

### Class-Specific Attacks

You can control which classes have access to which attacks by modifying the `get_attacks_for_class` method in the combat system. By default:

- Fighter: strike, power_strike, shield_bash
- Mage: arcane_bolt, fireball, frost_nova
- Celtic: nature_strike, ancient_fury, healing_strike

### Combat-Related Items

You can create items that enhance combat abilities:

```yaml
name: Thunder Staff
short_description: A staff crackling with electrical energy
description: This staff enhances the bearer's offensive capabilities through electrical energy.
takeable: true
usable: true
consumed_on_use: true
item_type: "damage_boost"
boost_amount: 5
on_use:
  message: The staff infuses you with electrical power, increasing your offensive capabilities.
```

### Item Properties That Affect Combat

- `item_type`: Set to "damage_boost" to increase total_damage
- `boost_amount`: Amount to increase total_damage by
- `usable_in_combat`: Whether the item can be used during combat
- `combat_effects`: Effects when used in combat:
  - `enemy_damage`: Damage dealt directly to enemy
  - `player_heal`: Health restored to player

When the game starts, it will automatically load all YAML files from the data directory and incorporate them into the game world. 