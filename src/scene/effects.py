"""
Effects — pure timeline math for battle animation.

No Textual, no PIL: given a time t since the effect started, return where a
sprite should be / whether it should flash. SceneView owns the clock and calls
these every tick. All durations in seconds.
"""
from dataclasses import dataclass

LUNGE_SECONDS = 0.4
FLASH_SECONDS = 0.5
FLASH_PERIOD = 0.1   # on/off toggle interval
HP_DRAIN_SECONDS = 0.4
LUNGE_MAX_PX = 10
BOB_PERIOD = 1.6     # idle bob: full up/down cycle


@dataclass(frozen=True)
class FxState:
    """Per-frame effect offsets applied by the compositor. dx = px toward opponent,
    dy = px of idle-bob lift."""
    player_dx: int = 0
    enemy_dx: int = 0
    player_flash: bool = False
    enemy_flash: bool = False
    player_dy: int = 0
    enemy_dy: int = 0


def lunge_offset(t: float, duration: float = LUNGE_SECONDS, max_px: int = LUNGE_MAX_PX) -> int:
    """Triangle wave: dash toward the opponent and snap back."""
    if t <= 0 or t >= duration:
        return 0
    half = duration / 2
    frac = t / half if t < half else (duration - t) / half
    return round(max_px * frac)


def flash_on(t: float, duration: float = FLASH_SECONDS) -> bool:
    """Blink: on for FLASH_PERIOD, off for FLASH_PERIOD, while t < duration."""
    if t < 0 or t >= duration:
        return False
    return int(t / FLASH_PERIOD) % 2 == 0


def bob_offset(t: float, period: float = BOB_PERIOD) -> int:
    """Idle bob: 2-frame square wave — up (1 px) half the period, down the other."""
    return 1 if (t % period) < period / 2 else 0


def approach(current: float, target: float, dt: float, seconds: float = HP_DRAIN_SECONDS) -> float:
    """Move `current` toward `target`, covering the full gap in `seconds`."""
    if current == target:
        return target
    step = abs(current - target) * min(1.0, dt / seconds) if seconds > 0 else abs(current - target)
    # Guarantee progress even for tiny gaps so we terminate.
    step = max(step, 1.0 * dt / max(seconds, dt))
    if current > target:
        return max(target, current - step)
    return min(target, current + step)
