"""RoomView carries entity ids + zone so the scene can resolve sprite files."""
from src.viewmodels.view_builder import ViewBuilder


class _FakeRoom:
    name = "The Graveyard"
    description = "Foggy."
    exits = []
    zone = "safe"


class _FakeEnemy:
    def __init__(self, name):
        self.name = name


class _FakeWorld:
    rooms = {"home_grove": _FakeRoom()}
    enemies = {"lost_inode.tmp": _FakeEnemy("Lost Inode")}
    npcs = {"oracle.db": {"name": "The Oracle"}}

    def get_enemies_in_room(self, room_id):
        return ["lost_inode.tmp"]

    def get_npcs_in_room(self, room_id):
        return ["oracle.db"]


def test_room_view_includes_ids_and_zone():
    view = ViewBuilder.build_room_view(_FakeWorld(), "home_grove")
    assert view.id == "home_grove"
    assert view.zone == "safe"
    assert view.enemy_ids == ["lost_inode.tmp"]
    assert view.npc_ids == ["oracle.db"]
    assert view.enemies == ["Lost Inode"]      # names still intact, same order
    assert view.npcs == ["The Oracle"]
    d = view.to_dict()
    assert d["enemy_ids"] == ["lost_inode.tmp"] and d["zone"] == "safe"


def test_room_view_marks_cleared_exits():
    # Fictional room ids (not real game content) so ROOM_ID_TO_PATH.get()
    # falls back to returning the id verbatim (its documented default when
    # a key isn't found) instead of resolving to some unrelated real room's
    # path — build_room_view reads that table as a module-level import, not
    # something this fake world provides.
    class _ExitRoom(_FakeRoom):
        exits = ["fake_cleared_room", "fake_uncleared_room"]

    class _World(_FakeWorld):
        rooms = {
            "fake_start": _ExitRoom(),
            "fake_cleared_room": _FakeRoom(),
            "fake_uncleared_room": _FakeRoom(),
        }

        def get_room_state(self, room_id):
            return {"hidden": False}

        def is_room_cleared(self, room_id):
            return room_id == "fake_cleared_room"

    view = ViewBuilder.build_room_view(_World(), "fake_start")
    assert "fake_cleared_room ✓" in view.exits
    assert "fake_uncleared_room" in view.exits  # uncleared: no marker
