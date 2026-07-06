"""Auto-tuner: calibrate each mode's multipliers to its win-rate band.

For each mode we hold sensible HP/XP presets (so modes feel distinct) and
bisect the enemy-damage multiplier — the strongest, monotonic lever — until the
AVERAGE win rate across the (now-comparable) classes lands in the target band.

Output is a *proposal*: a report + data/difficulty.proposed.yaml. A human
reviews and, if happy, copies it over data/difficulty.yaml. The tuner never
edits the live config (see docs/DIFFICULTY_SIM_DESIGN.md).

    python -m sim.tune --mode all --runs 60
"""
from __future__ import annotations

import argparse
import statistics

import yaml

from src import difficulty
from sim.simulator import measure

CLASSES = ["guardian", "weaver", "shaman"]

# Target average win-rate bands per mode.
BANDS = {
    "easy": (0.90, 0.98),
    "medium": (0.75, 0.85),
    "hard": (0.50, 0.70),
}

# Fixed per-mode presets that give each mode its own texture; the tuner moves
# only enemy_damage to hit the band.
HP_PRESET = {"easy": 0.85, "medium": 0.95, "hard": 1.15}
XP_PRESET = {"easy": 1.30, "medium": 1.00, "hard": 0.85}

DMG_LO, DMG_HI = 0.40, 2.00  # enemy-damage multiplier search bounds
MAX_STEPS = 8


def _avg_win(mode: str, runs: int, seed: int) -> float:
    return statistics.fmean(
        measure(cls, mode, runs=runs, seed=seed).win_rate for cls in CLASSES
    )


def tune_mode(mode: str, runs: int, seed: int) -> dict[str, float]:
    """Bisect enemy_damage to land avg win rate in the mode's band."""
    low_win = BANDS[mode][0]
    high_win = BANDS[mode][1]
    hp = HP_PRESET[mode]
    xp = XP_PRESET[mode]

    lo, hi = DMG_LO, DMG_HI
    dmg = (lo + hi) / 2
    win = 0.0
    for _ in range(MAX_STEPS):
        dmg = round((lo + hi) / 2, 3)
        difficulty.set_mode_multipliers(mode, hp, dmg, xp)
        win = _avg_win(mode, runs, seed)
        if low_win <= win <= high_win:
            break
        if win > high_win:      # too easy -> stronger enemies
            lo = dmg
        else:                   # too hard -> weaker enemies
            hi = dmg

    return {"enemy_hp": hp, "enemy_damage": dmg, "xp_gain": xp, "_avg_win": win}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sim.tune")
    parser.add_argument("--mode", default="all", help="easy|medium|hard|all")
    parser.add_argument("--runs", type=int, default=60, help="runs/class per measurement")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="data/difficulty.proposed.yaml")
    args = parser.parse_args(argv)

    modes = list(BANDS) if args.mode == "all" else [args.mode]

    print(f"# tuning {modes} — {args.runs} runs/class, band = target avg win rate")
    proposal: dict[str, dict[str, float]] = {}
    for mode in modes:
        result = tune_mode(mode, args.runs, args.seed)
        win = result.pop("_avg_win")
        proposal[mode] = result
        band = BANDS[mode]
        status = "OK " if band[0] <= win <= band[1] else "OUT"
        print(
            f"  {mode:<6} avg win {win * 100:5.1f}%  [{status}]  "
            f"hp={result['enemy_hp']}  dmg={result['enemy_damage']}  xp={result['xp_gain']}"
        )

    # Merge with existing modes not tuned this run, then write the proposal.
    full = difficulty.all_multipliers()
    full.update(proposal)
    with open(args.out, "w") as fh:
        fh.write("# PROPOSED difficulty multipliers (sim.tune). Review, then copy\n")
        fh.write("# over data/difficulty.yaml if the numbers look right.\n")
        yaml.safe_dump(full, fh, sort_keys=False)
    print(f"\nProposal written to {args.out} (not applied). Review + copy to data/difficulty.yaml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
