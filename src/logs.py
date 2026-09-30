"""Generated log files: hundreds of look-alike lines with one flag line.

Deterministic per item (seeded by its id), so the same log reads the same
every run and in every test. Uses its own Random, not src.rng, so reading a
log never shifts the game's seeded dice.
"""
from __future__ import annotations

import random
from typing import Any


def log_lines(item: Any) -> list[str]:
    spec = item.log
    rnd = random.Random(str(item.id))
    flag_at = spec.lines * 2 // 3
    out: list[str] = []
    for i in range(spec.lines):
        template = spec.flag_line if i == flag_at else rnd.choice(spec.templates)
        ts = f"03:{i // 60:02d}:{i % 60:02d}"
        out.append(template.replace("{ts}", ts).replace("{n}", str(rnd.randint(1, 99))))
    return out
