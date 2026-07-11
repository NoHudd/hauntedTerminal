"""Pure dialogue-bank resolution against game state."""
from src.npc_dialogue import resolve_dialogue_bank

BANKS = {
    "greeting": ["hello"],
    "with_key": ["you hold the key"],
    "without_key": ["no key, no entry"],
    "lore": ["old tales"],
    "wisdom": ["moo"],
    "farewell": ["the system rests"],
}


def _state(**kw):
    base = {"flags": {}, "items": set(), "met": set(), "npc_id": "npc.x", "game_won": False}
    base.update(kw)
    return base


def test_first_match_wins_in_order():
    rules = [
        {"bank": "with_key", "when": {"has_item": "chmod_key"}},
        {"bank": "without_key"},
    ]
    assert resolve_dialogue_bank(rules, BANKS, _state()) == ["no key, no entry"]
    assert resolve_dialogue_bank(rules, BANKS, _state(items={"chmod_key"})) == ["you hold the key"]


def test_story_flag_and_negation():
    rules = [
        {"bank": "farewell", "when": {"story_flag": "typo_discovered"}},
        {"bank": "greeting", "when": {"not_story_flag": "typo_discovered"}},
    ]
    assert resolve_dialogue_bank(rules, BANKS, _state()) == ["hello"]
    assert resolve_dialogue_bank(
        rules, BANKS, _state(flags={"typo_discovered": True})
    ) == ["the system rests"]


def test_first_meeting_and_game_won():
    rules = [
        {"bank": "farewell", "when": {"game_won": True}},
        {"bank": "greeting", "when": {"first_meeting": True}},
        {"bank": "lore"},
    ]
    assert resolve_dialogue_bank(rules, BANKS, _state()) == ["hello"]           # not met yet
    assert resolve_dialogue_bank(rules, BANKS, _state(met={"npc.x"})) == ["old tales"]
    s3 = _state(met={"npc.x"}, game_won=True)
    assert resolve_dialogue_bank(rules, BANKS, s3) == ["the system rests"]


def test_conditions_within_when_are_anded():
    rules = [{
        "bank": "with_key",
        "when": {"has_item": "chmod_key", "story_flag": "typo_discovered"},
    }]
    assert resolve_dialogue_bank(rules, BANKS, _state(items={"chmod_key"})) is None
    ok = _state(items={"chmod_key"}, flags={"typo_discovered": True})
    assert resolve_dialogue_bank(rules, BANKS, ok) == ["you hold the key"]


def test_banks_pooling_and_unknown_bank_skipped():
    rules = [{"banks": ["lore", "wisdom", "nonexistent"]}]
    assert resolve_dialogue_bank(rules, BANKS, _state()) == ["old tales", "moo"]


def test_no_rules_or_no_match_returns_none():
    assert resolve_dialogue_bank([], BANKS, _state()) is None
    rules = [{"bank": "farewell", "when": {"game_won": True}}]
    assert resolve_dialogue_bank(rules, BANKS, _state()) is None


def test_met_npcs_save_round_trip():
    from src.player import Player
    p = Player(name="t", player_class="guardian")
    p.met_npcs.add("librarian.bin")
    data = p.to_dict()
    assert data["metNpcs"] == ["librarian.bin"]
    p2 = Player.from_dict(data)
    assert p2.met_npcs == {"librarian.bin"}
    old = {k: v for k, v in data.items() if k != "metNpcs"}
    assert Player.from_dict(old).met_npcs == set()


def test_take_sets_item_story_flag():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        item = dict(s.world.get_item("milk_of_motherboard"))
        assert item.get("story_flag") == "milk_claimed"
        s.world.item_locations["milk_of_motherboard"] = s.player.current_room
        s.submit("take milk_of_motherboard")
        assert s.player.get_story_flag("milk_claimed")
    finally:
        s.close()


def _talk(s, npc_id):
    return "\n".join(str(x) for x in s.submit(f"talk {npc_id}"))


def test_talk_uses_rules_and_marks_met():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = s.engine.cmd_handler
        h.world.npc_locations["librarian.bin"] = s.player.current_room
        first = _talk(s, "librarian.bin")
        assert "librarian.bin" in s.player.met_npcs
        greetings = h.world.get_npc("librarian.bin")["dialogue"]["greeting"]
        assert any(g in first for g in greetings), first
    finally:
        s.close()


def test_talk_reacts_to_story_flags():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        h = s.engine.cmd_handler
        h.world.npc_locations["librarian.bin"] = s.player.current_room
        s.player.met_npcs.add("librarian.bin")
        s.player.set_story_flag("typo_discovered")
        out = _talk(s, "librarian.bin")
        panic_lines = h.world.get_npc("librarian.bin")["dialogue"]["about_panic"]
        assert any(line in out for line in panic_lines), out
    finally:
        s.close()


def test_flat_list_npc_still_works():
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        out = _talk(s, "home_guardian.sys")
        assert "Grove Guardian" in out
        assert '"' in out
    finally:
        s.close()


def test_validate_catches_dangling_bank():
    from engine.content import GameContent, find_dialogue_problems
    from engine.schema import NPC
    npc = NPC(id="x", name="X", dialogue={"greeting": ["hi"]},
              dialogue_rules=[{"bank": "nope"}])
    content = GameContent(rooms={}, items={}, enemies={}, npcs={"x": npc},
                          classes={}, abilities={}, attacks={})
    problems = find_dialogue_problems(content)
    assert any("nope" in p for p in problems)


def test_talk_output_is_one_line_not_a_frame_flood():
    """Typewriter frames must coalesce (replace), not append per character."""
    from engine.api import GameSession
    s = GameSession()
    try:
        s.new_game("t", "guardian")
        out = s.submit("talk home_guardian.sys")
        # Headless coalesces frames: a handful of entries, not one per character.
        assert len(out) < 10, f"frame flood: {len(out)} entries"
        assert any("Grove Guardian" in str(x) for x in out)
    finally:
        s.close()
