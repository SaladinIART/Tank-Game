"""
Tests for src/engine/stance_actions.py and the underlying stance combat math.

Covers:
  - Defend stance grants +2 DEF and locks attacks.
  - Retreat picks the reachable hex closest to own HQ.
  - actionable_units() reflects the .can_act() definition.
  - HQ clearance converts impassable neighbours to plain in scenario load.
  - Save/load round-trip preserves stance.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from src.engine.combat import (
    can_attack,
    load_damage_matrix,
    predict_damage,
)
from src.engine.hex import Hex, neighbours
from src.engine.scenario import clear_hq_surroundings, load_scenario
from src.engine.stance_actions import (
    actionable_units,
    retreat,
    retreat_destination,
    set_defend,
)
from src.engine.state import Faction, GameState
from src.engine.tile import Tile, load_terrain
from src.engine.unit import (
    DEFEND_BONUS,
    STANCE_ATTACK,
    STANCE_DEFEND,
    Unit,
    load_units,
)
from src.persistence.save import save_state, load_state


# ---------------------------------------------------------------------------
# Fixtures: tiny battlefield
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _load_data():
    load_terrain()
    load_units()
    load_damage_matrix()


def _two_faction_state(
    attacker_hex: Hex = Hex(0, 0),
    defender_hex: Hex = Hex(1, 0),
) -> tuple[GameState, Unit, Unit]:
    factions = [
        Faction(id="NATO",  name="NATO",  color=(0, 0, 0), credits=0, oil=0, is_ai=False),
        Faction(id="BRICS", name="BRICS", color=(0, 0, 0), credits=0, oil=0, is_ai=True),
    ]
    tiles = {Hex(q, r): Tile(Hex(q, r), "plain")
             for q in range(8) for r in range(8)}
    # Place HQs so retreat has somewhere to head to.
    tiles[Hex(0, 0)] = Tile(Hex(0, 0), "hq", owner_faction="NATO")
    tiles[Hex(7, 7)] = Tile(Hex(7, 7), "hq", owner_faction="BRICS")
    state = GameState(factions=factions, tiles=tiles)
    a = Unit(type_id="nato_inf_m", faction="NATO",  hex=attacker_hex, hp=10)
    d = Unit(type_id="brics_inf_m", faction="BRICS", hex=defender_hex, hp=10)
    state.add_unit(a)
    state.add_unit(d)
    return state, a, d


# ---------------------------------------------------------------------------
# Defend stance: combat math
# ---------------------------------------------------------------------------

class TestDefendStance:
    def test_default_stance_is_attack(self):
        state, a, _ = _two_faction_state()
        assert a.stance == STANCE_ATTACK

    def test_set_defend_consumes_action(self):
        state, a, _ = _two_faction_state()
        set_defend(state, a)
        assert a.stance == STANCE_DEFEND
        assert not a.can_act()       # actions consumed

    def test_defend_blocks_attack_attempt(self):
        state, a, d = _two_faction_state()
        set_defend(state, a)
        assert not can_attack(state, a, d), \
            "Defending unit should refuse to initiate attacks"

    def test_defend_reduces_incoming_damage(self):
        state, a, d = _two_faction_state(Hex(2, 2), Hex(3, 2))
        # Attack BRICS vs NATO inf_m on plain ground
        baseline = predict_damage(state, d, a)
        a.stance = STANCE_DEFEND
        defended = predict_damage(state, d, a)
        assert defended < baseline, \
            f"Defend should reduce damage: baseline={baseline} def={defended}"

    def test_defend_clears_on_turn_start(self):
        state, a, _ = _two_faction_state()
        set_defend(state, a)
        # Force NATO inactive → BRICS active → cycle back to NATO
        state.end_turn()  # NATO -> BRICS (NATO is_ai=False but cycle still happens)
        state.end_turn()  # BRICS -> NATO; NATO start fires reset_turn
        assert a.stance == STANCE_ATTACK, \
            "reset_turn should clear defend stance at start of own turn"
        assert a.can_act()

    def test_defend_bonus_constant(self):
        assert DEFEND_BONUS == 2


# ---------------------------------------------------------------------------
# Retreat
# ---------------------------------------------------------------------------

class TestRetreat:
    def test_retreat_destination_moves_toward_hq(self):
        # Unit far from HQ; retreat should pick closer hex.
        state, a, _ = _two_faction_state(attacker_hex=Hex(4, 4))
        dest = retreat_destination(state, a)
        assert dest is not None
        from src.engine.hex import distance
        hq = state.hq_of("NATO").hex
        assert distance(dest, hq) < distance(a.hex, hq)

    def test_retreat_consumes_actions(self):
        state, a, _ = _two_faction_state(attacker_hex=Hex(4, 4))
        retreat(state, a)
        assert a.has_moved
        assert a.has_attacked

    def test_retreat_moves_unit(self):
        state, a, _ = _two_faction_state(attacker_hex=Hex(4, 4))
        start = a.hex
        dest = retreat(state, a)
        assert dest is not None
        assert a.hex == dest
        assert a.hex != start

    def test_retreat_no_hq_returns_none(self):
        state, a, _ = _two_faction_state(attacker_hex=Hex(4, 4))
        # Remove NATO HQ
        state.tiles[Hex(0, 0)] = Tile(Hex(0, 0), "plain")
        assert retreat_destination(state, a) is None


# ---------------------------------------------------------------------------
# Actionable-units reminder
# ---------------------------------------------------------------------------

class TestActionableUnits:
    def test_counts_only_units_that_can_act(self):
        state, a, _ = _two_faction_state()
        assert len(actionable_units(state, "NATO")) == 1
        a.has_moved = True
        a.has_attacked = True
        assert len(actionable_units(state, "NATO")) == 0

    def test_defend_drops_from_actionable(self):
        state, a, _ = _two_faction_state()
        set_defend(state, a)
        assert len(actionable_units(state, "NATO")) == 0


# ---------------------------------------------------------------------------
# HQ surroundings clearance
# ---------------------------------------------------------------------------

class TestHQClearance:
    def test_mountain_neighbour_converted_to_plain(self):
        load_terrain()
        h_hq = Hex(5, 5)
        tiles = {h_hq: Tile(h_hq, "hq", owner_faction="NATO")}
        for n in neighbours(h_hq):
            tiles[n] = Tile(n, "mountain")
        n_cleared = clear_hq_surroundings(tiles)
        assert n_cleared == 6
        for n in neighbours(h_hq):
            assert tiles[n].terrain_id == "plain"

    def test_river_neighbour_converted_to_plain(self):
        h_hq = Hex(3, 3)
        tiles = {h_hq: Tile(h_hq, "hq", owner_faction="NATO")}
        for n in neighbours(h_hq):
            tiles[n] = Tile(n, "river")
        clear_hq_surroundings(tiles)
        for n in neighbours(h_hq):
            assert tiles[n].terrain_id == "plain"

    def test_forest_neighbour_kept(self):
        h_hq = Hex(2, 2)
        tiles = {h_hq: Tile(h_hq, "hq", owner_faction="NATO")}
        for n in neighbours(h_hq):
            tiles[n] = Tile(n, "forest")
        clear_hq_surroundings(tiles)
        for n in neighbours(h_hq):
            # Forest is passable to foot → should be preserved as cover.
            assert tiles[n].terrain_id == "forest"

    def test_scenario_load_clears_hq(self):
        """Real m1 must have no impassable terrain in HQ neighbourhoods."""
        state, _meta = load_scenario("data/scenarios/m1.json")
        for tile in state.tiles.values():
            if not tile.terrain.is_hq:
                continue
            for n in neighbours(tile.hex):
                neighbour = state.tiles.get(n)
                if neighbour is None:
                    continue
                assert neighbour.terrain_id not in ("mountain", "river"), (
                    f"HQ at {tile.hex} has impassable neighbour {n}: {neighbour.terrain_id}"
                )


# ---------------------------------------------------------------------------
# Save/load round-trip
# ---------------------------------------------------------------------------

class TestStancePersists:
    def test_defend_round_trips_through_save(self, tmp_path):
        state, a, _ = _two_faction_state()
        set_defend(state, a)
        assert a.stance == STANCE_DEFEND

        save_path = tmp_path / "stance_save.json"
        save_state(state, save_path, scenario_slug="test")
        loaded, _meta = load_state(save_path)

        reloaded_a = loaded.units[a.uid]
        assert reloaded_a.stance == STANCE_DEFEND

    def test_old_save_without_stance_defaults_to_attack(self, tmp_path):
        """Back-compat: pre-stance saves must still load."""
        # Build a save dict and strip the stance field
        state, a, _ = _two_faction_state()
        save_path = tmp_path / "legacy_save.json"
        save_state(state, save_path, scenario_slug="test")
        data = json.loads(save_path.read_text(encoding="utf-8"))
        for u in data["units"]:
            u.pop("stance", None)
        save_path.write_text(json.dumps(data), encoding="utf-8")
        loaded, _meta = load_state(save_path)
        for u in loaded.units.values():
            assert u.stance == STANCE_ATTACK
