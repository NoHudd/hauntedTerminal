"""Intent checks: content that references real ids but means the wrong thing.

The reference linker proves ids exist. These pin the next layer: keys and locks
agree, no content field is silently ignored by the game, and every entity the
scene view draws has art.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.content import GameContent, find_lock_problems, find_unread_fields, load_all
from engine.content.linker import UNIMPLEMENTED_FIELDS
from engine.schema import Enemy, ItemId, RoomId


@pytest.fixture(scope="module")
def content() -> GameContent:
    return load_all("data")


def _copy(content: GameContent) -> GameContent:
    return GameContent(
        rooms={k: v.model_copy(deep=True) for k, v in content.rooms.items()},
        items={k: v.model_copy(deep=True) for k, v in content.items.items()},
        enemies={k: v.model_copy(deep=True) for k, v in content.enemies.items()},
        npcs=dict(content.npcs),
        classes=dict(content.classes),
        abilities=dict(content.abilities),
        attacks=dict(content.attacks),
    )


def test_shipped_content_is_clean(content: GameContent) -> None:
    assert find_lock_problems(content) == []
    assert find_unread_fields(content) == []


def test_a_lock_without_a_key_is_caught(content: GameContent) -> None:
    c = _copy(content)
    c.rooms[RoomId("usr_lib_arcane")].key_required = None
    assert any("locked, but names no key_required" in p for p in find_lock_problems(c))


def test_a_key_that_misses_its_own_door_is_caught(content: GameContent) -> None:
    c = _copy(content)
    c.items[ItemId("lib_key")].unlocks = []
    assert any("does not list it" in p for p in find_lock_problems(c))


def test_a_key_claiming_someone_elses_door_is_caught(content: GameContent) -> None:
    c = _copy(content)
    c.items[ItemId("lib_key")].unlocks.append(RoomId("core"))
    problems = find_lock_problems(c)
    assert any("item 'lib_key': unlocks 'core'" in p for p in problems)


def test_a_non_key_used_as_a_key_is_caught(content: GameContent) -> None:
    c = _copy(content)
    c.rooms[RoomId("core")].key_required = ItemId("health_packet")
    assert any("is a consumable, not a key" in p for p in find_lock_problems(c))


def test_a_new_unread_field_fails(content: GameContent) -> None:
    c = _copy(content)
    eid = next(iter(c.enemies))
    body = c.enemies[eid].model_dump(exclude_unset=True)
    c.enemies[eid] = Enemy(**body, bonus_gold=50)
    assert any("field 'bonus_gold' is not in the schema" in p for p in find_unread_fields(c))


def test_a_stale_allowlist_entry_fails(content: GameContent) -> None:
    c = _copy(content)
    for eid, enemy in list(c.enemies.items()):
        body = enemy.model_dump(exclude_unset=True)
        body.pop("on_defeat", None)
        c.enemies[eid] = Enemy(**body)
    assert "on_defeat" in UNIMPLEMENTED_FIELDS["enemy"]
    assert any("lists 'on_defeat', but no enemy uses it" in p for p in find_unread_fields(c))


@pytest.mark.parametrize("kind", ["enemies", "npcs", "classes"])
def test_every_drawn_entity_has_art(content: GameContent, kind: str) -> None:
    root = Path("assets/sprites") / kind
    missing = [str(i) for i in getattr(content, kind) if not (root / f"{i}.png").exists()]
    assert not missing, f"no sprite in {root} for: {missing} (the scene would show a placeholder)"


def test_every_room_zone_has_a_backdrop(content: GameContent) -> None:
    root = Path("assets/sprites/backdrops")
    zones = {room.zone for room in content.rooms.values() if room.zone}
    missing = sorted(z for z in zones if not (root / f"{z}.png").exists())
    assert not missing, f"no backdrop for zones: {missing}"


def test_validate_cli_fails_on_an_unread_field(tmp_path: Path) -> None:
    import shutil

    from engine.validate import main

    data = tmp_path / "data"
    shutil.copytree("data", data)
    enemy_file = sorted((data / "enemies").glob("*.yml"))[0]
    enemy_file.write_text(enemy_file.read_text() + "\nbonus_gold: 50\n")
    assert main([str(data)]) == 1
