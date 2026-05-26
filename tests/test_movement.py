"""Tests for movement.py: Dijkstra reachability + path reconstruction."""
from __future__ import annotations

import pytest

from src.engine.hex import Hex
from src.engine.movement import compute_movement
from src.engine.state import Faction, GameState
from src.engine.tile import Tile, load_terrain
from src.engine.unit import Unit, load_units


@pytest.fixture(autouse=True)
def ensure_loaded():
    load_terrain()
    load_units()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tiles(*pairs: tuple[tuple[int, int], str]) -> dict[Hex, Tile]:
    return {Hex(q, r): Tile(Hex(q, r), tid) for (q, r), tid in pairs}


def _state(tiles: dict[Hex, Tile]) -> GameState:
    nato = Faction(id="NATO", name="NATO", color=(0, 0, 200), credits=500, oil=5, is_ai=False)
    brics = Faction(id="BRICS", name="BRICS", color=(200, 0, 0), credits=500, oil=5)
    return GameState(factions=[nato, brics], tiles=tiles)


def _plain_state(w: int, h: int) -> GameState:
    """w×h all-plain map with no units."""
    tiles = {Hex(q, r): Tile(Hex(q, r), "plain") for q in range(w) for r in range(h)}
    return _state(tiles)


# ---------------------------------------------------------------------------
# Reachability: basics
# ---------------------------------------------------------------------------

def test_own_hex_not_in_reachable():
    s = _plain_state(3, 3)
    u = Unit("nato_inf_l", "NATO", Hex(1, 1))
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(1, 1) not in mv.reachable


def test_adjacent_plain_reachable():
    s = _plain_state(3, 3)
    u = Unit("nato_inf_l", "NATO", Hex(1, 1))
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(2, 1) in mv.reachable
    assert Hex(0, 1) in mv.reachable
    assert Hex(1, 0) in mv.reachable


def test_cost_stored_correctly():
    s = _plain_state(3, 3)
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert mv.reachable[Hex(1, 0)] == 1
    assert mv.reachable[Hex(2, 0)] == 2


def test_exact_budget_boundary():
    """Hex at exactly move budget is reachable; one step beyond is not."""
    s = _state(_tiles(
        ((0, 0), "plain"), ((1, 0), "plain"), ((2, 0), "plain"),
        ((3, 0), "plain"), ((4, 0), "plain"),
    ))
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))  # move=3
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(3, 0) in mv.reachable      # cost=3, exactly at budget
    assert Hex(4, 0) not in mv.reachable  # cost=4, over budget


# ---------------------------------------------------------------------------
# Reachability: terrain costs
# ---------------------------------------------------------------------------

def test_forest_costs_2_for_foot():
    s = _state(_tiles(((0, 0), "plain"), ((1, 0), "forest"), ((2, 0), "plain")))
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))  # foot, move=3
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(1, 0) in mv.reachable
    assert mv.reachable[Hex(1, 0)] == 2
    assert Hex(2, 0) in mv.reachable  # 2+1=3 ≤ move=3


def test_mountain_impassable_for_tracked():
    s = _state(_tiles(((0, 0), "plain"), ((1, 0), "mountain"), ((2, 0), "plain")))
    u = Unit("nato_vehicle_l", "NATO", Hex(0, 0))  # tracked
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(1, 0) not in mv.reachable
    assert Hex(2, 0) not in mv.reachable  # blocked by mountain


def test_mountain_passable_for_foot():
    s = _state(_tiles(((0, 0), "plain"), ((1, 0), "mountain")))
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))  # foot, move=3
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(1, 0) in mv.reachable
    assert mv.reachable[Hex(1, 0)] == 2


def test_river_impassable_for_foot():
    s = _state(_tiles(((0, 0), "plain"), ((1, 0), "river"), ((2, 0), "plain")))
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(1, 0) not in mv.reachable
    assert Hex(2, 0) not in mv.reachable


def test_flying_ignores_impassable_terrain():
    s = _state(_tiles(
        ((0, 0), "plain"), ((1, 0), "mountain"),
        ((2, 0), "river"), ((3, 0), "plain"),
    ))
    u = Unit("nato_jet_l", "NATO", Hex(0, 0))  # flying=True
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert Hex(1, 0) in mv.reachable
    assert Hex(2, 0) in mv.reachable
    assert Hex(3, 0) in mv.reachable


def test_flying_costs_1_per_hex():
    s = _state(_tiles(
        ((0, 0), "plain"), ((1, 0), "plain"),
        ((2, 0), "plain"), ((3, 0), "plain"),
    ))
    u = Unit("nato_jet_l", "NATO", Hex(0, 0))
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert mv.reachable[Hex(1, 0)] == 1
    assert mv.reachable[Hex(2, 0)] == 2
    assert mv.reachable[Hex(3, 0)] == 3


# ---------------------------------------------------------------------------
# Reachability: occupancy
# ---------------------------------------------------------------------------

def test_cannot_stop_on_friendly_occupied_hex():
    s = _plain_state(3, 3)
    u1 = Unit("nato_inf_l", "NATO", Hex(0, 0))
    u2 = Unit("nato_inf_l", "NATO", Hex(1, 0))  # friendly
    s.add_unit(u1)
    s.add_unit(u2)
    mv = compute_movement(s, u1)
    assert Hex(1, 0) not in mv.reachable


def test_can_pass_through_friendly_to_reach_beyond():
    s = _state(_tiles(((0, 0), "plain"), ((1, 0), "plain"), ((2, 0), "plain")))
    u1 = Unit("nato_inf_l", "NATO", Hex(0, 0))  # move=3
    u2 = Unit("nato_inf_l", "NATO", Hex(1, 0))  # friendly blocker
    s.add_unit(u1)
    s.add_unit(u2)
    mv = compute_movement(s, u1)
    assert Hex(1, 0) not in mv.reachable   # can't stop there
    assert Hex(2, 0) in mv.reachable       # can reach by passing through


def test_cannot_pass_through_enemy():
    s = _state(_tiles(((0, 0), "plain"), ((1, 0), "plain"), ((2, 0), "plain")))
    u1 = Unit("nato_inf_l", "NATO", Hex(0, 0))
    enemy = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(u1)
    s.add_unit(enemy)
    mv = compute_movement(s, u1)
    assert Hex(1, 0) not in mv.reachable
    assert Hex(2, 0) not in mv.reachable  # blocked behind enemy


def test_cannot_stop_on_enemy_hex():
    s = _state(_tiles(((0, 0), "plain"), ((1, 0), "plain")))
    u1 = Unit("nato_inf_l", "NATO", Hex(0, 0))
    enemy = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(u1)
    s.add_unit(enemy)
    mv = compute_movement(s, u1)
    assert Hex(1, 0) not in mv.reachable


# ---------------------------------------------------------------------------
# Path reconstruction
# ---------------------------------------------------------------------------

def test_path_to_adjacent():
    s = _plain_state(3, 3)
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))
    s.add_unit(u)
    mv = compute_movement(s, u)
    path = mv.path_to(Hex(1, 0))
    assert path[0] == Hex(0, 0)
    assert path[-1] == Hex(1, 0)
    assert len(path) == 2


def test_path_includes_start():
    s = _plain_state(3, 3)
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))
    s.add_unit(u)
    mv = compute_movement(s, u)
    path = mv.path_to(Hex(2, 0))
    assert path[0] == Hex(0, 0)
    assert path[-1] == Hex(2, 0)


def test_path_to_unreachable_returns_empty():
    s = _state(_tiles(((0, 0), "plain"), ((99, 99), "plain")))
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))
    s.add_unit(u)
    mv = compute_movement(s, u)
    assert mv.path_to(Hex(99, 99)) == []


def test_path_length_matches_hops_on_plain():
    s = _state(_tiles(
        ((0, 0), "plain"), ((1, 0), "plain"),
        ((2, 0), "plain"), ((3, 0), "plain"),
    ))
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))  # move=3
    s.add_unit(u)
    mv = compute_movement(s, u)
    path = mv.path_to(Hex(3, 0))  # 3 steps away
    assert path[0] == Hex(0, 0)
    assert path[-1] == Hex(3, 0)
    assert len(path) == 4  # start + 3 hops
