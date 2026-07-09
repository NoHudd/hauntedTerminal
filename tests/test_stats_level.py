"""StatsView must expose the player's level + XP so the stats panel can show it (#4)."""
from __future__ import annotations

from src.player import Player
from src.viewmodels.view_builder import ViewBuilder


def test_stats_view_includes_level_and_cycles():
    p = Player("T", "guardian", "home_grove")
    p.level = 3
    p.harvesting_cycles = 45
    p.cycles_to_next_level = 150

    sv = ViewBuilder.build_stats_view(p)
    d = sv.to_dict()
    assert d["level"] == 3
    assert d["cycles"] == 45
    assert d["cycles_to_next"] == 150
