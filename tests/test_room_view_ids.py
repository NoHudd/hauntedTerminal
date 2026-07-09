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
