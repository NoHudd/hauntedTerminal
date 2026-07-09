# Sprite assets

Drop PNGs here; the game picks them up by filename — no code changes.

| Folder | Filename | Example |
|---|---|---|
| `classes/` | `<class_id>.png` | `guardian.png` |
| `enemies/` | `<enemy_id>.png` (ids keep dots) | `corrupt_process.bin.png` |
| `npcs/` | `<npc_id>.png` | `oracle.db.png` |
| `backdrops/` | `<zone>.png` | `dangerous.png` |
| `backdrops/rooms/` | `<room_id>.png` (overrides the zone backdrop) | `var_dungeon.png` |
| `ui/` | menu art | `logo.png`, `class_guardian.png`, `difficulty_easy.png` |

Guidelines: RGBA PNG, transparent background for characters. Terminal cells are
1 px wide × 2 px tall, so art displays at half its pixel height in rows.
Characters: ~24×24 px. Backdrops: ~100×36 px (they get resized to fit).
Missing files are fine — the game draws a colored placeholder until art exists.
