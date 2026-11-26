"""Sound effects: playback backends, generated files, and the event board."""
from __future__ import annotations

import wave

import pytest

from engine.events import EventBus
from engine.events import EventType as E
from src.sound import player as P


class FakeProc:
    def __init__(self, done: bool = False) -> None:
        self.done = done

    def poll(self) -> int | None:
        return 0 if self.done else None


def test_make_player_picks_backend_per_platform(monkeypatch):
    monkeypatch.setattr(P, "ENABLED", True)

    def have(*names):
        return lambda n: f"/bin/{n}" if n in names else None

    assert P.make_player("darwin", have("afplay"))._argv == ["afplay"]
    assert P.make_player("linux", have("paplay", "aplay"))._argv == ["paplay"]
    assert P.make_player("linux", have("aplay"))._argv == ["aplay", "-q"]
    assert isinstance(P.make_player("linux", have()), P.SilentPlayer)
    monkeypatch.setattr(P, "ENABLED", False)
    assert isinstance(P.make_player("darwin", have("afplay")), P.SilentPlayer)


def test_command_player_caps_concurrent_sounds():
    spawned = []

    def spawn(argv):
        spawned.append(argv)
        return FakeProc()

    p = P.CommandPlayer(["afplay"], spawn=spawn)
    for _ in range(P.MAX_CONCURRENT + 3):
        p.play("hit")
    assert len(spawned) == P.MAX_CONCURRENT
    assert spawned[0] == ["afplay", str(P.SOUNDS_DIR / "hit.wav")]


def test_backend_failure_is_swallowed():
    def spawn(argv):
        raise OSError("no audio device")

    P.CommandPlayer(["afplay"], spawn=spawn).play("hit")  # must not raise


NAMES = ["step", "alert", "hit", "hurt", "heal", "defeat", "gameover", "victory"]


def test_all_sounds_exist_and_are_short():
    assert P.SOUNDS_DIR.is_absolute()
    for name in NAMES:
        with wave.open(str(P.SOUNDS_DIR / f"{name}.wav")) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 22050)
            assert 0 < w.getnframes() / w.getframerate() <= 1.5


class Recorder:
    def __init__(self) -> None:
        self.played: list[str] = []

    def play(self, name: str) -> None:
        self.played.append(name)


@pytest.mark.parametrize("etype,data,expected", [
    (E.ROOM_ENTERED, {}, "step"),
    (E.COMBAT_STARTED, {}, "alert"),
    (E.COMBAT_ACTION_RESULT, {"actor": "player", "damage": 7}, "hit"),
    (E.COMBAT_ACTION_RESULT, {"actor": "enemy", "damage": 3}, "hurt"),
    (E.COMBAT_ACTION_RESULT, {"actor": "player", "damage": 0, "healing": 5}, "heal"),
    (E.COMBAT_ACTION_RESULT, {"actor": "player", "damage": 0}, None),
    (E.COMBAT_ACTION_RESULT, {"actor": "system", "damage": 0}, None),
    (E.ENEMY_DEFEATED, {}, "defeat"),
    (E.GAME_OVER, {"reason": "defeat"}, "gameover"),
    (E.GAME_OVER, {"reason": "menu"}, None),
    (E.GAME_WON, {}, "victory"),
])
def test_board_maps_events(etype, data, expected):
    from src.sound.board import SoundBoard

    bus, rec = EventBus(), Recorder()
    SoundBoard(rec, lambda: True).attach(bus)
    bus.emit_event(etype, data, "test")
    assert rec.played == ([expected] if expected else [])


def test_board_silent_when_disabled_and_after_detach():
    from src.sound.board import SoundBoard

    bus, rec, on = EventBus(), Recorder(), [True]
    board = SoundBoard(rec, lambda: on[0])
    board.attach(bus)
    on[0] = False
    bus.emit_event(E.ROOM_ENTERED, {}, "test")
    on[0] = True
    board.detach()
    bus.emit_event(E.ROOM_ENTERED, {}, "test")
    assert rec.played == []


def test_sound_setting_defaults_on_and_has_a_row(tmp_path):
    from config.settings_manager import SettingsManager
    from src.ui.screens.settings_screen import ROWS

    m = SettingsManager(str(tmp_path / "s.json"))
    m.load()
    assert m.settings["sound"] is True
    row = next(r for r in ROWS if r.key == "sound")
    assert (row.label, row.values, row.names) == ("Sound", (True, False), ("On", "Off"))
    row.apply(m, False)
    assert m.settings["sound"] is False
