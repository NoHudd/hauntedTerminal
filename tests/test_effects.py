"""Effects: pure timeline math for battle animation."""
from src.scene.effects import (
    FLASH_PERIOD,
    FLASH_SECONDS,
    LUNGE_MAX_PX,
    LUNGE_SECONDS,
    FxState,
    approach,
    flash_on,
    lunge_offset,
)


def test_lunge_starts_and_ends_at_zero():
    assert lunge_offset(0.0) == 0
    assert lunge_offset(LUNGE_SECONDS) == 0
    assert lunge_offset(LUNGE_SECONDS + 1.0) == 0  # long after: settled


def test_lunge_peaks_mid():
    assert lunge_offset(LUNGE_SECONDS / 2) == LUNGE_MAX_PX
    assert 0 < lunge_offset(LUNGE_SECONDS / 4) <= LUNGE_MAX_PX


def test_flash_alternates_then_stops():
    assert flash_on(0.0) is True
    assert flash_on(FLASH_PERIOD * 1.5) is False   # second blink window: off
    assert flash_on(FLASH_PERIOD * 2.5) is True    # third window: on again
    assert flash_on(FLASH_SECONDS) is False        # duration reached
    assert flash_on(FLASH_SECONDS + 5.0) is False


def test_approach_closes_distance_and_clamps():
    v = approach(100.0, 60.0, dt=0.2, seconds=0.4)
    assert v == 80.0                 # half the distance in half the time
    assert approach(61.0, 60.0, dt=1.0) == 60.0   # clamps at target
    assert approach(60.0, 60.0, dt=0.1) == 60.0   # no-op at target


def test_fxstate_defaults():
    fx = FxState()
    assert fx.player_dx == 0 and fx.enemy_dx == 0
    assert fx.player_flash is False and fx.enemy_flash is False
    assert fx.player_dy == 0 and fx.enemy_dy == 0


def test_bob_offset_square_wave():
    from src.scene.effects import BOB_PERIOD, bob_offset
    half = BOB_PERIOD / 2
    assert bob_offset(0.0) == 1
    assert bob_offset(half - 0.01) == 1
    assert bob_offset(half + 0.01) == 0
    assert bob_offset(BOB_PERIOD + 0.01) == 1   # wraps
