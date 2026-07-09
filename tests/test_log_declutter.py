"""High-frequency accessor logs must be gated (category='world') and never dump collections."""
from __future__ import annotations


def test_get_items_in_room_logs_are_gated_and_have_no_dict_dump(monkeypatch):
    import src.game_world as gw

    records = []
    monkeypatch.setattr(
        gw, "debug_log", lambda msg, category="system": records.append((str(msg), category))
    )

    from engine.content.loader import load_enemies, load_items, load_rooms
    rooms = {str(r): rr for r, rr in load_rooms("data").items()}
    enemies = {str(e): ee for e, ee in load_enemies("data").items()}
    items = {str(i): ii for i, ii in load_items("data").items()}
    world = gw.GameWorld(rooms, items, enemies, {})

    records.clear()
    world.get_items_in_room("home_grove")

    # no whole-collection dumps
    assert not any("item_locations:" in m and "{" in m for m, _ in records), \
        "get_items_in_room must not dump the full item_locations dict"
    # its informational lines are gated under the 'world' category
    info = [(m, c) for m, c in records if not m.startswith("WARNING")]
    assert info and all(c == "world" for _, c in info), \
        f"accessor logs should be category='world', got {info}"
