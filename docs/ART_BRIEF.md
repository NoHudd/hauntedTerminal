# HFSE Art Brief — pixel sprites for the terminal

Hand this to anyone making art. No coding knowledge needed.

## The one rule

**Save a PNG with the right name into the right folder. That's it.**
The game finds it by filename on next launch — no code, no config. Until your file
exists, the game shows an auto-generated colored box (that's what's in the game now).

## How it looks in the game

The terminal renders 2 pixels per character cell using half-block characters, in full
color. Practical meaning:

- Art displays at **half its pixel height** in terminal rows (a 24 px-tall sprite ≈ 12 rows).
- Pixels are **tall rectangles on screen, not squares** (a cell is ~1:2). Circles will
  look slightly stretched vertically — test in-game before polishing.
- Fine detail below ~2 px is lost. Bold shapes, strong silhouettes, high contrast win.

## File format

| Property | Requirement |
|---|---|
| Format | PNG, RGBA (keep transparency) |
| Background | **Transparent** for characters (real alpha — NOT a baked checkerboard/white); opaque for backdrops |
| Characters (enemies, NPCs, classes) | **exactly 24×24 px** (displayed 1:1 in battle — no resize, no quality loss) |
| Menu/UI cards (`ui/`) | **exactly 40×40 px** (displayed 1:1 on selection cards) |
| Backdrops | **~100×36 px**, opaque, stretched to fit — keep it abstract/texture-like |
| Style | True pixel grid, flat colors, **no anti-aliasing / dithering / gradients**, ≤16 colors, dark outline, oversized props |
| Palette | Free choice; dark-terminal friendly (avoid pure black shapes on transparent) |
| Tools | Aseprite, Piskel (free, browser), Pixilart — anything that exports PNG |

**Using an AI generator?** Prompt with: "true pixel art on a native 64×64 grid, each
pixel one cell, no anti-aliasing, no dithering, flat colors, max 16 colors, bold dark
outline, key props oversized (shield/weapon ~40% of silhouette), front-facing, single
character, centered, transparent background, no drop shadow." Then downscale to the
exact sizes above in a pixel editor yourself — oversized art dropped straight in gets
resampled by tooling and picks up wobble/fringe.

## Where files go (`assets/sprites/`)

```
assets/sprites/
  classes/<class_id>.png        player characters
  enemies/<enemy_id>.png        file name = enemy id, DOTS INCLUDED
  npcs/<npc_id>.png
  backdrops/<zone>.png          room background per zone
  backdrops/rooms/<room_id>.png optional: unique background for one specific room
  ui/                           menu art (logo, class/difficulty cards)
```

⚠ Filenames must match EXACTLY, including dots: `corrupt_process.bin.png`, not
`corrupt_process.png`.

## Testing your art

1. Drop the PNG in the folder.
2. Run the game (`python main.py`), walk to a room with that entity (or start a fight).
3. Not showing? Filename mismatch — check against the lists below.

## Asset checklist — ✅ COMPLETE (2026-07-10)

Every base-game asset is in: **24/24 enemies · 12/12 NPCs · 3/3 classes (+card
versions) · 3/3 difficulty cards · 8/8 zone backdrops · logo.**

What's still open for artists:
- **Per-room backdrop overrides** (`backdrops/rooms/<room_id>.png`) — optional polish;
  any specific room can get unique art that beats its zone backdrop.
- **Frame animation** — see "Later" below; not shipped yet.
- **Redraws** — any sprite can be replaced anytime by overwriting its PNG.

## Style direction (suggestion, not law)

Haunted filesystem: ghosts of dead processes, corrupted data, Unix-flavored horror
with warmth. Think Pokemon Gen 1/2 sprite energy — readable silhouette, personality
over detail. Enemies skew glitchy/corrupted (harsh edges, error-red/magenta accents);
NPCs skew soft/ghostly (cool blues, translucency via partial alpha works in-game).

## What the game adds for free (don't draw these)

- Attack lunge, hit flash (white), damage/heal numbers, HP bars, name tags
- Placeholder boxes for anything not yet drawn
- Scaling — oversized art is shrunk (crisply, no blur), but drawing at target size looks best

## Later (don't do yet)

Frame animation (idle bob, attack pose) is designed-for but not shipped — one static
PNG per entity for now. When it lands the convention will extend to
`<id>/idle_1.png`-style folders; single PNGs will keep working.
