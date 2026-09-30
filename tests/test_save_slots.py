"""One save slot per run: saves overwrite the run's own file, the picker lists
runs, a replaced run survives until the new run's first save."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

import src.save as save_mod
from engine.api import GameSession
from src.player import Player
from src.save import MAX_RUNS, SAVE_VERSION, SaveManager


@pytest.fixture
def session() -> Iterator[GameSession]:
    s = GameSession()
    s.new_game("Slotty", "guardian")
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def mgr(tmp_path: Path) -> SaveManager:
    return SaveManager(save_dir=str(tmp_path))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every save gets a later timestamp, so newest-first order is exact."""
    ticks = iter(range(1000, 100000, 10))
    monkeypatch.setattr(save_mod, "_now", lambda: float(next(ticks)))


def _save(mgr: SaveManager, s: GameSession) -> str:
    return mgr.save_game(s.player, s.world.get_state())


def test_saves_in_one_run_overwrite_one_file(mgr, session, tmp_path, clock) -> None:
    mgr.begin_run()
    first = json.loads(Path(_save(mgr, session)).read_text())
    session.submit("cd root")
    _save(mgr, session)

    files = list(tmp_path.glob("run_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["runId"] == mgr.active_run_id
    assert data["createdAt"] == first["createdAt"]
    assert data["savedAt"] > first["savedAt"]
    assert data["player"]["current_room"] == session.player.current_room


def test_two_new_games_are_two_slots_even_with_the_same_hero(mgr, session) -> None:
    mgr.begin_run()
    _save(mgr, session)
    mgr.begin_run()
    _save(mgr, session)
    assert len(mgr.list_runs()) == 2


def test_saving_with_no_run_in_progress_starts_one(mgr, session) -> None:
    assert mgr.active_run_id is None
    _save(mgr, session)
    assert mgr.active_run_id is not None
    assert [r.run_id for r in mgr.list_runs()] == [mgr.active_run_id]


def test_envelope_is_v6_and_camelcase(mgr, session) -> None:
    raw = json.loads(Path(_save(mgr, session)).read_text())
    assert raw["version"] == SAVE_VERSION == 6
    for key in ("runId", "createdAt", "cleared", "savedAt", "saveDate", "difficulty"):
        assert key in raw
    assert raw["cleared"] is False


def test_list_runs_is_newest_first_with_what_the_picker_shows(mgr, session, clock) -> None:
    mgr.begin_run()
    _save(mgr, session)
    older = mgr.active_run_id
    mgr.begin_run()
    _save(mgr, session)
    newer = mgr.active_run_id

    runs = mgr.list_runs()
    assert [r.run_id for r in runs] == [newer, older]
    run = runs[0]
    assert (run.player_name, run.player_class) == ("Slotty", "guardian")
    assert (run.level, run.room_id) == (session.player.level, session.player.current_room)
    assert (run.health, run.max_health) == (session.player.health, session.player.max_health)
    assert run.cleared is False


def test_replace_happens_on_the_new_runs_first_save(mgr, session) -> None:
    mgr.begin_run()
    _save(mgr, session)
    old = mgr.active_run_id

    mgr.begin_run(replace=old)
    assert [r.run_id for r in mgr.list_runs()] == [old]  # backing out now loses nothing

    _save(mgr, session)
    assert [r.run_id for r in mgr.list_runs()] == [mgr.active_run_id]
    assert mgr.pending_replace is None


def test_resuming_a_run_cancels_a_pending_replace(mgr, session) -> None:
    mgr.begin_run()
    _save(mgr, session)
    old = mgr.active_run_id
    mgr.begin_run(replace=old)
    mgr.resume_run(old)
    _save(mgr, session)
    assert [r.run_id for r in mgr.list_runs()] == [old]


def test_end_run_clears_the_run_in_progress(mgr) -> None:
    mgr.begin_run(replace="abc")
    mgr.end_run()
    assert (mgr.active_run_id, mgr.pending_replace) == (None, None)


def test_runs_full_at_nine(mgr, session) -> None:
    assert MAX_RUNS == 9
    for _ in range(MAX_RUNS - 1):
        mgr.begin_run()
        _save(mgr, session)
    assert not mgr.runs_full()
    mgr.begin_run()
    _save(mgr, session)
    assert mgr.runs_full()


def test_mark_cleared_flips_only_the_flag(mgr, session) -> None:
    path = Path(_save(mgr, session))
    before = json.loads(path.read_text())
    mgr.mark_cleared()
    after = json.loads(path.read_text())
    assert after.pop("cleared") is True
    before.pop("cleared")
    assert after == before

    _save(mgr, session)  # a later save keeps the mark
    assert json.loads(path.read_text())["cleared"] is True


def test_delete_run(mgr, session) -> None:
    _save(mgr, session)
    run_id = mgr.active_run_id
    assert mgr.delete_run(run_id) is True
    assert mgr.list_runs() == []
    assert mgr.delete_run(run_id) is False


def test_unreadable_run_file_is_skipped(mgr, session, tmp_path) -> None:
    _save(mgr, session)
    (tmp_path / "run_deadbeef.json").write_text("{not json")
    assert len(mgr.list_runs()) == 1
    assert mgr.load_run("deadbeef") is None


def test_atomic_write_leaves_no_temp_file(mgr, session, tmp_path) -> None:
    _save(mgr, session)
    assert list(tmp_path.glob("*.tmp")) == []


def test_load_run_round_trip(mgr, session) -> None:
    _save(mgr, session)
    loaded = mgr.load_run(mgr.active_run_id)
    assert loaded is not None
    assert Player.from_dict(loaded["player"]).name == "Slotty"
