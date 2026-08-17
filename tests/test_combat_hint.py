"""CombatModeHintScreen copy: describes auto-entry into Selection Mode, the
flee hotkey, and how to TAB out for item use — not "you entered" phrasing."""
from src.ui.screens.combat_hint import CombatModeHintScreen


def test_hint_describes_auto_entry_not_manual_entry():
    import inspect
    source = inspect.getsource(CombatModeHintScreen.on_mount)
    assert "you are currently in" not in source.lower()
    assert "automatically" in source.lower()


def test_hint_documents_flee_and_tab_for_items():
    import inspect
    source = inspect.getsource(CombatModeHintScreen.on_mount)
    assert "0" in source
    assert "flee" in source.lower()
    assert "use [item]" in source.lower() or "use[item]" in source.lower().replace(" ", "")
