"""Seedable RNG tests (difficulty-sim Part A′).

Gameplay randomness routes through src.rng so runs are reproducible (the
simulation seeds it per run). These assert the infra is deterministic.
"""
from __future__ import annotations

from src import rng


def test_same_seed_same_sequence() -> None:
    rng.seed(1234)
    a = [rng.randint(1, 100) for _ in range(20)]
    rng.seed(1234)
    b = [rng.randint(1, 100) for _ in range(20)]
    assert a == b


def test_different_seed_diverges() -> None:
    rng.seed(1)
    a = [rng.randint(1, 1_000_000) for _ in range(20)]
    rng.seed(2)
    b = [rng.randint(1, 1_000_000) for _ in range(20)]
    assert a != b


def test_choice_and_shuffle_deterministic() -> None:
    pool = list(range(50))
    rng.seed(99)
    picks_a = [rng.choice(pool) for _ in range(10)]
    seq_a = pool[:]
    rng.shuffle(seq_a)

    rng.seed(99)
    picks_b = [rng.choice(pool) for _ in range(10)]
    seq_b = pool[:]
    rng.shuffle(seq_b)

    assert picks_a == picks_b
    assert seq_a == seq_b


def test_loot_placement_deterministic_for_seed() -> None:
    # Full-stack: same seed -> identical loot placement in a fresh game.
    from engine.api import GameSession

    def placement(seed: int) -> dict:
        rng.seed(seed)
        s = GameSession()
        s.new_game("T", "guardian")
        loc = dict(s.world.item_locations)
        s.close()
        return loc

    assert placement(42) == placement(42)
