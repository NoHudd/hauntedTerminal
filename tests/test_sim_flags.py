"""The sim plays the game the flag hunt made: rogue fights on the main path,
flag XP along the way."""
from sim.gauntlet import main_path_enemy_ids
from sim.simulator import flag_xp_schedule
from src import rng

ROGUES = ("runaway_fork.bomb", "zombie_tmpwatch.sh", "rogue_crond.d")


def test_gauntlet_includes_each_rogue_once() -> None:
    rng.seed(0)
    ids = main_path_enemy_ids()
    for rogue in ROGUES:
        assert ids.count(rogue) == 1, rogue


def test_flag_xp_schedule_sums_to_all_flags() -> None:
    schedule = flag_xp_schedule(20, 12, 15)
    assert len(schedule) == 20
    assert sum(schedule) == 12 * 15
    assert all(x >= 0 for x in schedule)


def test_flag_xp_schedule_handles_short_runs() -> None:
    schedule = flag_xp_schedule(5, 12, 15)
    assert len(schedule) == 5 and sum(schedule) == 180


def test_flag_xp_schedule_with_no_fights() -> None:
    assert flag_xp_schedule(0, 12, 15) == []


def test_rogue_fights_earn_no_gear_progress() -> None:
    """Killing a rogue drops no gear in the game, so it must not advance the
    sim's gear tier (they sort first and would hand out free upgrades)."""
    from sim.simulator import gear_stages

    stages = gear_stages(["r1", "r2", "a", "b"], {"r1", "r2"})
    assert stages == [(0, 2), (0, 2), (0, 2), (1, 2)]
    assert gear_stages(["a", "b"], set()) == [(0, 2), (1, 2)]
