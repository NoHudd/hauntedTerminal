"""Sound effects: playback backends, generated files, and the event board."""
from __future__ import annotations

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
    import wave

    assert P.SOUNDS_DIR.is_absolute()
    for name in NAMES:
        with wave.open(str(P.SOUNDS_DIR / f"{name}.wav")) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 22050)
            assert 0 < w.getnframes() / w.getframerate() <= 1.5
