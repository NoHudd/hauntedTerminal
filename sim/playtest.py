"""Playtest simulation CLI.

    python -m sim.playtest measure --mode medium --runs 200
    python -m sim.playtest measure --mode all --class all --runs 200

Reports win rate + difficulty stats per (mode, class). See
docs/DIFFICULTY_SIM_DESIGN.md.
"""
from __future__ import annotations

import argparse
import sys

from sim.simulator import Measurement, measure

CLASSES = ["guardian", "weaver", "shaman"]
MODES = ["easy", "medium", "hard"]


def _format(m: Measurement) -> str:
    top_deaths = ", ".join(f"{eid}×{n}" for eid, n in list(m.deaths_by_enemy.items())[:3])
    return (
        f"{m.mode:<6} {m.player_class:<9} "
        f"win {m.win_rate * 100:5.1f}%  "
        f"cleared {m.avg_cleared:4.1f}  "
        f"end-HP {m.avg_ending_hp * 100:5.1f}%  "
        f"deaths[{top_deaths or '-'}]"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sim.playtest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    mp = sub.add_parser("measure", help="measure difficulty per mode/class")
    mp.add_argument("--mode", default="medium", help="easy|medium|hard|all")
    mp.add_argument("--class", dest="cls", default="all", help="guardian|weaver|shaman|all")
    mp.add_argument("--runs", type=int, default=200)
    mp.add_argument("--seed", type=int, default=0)

    args = parser.parse_args(argv)

    if args.cmd == "measure":
        modes = MODES if args.mode == "all" else [args.mode]
        classes = CLASSES if args.cls == "all" else [args.cls]
        print(f"# {args.runs} runs/cell, seed base {args.seed}")
        for mode in modes:
            for cls in classes:
                print(_format(measure(cls, mode, args.runs, args.seed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
