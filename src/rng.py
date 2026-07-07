#!/usr/bin/env python3
"""Central seedable RNG for gameplay.

All gameplay randomness (loot placement, combat rolls, dialogue picks) goes
through this one source so a run can be made reproducible — the simulation
harness seeds it per run for deterministic measurements, and a future
player-facing "enter a seed" feature is a small addition on top. See
docs/DIFFICULTY_SIM_DESIGN.md.

Interactive play leaves it unseeded (system entropy), matching prior behavior.
"""
from __future__ import annotations

import random as _random
from typing import Any, Sequence

# Single shared generator. Not seeded by default → non-deterministic like before.
_rng = _random.Random()


def seed(value: int | str | None) -> None:
    """Seed the shared generator (None re-seeds from system entropy)."""
    _rng.seed(value)


def get_rng() -> _random.Random:
    """The underlying Random instance (for callers that need the object)."""
    return _rng


# Thin pass-throughs mirroring the stdlib random API used across gameplay.
def shuffle(seq: list) -> None:
    _rng.shuffle(seq)


def choice(seq: Sequence[Any]) -> Any:
    return _rng.choice(seq)


def choices(population: Sequence[Any], weights: Sequence[float] | None = None,
            k: int = 1) -> list:
    return _rng.choices(population, weights=weights, k=k)


def randint(a: int, b: int) -> int:
    return _rng.randint(a, b)


def random() -> float:
    return _rng.random()


def sample(population: Sequence[Any], k: int) -> list:
    return _rng.sample(list(population), k)
