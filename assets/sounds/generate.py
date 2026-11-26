"""Generate the game's chiptune sound effects (standard library only).

Run ``python assets/sounds/generate.py`` to rewrite every .wav next to this
script. Output is deterministic (fixed noise seed), so regenerating without
changes leaves git clean. Retune a sound by editing its entry in SOUNDS.

Format: mono, 16-bit, 22050 Hz. Peak level stays at or under 0.35 of full
scale because Windows playback has no volume control.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from collections.abc import Callable
from pathlib import Path

RATE = 22050
PEAK = 0.35
FADE = 0.005  # seconds of fade in/out on every sound, to avoid clicks

# Grit applied to every sound (see grit()). Raise HOLD / HISS or lower BITS
# for dirtier; HOLD 1, BITS 16, HISS 0 is the clean original.
GRIT_HOLD = 4     # ~5.5 kHz effective rate
GRIT_BITS = 5     # 32 levels
GRIT_HISS = 0.25
_GRIT_RNG = random.Random(4242)

# Detune: every tone is pitched a little flat, wobbles, and carries a second
# voice slightly sharp of it, so notes beat and sound sour rather than clean.
# DETUNE_CENTS 0, WOBBLE_DEPTH 0, BEAT_MIX 0 is in tune.
DETUNE_CENTS = -35    # whole-tone offset (100 cents = one semitone)
WOBBLE_HZ = 7.0       # warble speed
WOBBLE_DEPTH = 0.012  # warble width, fraction of pitch
BEAT_RATIO = 1.027    # second voice's pitch relative to the first
BEAT_MIX = 0.45       # second voice's level

Samples = list[float]


def _n(seconds: float) -> int:
    return int(RATE * seconds)


def sweep(f0: float, f1: float, seconds: float, duty: float = 0.5) -> Samples:
    """Detuned square wave gliding from f0 to f1 Hz (f0 == f1 for a steady tone).

    Pitched DETUNE_CENTS off, warbling, with a second voice at BEAT_RATIO.
    """
    out: Samples = []
    phase = beat = 0.0
    n = _n(seconds)
    offset = 2 ** (DETUNE_CENTS / 1200)
    for i in range(n):
        wobble = 1 + WOBBLE_DEPTH * math.sin(2 * math.pi * WOBBLE_HZ * i / RATE)
        f = (f0 + (f1 - f0) * i / max(n - 1, 1)) * offset * wobble
        phase = (phase + f / RATE) % 1.0
        beat = (beat + f * BEAT_RATIO / RATE) % 1.0
        main = 1.0 if phase < duty else -1.0
        second = 1.0 if beat < duty else -1.0
        out.append((main + BEAT_MIX * second) / (1 + BEAT_MIX))
    return out


def square(freq: float, seconds: float, duty: float = 0.5) -> Samples:
    return sweep(freq, freq, seconds, duty)


def noise(seconds: float, rng: random.Random) -> Samples:
    return [rng.uniform(-1.0, 1.0) for _ in range(_n(seconds))]


def decay(samples: Samples, speed: float) -> Samples:
    """Exponential fade; higher speed dies away faster."""
    n = len(samples)
    return [s * math.exp(-speed * i / n) for i, s in enumerate(samples)]


def mix(*tracks: tuple[Samples, float]) -> Samples:
    n = max(len(t) for t, _ in tracks)
    out = [0.0] * n
    for t, gain in tracks:
        for i, s in enumerate(t):
            out[i] += s * gain
    return out


def notes(freqs: list[float], each: float, hold_last: float = 0.0,
          gap: float = 0.01, speed: float = 2.0) -> Samples:
    """A run of short square notes, each decaying, with a tiny gap between."""
    out: Samples = []
    for i, f in enumerate(freqs):
        length = each + (hold_last if i == len(freqs) - 1 else 0.0)
        out += decay(square(f, length - gap), speed) + [0.0] * _n(gap)
    return out


def grit(samples: Samples, rng: random.Random, hold: int = GRIT_HOLD,
         bits: int = GRIT_BITS, hiss: float = GRIT_HISS) -> Samples:
    """Dirty a clean signal: hiss under it, then crush rate and bit depth.

    ``hold`` repeats each sample that many times (fake low sample rate, so
    the tone aliases and buzzes); ``bits`` quantises to 2**bits levels.
    """
    levels = 2 ** (bits - 1)
    out: Samples = []
    held = 0.0
    for i, s in enumerate(samples):
        if i % hold == 0:
            held = s + rng.uniform(-hiss, hiss) * (abs(s) + 0.1)
        out.append(round(max(-1.0, min(1.0, held)) * levels) / levels)
    return out


def finish(samples: Samples, gain: float = 1.0) -> Samples:
    """Grit, normalise to PEAK * gain, and apply the anti-click fades."""
    samples = grit(samples, _GRIT_RNG)
    top = max((abs(s) for s in samples), default=0.0) or 1.0
    scale = PEAK * gain / top
    out = [s * scale for s in samples]
    f = min(_n(FADE), len(out) // 2)
    for i in range(f):
        k = i / f
        out[i] *= k
        out[-1 - i] *= k
    return out


def write_wav(path: Path, samples: Samples) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
        ))


def build(rng: random.Random) -> dict[str, Callable[[], Samples]]:
    return {
        "step": lambda: finish(decay(square(440, 0.06, duty=0.25), 6), 0.6),
        "alert": lambda: finish(notes([330, 494], 0.125, speed=1.5)),
        "hit": lambda: finish(mix(
            (decay(noise(0.12, rng), 7), 0.7),
            (decay(square(180, 0.12), 5), 0.5),
        )),
        "hurt": lambda: finish(decay(sweep(160, 70, 0.20), 3)),
        "heal": lambda: finish(notes([523, 659, 784], 0.10, speed=1.5), 0.8),
        "defeat": lambda: finish(sweep(880, 110, 0.32, duty=0.25)
                                 + decay(noise(0.08, rng), 5)),
        "gameover": lambda: finish(notes([392, 330, 262, 196], 0.30, speed=1.2)),
        "victory": lambda: finish(notes([523, 659, 784, 1047], 0.12,
                                        hold_last=0.42, speed=1.2), 0.9),
    }


def main() -> None:
    here = Path(__file__).resolve().parent
    rng = random.Random(1337)
    for name, make in build(rng).items():
        write_wav(here / f"{name}.wav", make())
        print(f"wrote {name}.wav")


if __name__ == "__main__":
    main()
