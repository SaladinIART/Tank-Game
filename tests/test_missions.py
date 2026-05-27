"""
CP-19–22 tests — Missions 2–5 scenario validation.

Covers:
  - All four missions load without errors.
  - Correct factions (NATO human + correct AI faction per mission).
  - HQ tiles exist for both factions.
  - Starting units have expected counts and factions.
  - Each mission's signature victory condition type is installed.
  - Triggering the win condition resolves correctly.
  - End-turn does not crash.
  - _apply_difficulty works on any AI faction, not just BRICS.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.combat import load_damage_matrix
from src.engine.hex import Hex
from src.engine.scenario import load_scenario
from src.engine.tile import load_terrain
from src.engine.unit import Unit, load_units
from src.engine.victory import (
    DestroyHQ,
    DestroyUnitType,
    HoldTiles,
    Outcome,
    OwnAllOfTerrain,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
M2_PATH = _ROOT / "data" / "scenarios" / "m2.json"
M3_PATH = _ROOT / "data" / "scenarios" / "m3.json"
M4_PATH = _ROOT / "data" / "scenarios" / "m4.json"
M5_PATH = _ROOT / "data" / "scenarios" / "m5.json"


@pytest.fixture(autouse=True)
def loaded():
    load_terrain()
    load_units()
    load_damage_matrix()


# ---------------------------------------------------------------------------
# Convenience fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def m2():
    return load_scenario(M2_PATH)


@pytest.fixture()
def m3():
    return load_scenario(M3_PATH)


@pytest.fixture()
def m4():
    return load_scenario(M4_PATH)


@pytest.fixture()
def m5():
    return load_scenario(M5_PATH)


# ---------------------------------------------------------------------------
# Smoke tests: all missions load cleanly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_load(path):
    state, meta = load_scenario(path)
    assert state is not None
    assert "name" in meta


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_have_nato(path):
    state, _ = load_scenario(path)
    nato = state.faction_by_id("NATO")
    assert nato.is_ai is False


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_have_ai_faction(path):
    state, _ = load_scenario(path)
    assert any(f.is_ai for f in state.factions)


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_both_hqs_present(path):
    state, _ = load_scenario(path)
    for f in state.factions:
        hq = state.hq_of(f.id)
        assert hq is not None, f"No HQ tile for faction {f.id} in {path.name}"


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_victory_configs_installed(path):
    state, _ = load_scenario(path)
    for f in state.factions:
        assert f.id in state.victory_configs, f"Missing VictoryConfig for {f.id}"


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_outcomes_pending_at_start(path):
    state, _ = load_scenario(path)
    state.evaluate_victory()
    for f in state.factions:
        assert state.outcomes.get(f.id, Outcome.PENDING) == Outcome.PENDING


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_end_turn_does_not_crash(path):
    state, _ = load_scenario(path)
    state.end_turn()
    assert state.active_faction is not None


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_units_in_bounds(path):
    state, _ = load_scenario(path)
    for u in state.units.values():
        assert u.hex in state.tiles, f"Unit at {u.hex} is out-of-bounds in {path.name}"


@pytest.mark.parametrize("path", [M2_PATH, M3_PATH, M4_PATH, M5_PATH])
def test_all_missions_no_two_units_same_hex(path):
    state, _ = load_scenario(path)
    seen: set[Hex] = set()
    for u in state.units.values():
        assert u.hex not in seen, f"Hex conflict at {u.hex} in {path.name}"
        seen.add(u.hex)


# ---------------------------------------------------------------------------
# Mission 2: Shadow War — NATO vs GUERILLA
# ---------------------------------------------------------------------------

class TestMission2:
    def test_m2_faction_ids(self, m2):
        state, _ = m2
        ids = {f.id for f in state.factions}
        assert "NATO" in ids
        assert "GUERILLA" in ids

    def test_m2_guerilla_is_ai(self, m2):
        state, _ = m2
        assert state.faction_by_id("GUERILLA").is_ai is True

    def test_m2_has_personality(self, m2):
        _, meta = m2
        assert "GUERILLA" in meta["personalities"]

    def test_m2_nato_has_four_starting_units(self, m2):
        state, _ = m2
        assert len(state.units_of("NATO")) == 4

    def test_m2_guerilla_has_five_starting_units(self, m2):
        state, _ = m2
        assert len(state.units_of("GUERILLA")) == 5

    def test_m2_has_neutral_cities(self, m2):
        state, _ = m2
        neutral_cities = [
            t for t in state.tiles.values()
            if t.terrain_id == "city" and t.owner_faction is None
        ]
        assert len(neutral_cities) >= 2

    def test_m2_guerilla_has_stealth_scout(self, m2):
        state, _ = m2
        scouts = [
            u for u in state.units_of("GUERILLA") if u.type_id == "guerilla_scout"
        ]
        assert len(scouts) == 1
        assert scouts[0].unit_type.stealth is True

    def test_m2_victory_has_hold_tiles_condition(self, m2):
        state, _ = m2
        cfg = state.victory_configs["NATO"]
        hold = [c for c in cfg.win_conditions if isinstance(c, HoldTiles)]
        assert hold, "NATO M2 should have a HoldTiles win condition"

    def test_m2_hold_tiles_has_correct_targets(self, m2):
        state, _ = m2
        cfg = state.victory_configs["NATO"]
        hold = next(c for c in cfg.win_conditions if isinstance(c, HoldTiles))
        assert len(hold.target_hexes) == 2

    def test_m2_hold_tiles_turns_required(self, m2):
        state, _ = m2
        cfg = state.victory_configs["NATO"]
        hold = next(c for c in cfg.win_conditions if isinstance(c, HoldTiles))
        assert hold.turns_required == 8

    def test_m2_victory_has_destroy_hq_fallback(self, m2):
        state, _ = m2
        cfg = state.victory_configs["NATO"]
        dhq = [c for c in cfg.win_conditions if isinstance(c, DestroyHQ)]
        assert dhq, "NATO M2 should also have a DestroyHQ fallback condition"

    def test_m2_hold_tiles_triggers_after_n_turns(self, m2):
        state, _ = m2
        cfg = state.victory_configs["NATO"]
        hold = next(c for c in cfg.win_conditions if isinstance(c, HoldTiles))
        # Give NATO ownership of both target hexes
        for h in hold.target_hexes:
            state.tiles[h].owner_faction = "NATO"
        # Need turns_required consecutive evaluations
        for i in range(hold.turns_required - 1):
            assert hold.evaluate(state, "NATO") is False, f"Should not win at eval {i+1}"
        assert hold.evaluate(state, "NATO") is True

    def test_m2_guerilla_loses_when_hq_destroyed(self, m2):
        state, _ = m2
        hq = state.hq_of("GUERILLA")
        state.tiles[hq.hex].owner_faction = None
        cfg = state.victory_configs["GUERILLA"]
        assert cfg.evaluate(state, "GUERILLA") == Outcome.LOST


# ---------------------------------------------------------------------------
# Mission 3: Iron Fist — NATO vs BRICS (own all oil wells)
# ---------------------------------------------------------------------------

class TestMission3:
    def test_m3_faction_ids(self, m3):
        state, _ = m3
        ids = {f.id for f in state.factions}
        assert "NATO" in ids and "BRICS" in ids

    def test_m3_nato_has_five_starting_units(self, m3):
        state, _ = m3
        assert len(state.units_of("NATO")) == 5

    def test_m3_brics_has_six_starting_units(self, m3):
        state, _ = m3
        assert len(state.units_of("BRICS")) == 6

    def test_m3_has_five_oil_wells(self, m3):
        state, _ = m3
        oil_wells = [t for t in state.tiles.values() if t.terrain_id == "oil_well"]
        assert len(oil_wells) == 5

    def test_m3_oil_wells_start_neutral(self, m3):
        state, _ = m3
        oil_wells = [t for t in state.tiles.values() if t.terrain_id == "oil_well"]
        owned_by_nato = sum(1 for t in oil_wells if t.owner_faction == "NATO")
        assert owned_by_nato == 0, "No oil wells should be pre-owned by NATO in M3"

    def test_m3_has_river_and_bridge(self, m3):
        state, _ = m3
        rivers = [t for t in state.tiles.values() if t.terrain_id == "river"]
        bridges = [t for t in state.tiles.values() if t.terrain_id == "bridge"]
        assert len(rivers) >= 2
        assert len(bridges) >= 1

    def test_m3_victory_is_own_all_terrain(self, m3):
        state, _ = m3
        cfg = state.victory_configs["NATO"]
        oat = [c for c in cfg.win_conditions if isinstance(c, OwnAllOfTerrain)]
        assert oat, "NATO M3 should win via OwnAllOfTerrain"

    def test_m3_own_all_terrain_targets_oil_well(self, m3):
        state, _ = m3
        cfg = state.victory_configs["NATO"]
        oat = next(c for c in cfg.win_conditions if isinstance(c, OwnAllOfTerrain))
        assert oat.terrain_id == "oil_well"

    def test_m3_owning_all_oil_wells_wins(self, m3):
        state, _ = m3
        for tile in state.tiles.values():
            if tile.terrain_id == "oil_well":
                tile.owner_faction = "NATO"
        cfg = state.victory_configs["NATO"]
        assert cfg.evaluate(state, "NATO") == Outcome.WON

    def test_m3_partial_oil_ownership_is_pending(self, m3):
        state, _ = m3
        oil_wells = [t for t in state.tiles.values() if t.terrain_id == "oil_well"]
        # Give NATO all but one
        for t in oil_wells[:-1]:
            t.owner_faction = "NATO"
        cfg = state.victory_configs["NATO"]
        assert cfg.evaluate(state, "NATO") == Outcome.PENDING

    def test_m3_brics_has_resource_personality(self, m3):
        _, meta = m3
        assert "BRICS" in meta["personalities"]


# ---------------------------------------------------------------------------
# Mission 4: Last Stand — NATO defends (hold_tiles on own HQ)
# ---------------------------------------------------------------------------

class TestMission4:
    def test_m4_faction_ids(self, m4):
        state, _ = m4
        ids = {f.id for f in state.factions}
        assert "NATO" in ids and "BRICS" in ids

    def test_m4_nato_smaller_force(self, m4):
        state, _ = m4
        nato_count = len(state.units_of("NATO"))
        brics_count = len(state.units_of("BRICS"))
        assert nato_count < brics_count, "NATO should start with fewer units"

    def test_m4_brics_has_more_credits(self, m4):
        state, _ = m4
        assert state.faction_by_id("BRICS").credits > state.faction_by_id("NATO").credits

    def test_m4_has_forest_near_nato(self, m4):
        state, _ = m4
        forests = [t for t in state.tiles.values() if t.terrain_id == "forest"]
        assert len(forests) >= 2

    def test_m4_victory_has_hold_tiles_on_hq(self, m4):
        state, _ = m4
        cfg = state.victory_configs["NATO"]
        hold = [c for c in cfg.win_conditions if isinstance(c, HoldTiles)]
        assert hold, "M4 NATO should have a HoldTiles win condition"
        hq = state.hq_of("NATO")
        assert hq is not None
        h = hold[0]
        assert hq.hex in h.target_hexes, "HoldTiles target must include NATO's HQ hex"

    def test_m4_hold_tiles_turns_required_20(self, m4):
        state, _ = m4
        cfg = state.victory_configs["NATO"]
        hold = next(c for c in cfg.win_conditions if isinstance(c, HoldTiles))
        assert hold.turns_required == 20

    def test_m4_hold_tiles_hq_triggers_win(self, m4):
        state, _ = m4
        cfg = state.victory_configs["NATO"]
        hold = next(c for c in cfg.win_conditions if isinstance(c, HoldTiles))
        # HQ starts NATO-owned; run 20 consecutive evaluations
        hq = state.hq_of("NATO")
        assert hq is not None
        for i in range(hold.turns_required - 1):
            assert hold.evaluate(state, "NATO") is False, f"Should not win at eval {i+1}"
        assert hold.evaluate(state, "NATO") is True

    def test_m4_hq_loss_resets_hold_counter(self, m4):
        state, _ = m4
        cfg = state.victory_configs["NATO"]
        hold = next(c for c in cfg.win_conditions if isinstance(c, HoldTiles))
        hq = state.hq_of("NATO")
        # Advance counter partway
        for _ in range(5):
            hold.evaluate(state, "NATO")
        assert hold.consecutive_turns == 5
        # BRICS captures HQ
        state.tiles[hq.hex].owner_faction = "BRICS"
        hold.evaluate(state, "NATO")
        assert hold.consecutive_turns == 0

    def test_m4_destroy_brics_hq_also_wins(self, m4):
        state, _ = m4
        hq = state.hq_of("BRICS")
        state.tiles[hq.hex].owner_faction = None
        cfg = state.victory_configs["NATO"]
        assert cfg.evaluate(state, "NATO") == Outcome.WON

    def test_m4_brics_aggressive_personality(self, m4):
        _, meta = m4
        assert "BRICS" in meta["personalities"]


# ---------------------------------------------------------------------------
# Mission 5: Decapitation — destroy the Iskander-M
# ---------------------------------------------------------------------------

class TestMission5:
    def test_m5_faction_ids(self, m5):
        state, _ = m5
        ids = {f.id for f in state.factions}
        assert "NATO" in ids and "BRICS" in ids

    def test_m5_has_brics_hypersonic_unit(self, m5):
        state, _ = m5
        hypersonics = [
            u for u in state.units_of("BRICS") if u.type_id == "brics_hypersonic"
        ]
        assert len(hypersonics) == 1, "Exactly one Iskander-M should be on the map"

    def test_m5_hypersonic_is_indirect_fire(self, m5):
        """Iskander-M is a long-range towed missile — range_min > 1 (indirect only)."""
        state, _ = m5
        hyp = next(u for u in state.units_of("BRICS") if u.type_id == "brics_hypersonic")
        assert hyp.unit_type.is_indirect() is True
        assert hyp.unit_type.range_max >= 6

    def test_m5_hypersonic_is_t3(self, m5):
        state, _ = m5
        hyp = next(u for u in state.units_of("BRICS") if u.type_id == "brics_hypersonic")
        assert hyp.unit_type.tier == 3

    def test_m5_victory_is_destroy_unit_type(self, m5):
        state, _ = m5
        cfg = state.victory_configs["NATO"]
        dut = [c for c in cfg.win_conditions if isinstance(c, DestroyUnitType)]
        assert dut, "NATO M5 should win via DestroyUnitType"

    def test_m5_destroy_unit_type_targets_hypersonic(self, m5):
        state, _ = m5
        cfg = state.victory_configs["NATO"]
        dut = next(c for c in cfg.win_conditions if isinstance(c, DestroyUnitType))
        assert dut.type_id == "brics_hypersonic"
        assert dut.owner_faction == "BRICS"

    def test_m5_killing_hypersonic_wins(self, m5):
        state, _ = m5
        hyp = next(u for u in state.units_of("BRICS") if u.type_id == "brics_hypersonic")
        state.units.pop(hyp.uid)
        cfg = state.victory_configs["NATO"]
        assert cfg.evaluate(state, "NATO") == Outcome.WON

    def test_m5_hypersonic_alive_is_pending(self, m5):
        state, _ = m5
        cfg = state.victory_configs["NATO"]
        assert cfg.evaluate(state, "NATO") == Outcome.PENDING

    def test_m5_brics_loses_when_hypersonic_destroyed(self, m5):
        state, _ = m5
        hyp = next(u for u in state.units_of("BRICS") if u.type_id == "brics_hypersonic")
        state.units.pop(hyp.uid)
        cfg = state.victory_configs["BRICS"]
        assert cfg.evaluate(state, "BRICS") == Outcome.LOST

    def test_m5_has_two_river_crossings(self, m5):
        state, _ = m5
        bridges = [t for t in state.tiles.values() if t.terrain_id == "bridge"]
        assert len(bridges) >= 2

    def test_m5_nato_has_six_starting_units(self, m5):
        state, _ = m5
        assert len(state.units_of("NATO")) == 6

    def test_m5_brics_has_escort_units(self, m5):
        state, _ = m5
        brics_units = state.units_of("BRICS")
        assert len(brics_units) >= 6

    def test_m5_brics_guardian_personality(self, m5):
        _, meta = m5
        assert "BRICS" in meta["personalities"]


# ---------------------------------------------------------------------------
# _apply_difficulty: faction-agnostic (works for GUERILLA)
# ---------------------------------------------------------------------------

class TestApplyDifficultyFactionAgnostic:
    def test_hard_boosts_guerilla_in_m2(self):
        from main import _apply_difficulty
        state, meta = load_scenario(M2_PATH)
        grl = state.faction_by_id("GUERILLA")
        credits_before = grl.credits
        _apply_difficulty(state, meta, "hard")
        assert grl.credits > credits_before

    def test_hard_sets_guerilla_personality_in_meta(self):
        from main import _apply_difficulty
        state, meta = load_scenario(M2_PATH)
        _apply_difficulty(state, meta, "hard")
        assert "GUERILLA" in meta.get("personalities", {})

    def test_normal_does_not_change_guerilla_credits(self):
        from main import _apply_difficulty
        state, meta = load_scenario(M2_PATH)
        grl = state.faction_by_id("GUERILLA")
        credits_before = grl.credits
        _apply_difficulty(state, meta, "normal")
        assert grl.credits == credits_before

    def test_hard_boosts_brics_in_m3(self):
        from main import _apply_difficulty
        state, meta = load_scenario(M3_PATH)
        brics = state.faction_by_id("BRICS")
        credits_before = brics.credits
        _apply_difficulty(state, meta, "hard")
        assert brics.credits > credits_before

    def test_hard_sets_brics_personality_in_m4(self):
        from main import _apply_difficulty
        state, meta = load_scenario(M4_PATH)
        _apply_difficulty(state, meta, "hard")
        assert "BRICS" in meta.get("personalities", {})
