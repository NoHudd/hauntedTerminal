from src.ui.screens.log_viewer import line_passes

ERR = "2026-07-09 10:00:00 - src.x - ERROR - boom"
WARN = "2026-07-09 10:00:00 - src.x - WARNING - hmm"
INFO = "2026-07-09 10:00:00 - src.x - INFO - fine"
COMBAT = "[2026-07-09 10:00:00.000] [COMBAT] [combat.py:f:1] hit"


def test_level_filter():
    assert line_passes(INFO, 0, None)                 # all
    assert not line_passes(INFO, 1, None)             # warn+err drops info
    assert line_passes(WARN, 1, None) and line_passes(ERR, 1, None)
    assert line_passes(ERR, 2, None) and not line_passes(WARN, 2, None)  # err-only


def test_category_filter():
    assert line_passes(COMBAT, 0, "combat")
    assert not line_passes(COMBAT, 0, "world")
    assert line_passes(COMBAT, 0, None)               # None = all categories
