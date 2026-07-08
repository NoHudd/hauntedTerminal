"""CharacterClass is typed end to end: the src loader yields engine models,
and the player-build + class-selection render paths work for every class."""
from __future__ import annotations

from engine.schema import CharacterClass


def test_load_class_data_returns_typed_models():
    from src.data_loader import load_class_data
    classes = load_class_data()
    for cid in ("guardian", "weaver", "shaman"):
        assert cid in classes
        klass = classes[cid]
        assert isinstance(klass, CharacterClass), type(klass)
        assert klass.base_health > 0 and klass.base_damage > 0


def test_new_game_builds_player_from_typed_class_data():
    # Exercises player.load_class_attributes + game_world class reads.
    from engine.api import GameSession
    for cid in ("guardian", "weaver", "shaman"):
        s = GameSession()
        try:
            s.new_game("Tester", cid)
            assert s.player.max_health > 0
            assert s.player.total_damage > 0
        finally:
            s.close()


def test_class_selection_renders_from_typed_display():
    # Exercises game_engine._show_class_selection's cls.display.* attribute reads.
    from engine.api import GameSession
    s = GameSession()
    try:
        s.ui.drain()
        s.engine._show_class_selection()
        assert s.ui.drain(), "class selection produced no output"
    finally:
        s.close()
