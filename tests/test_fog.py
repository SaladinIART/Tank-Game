"""Tests for fog.py: per-faction visibility + LOS + explored memory."""
from __future__ import annotations

import pickle

import pytest

from src.engine.fog import (
    can_faction_see_unit,
    compute_visible,
    effective_vision,
    hexes_visible_from,
)
from src.engine.hex import Hex
from src.engine.state import Faction, GameState
from src.engine.tile import Tile, load_terrain
from src.engine.unit import Unit, load_units


@pytest.fixture(autouse=True)
def ensure_loaded():
    load_terrain()
    load_units()


def _state(tiles: dict[Hex, Tile]) -> GameState:
    nato = Faction(id="NATO", name="NATO", color=(0, 0, 200), credits=500, oil=5, is_ai=False)
    brics = Faction(id="BRICS", name="BRICS", color=(200, 0, 0), credits=500, oil=5)
    return GameState(factions=[nato, brics], tiles=tiles)


def _plain_state(w: int, h: int) -> GameState:
    tiles = {Hex(q, r): Tile(Hex(q, r), "plain") for q in range(w) for r in range(h)}
    return _state(tiles)


# ---------------------------------------------------------------------------
# Effective vision
# ---------------------------------------------------------------------------

def test_plain_vision_is_base():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))  # base vision 2
    s.add_unit(u)
    assert effective_vision(s, u) == 2


def test_mountain_boosts_vision_by_2():
    tiles = {Hex(q, r): Tile(Hex(q, r), "plain") for q in range(5) for r in range(3)}
    tiles[Hex(0, 0)] = Tile(Hex(0, 0), "mountain")
    s = _state(tiles)
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))  # base 2 + mountain +2 = 4
    s.add_unit(u)
    assert effective_vision(s, u) == 4


def test_forest_reduces_vision_by_1():
    tiles = {Hex(q, r): Tile(Hex(q, r), "plain") for q in range(5) for r in range(3)}
    tiles[Hex(0, 0)] = Tile(Hex(0, 0), "forest")
    s = _state(tiles)
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))  # base 2 + forest -1 = 1
    s.add_unit(u)
    assert effective_vision(s, u) == 1


# ---------------------------------------------------------------------------
# Visibility: basic radius
# ---------------------------------------------------------------------------

def test_own_hex_always_visible():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    s.add_unit(u)
    vis = compute_visible(s, "NATO")
    assert Hex(2, 2) in vis


def test_hex_within_radius_visible():
    s = _plain_state(7, 7)
    u = Unit("nato_inf_l", "NATO", Hex(3, 3))  # vision=2
    s.add_unit(u)
    vis = compute_visible(s, "NATO")
    assert Hex(5, 3) in vis      # distance 2
    assert Hex(6, 3) not in vis  # distance 3 > 2


def test_recon_sees_at_distance_4():
    s = _plain_state(8, 8)
    u = Unit("nato_recon", "NATO", Hex(3, 3))  # vision=4
    s.add_unit(u)
    vis = compute_visible(s, "NATO")
    assert Hex(7, 3) in vis


def test_multiple_units_union():
    s = _plain_state(12, 3)
    u1 = Unit("nato_inf_l", "NATO", Hex(1, 1))
    u2 = Unit("nato_inf_l", "NATO", Hex(8, 1))
    s.add_unit(u1)
    s.add_unit(u2)
    vis = compute_visible(s, "NATO")
    assert Hex(1, 1) in vis
    assert Hex(8, 1) in vis
    # Far from u1 (dist 6), within u2 (dist 1):
    assert Hex(7, 1) in vis
    # Between both, outside either radius (dist 4 from u1, dist 3 from u2):
    assert Hex(5, 1) not in vis


def test_dead_units_dont_provide_vision():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    u.hp = 0
    s.add_unit(u)
    vis = compute_visible(s, "NATO")
    assert vis == set()


def test_no_units_means_no_visibility():
    s = _plain_state(5, 5)
    assert compute_visible(s, "NATO") == set()


# ---------------------------------------------------------------------------
# LOS / terrain blocking
# ---------------------------------------------------------------------------

def test_mountain_blocks_los_beyond_it():
    # Observer at (0,0); mountain at (2,0); target at (3,0)
    tiles = {
        Hex(0, 0): Tile(Hex(0, 0), "plain"),
        Hex(1, 0): Tile(Hex(1, 0), "plain"),
        Hex(2, 0): Tile(Hex(2, 0), "mountain"),
        Hex(3, 0): Tile(Hex(3, 0), "plain"),
        Hex(4, 0): Tile(Hex(4, 0), "plain"),
    }
    s = _state(tiles)
    u = Unit("nato_recon", "NATO", Hex(0, 0))  # vision=4
    s.add_unit(u)
    vis = compute_visible(s, "NATO")
    # Up to and including the mountain itself is visible.
    assert Hex(1, 0) in vis
    assert Hex(2, 0) in vis
    # Beyond the mountain is blocked.
    assert Hex(3, 0) not in vis
    assert Hex(4, 0) not in vis


def test_adjacent_always_visible_even_through_mountain():
    # Observer right next to a mountain — that mountain is still seen.
    tiles = {
        Hex(0, 0): Tile(Hex(0, 0), "plain"),
        Hex(1, 0): Tile(Hex(1, 0), "mountain"),
    }
    s = _state(tiles)
    u = Unit("nato_inf_l", "NATO", Hex(0, 0))
    s.add_unit(u)
    vis = compute_visible(s, "NATO")
    assert Hex(1, 0) in vis


def test_forest_does_not_block_los():
    # Forest doesn't block LOS (only mountain does).
    tiles = {
        Hex(0, 0): Tile(Hex(0, 0), "plain"),
        Hex(1, 0): Tile(Hex(1, 0), "forest"),
        Hex(2, 0): Tile(Hex(2, 0), "plain"),
    }
    s = _state(tiles)
    u = Unit("nato_recon", "NATO", Hex(0, 0))  # vision=4
    s.add_unit(u)
    vis = compute_visible(s, "NATO")
    assert Hex(2, 0) in vis  # forest does not block sight beyond


# ---------------------------------------------------------------------------
# GameState integration: cache + invalidation + explored
# ---------------------------------------------------------------------------

def test_visible_to_returns_cached_set():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    s.add_unit(u)
    v1 = s.visible_to("NATO")
    v2 = s.visible_to("NATO")
    assert v1 is v2  # cached identity


def test_invalidate_fog_drops_cache():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    s.add_unit(u)
    v1 = s.visible_to("NATO")
    s.invalidate_fog("NATO")
    v2 = s.visible_to("NATO")
    assert v1 == v2
    assert v1 is not v2  # recomputed


def test_move_unit_invalidates_fog():
    s = _plain_state(10, 3)
    u = Unit("nato_inf_l", "NATO", Hex(1, 1))  # vision=2
    s.add_unit(u)
    v1 = s.visible_to("NATO")
    assert Hex(7, 1) not in v1
    s.move_unit(u.uid, Hex(6, 1))
    v2 = s.visible_to("NATO")
    assert Hex(7, 1) in v2  # newly revealed


def test_end_turn_invalidates_all_fog():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    s.add_unit(u)
    _ = s.visible_to("NATO")
    assert "NATO" in s._visible_cache
    s.end_turn()
    assert s._visible_cache == {}


def test_explored_accumulates_across_moves():
    s = _plain_state(10, 3)
    u = Unit("nato_inf_l", "NATO", Hex(1, 1))
    s.add_unit(u)
    _ = s.visible_to("NATO")
    early = set(s.explored["NATO"])
    s.move_unit(u.uid, Hex(7, 1))
    _ = s.visible_to("NATO")
    later = s.explored["NATO"]
    assert early.issubset(later)
    assert Hex(7, 1) in later
    # The starting hex stays explored even though unit has moved away.
    assert Hex(1, 1) in later


# ---------------------------------------------------------------------------
# Stealth-aware unit visibility
# ---------------------------------------------------------------------------

def test_own_units_always_visible_to_self():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    s.add_unit(u)
    assert can_faction_see_unit(s, "NATO", u)


def test_dead_units_never_visible():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    u.hp = 0
    s.add_unit(u)
    assert not can_faction_see_unit(s, "NATO", u)


def test_enemy_in_fog_invisible():
    s = _plain_state(20, 3)
    n = Unit("nato_inf_l", "NATO", Hex(0, 1))   # vision=2
    b = Unit("nato_inf_l", "BRICS", Hex(18, 1))  # too far to see
    s.add_unit(n)
    s.add_unit(b)
    assert not can_faction_see_unit(s, "NATO", b)


def test_enemy_in_visible_radius_seen():
    s = _plain_state(5, 3)
    n = Unit("nato_inf_l", "NATO", Hex(0, 1))  # vision=2
    b = Unit("nato_inf_l", "BRICS", Hex(2, 1))  # distance 2
    s.add_unit(n)
    s.add_unit(b)
    assert can_faction_see_unit(s, "NATO", b)


# ---------------------------------------------------------------------------
# Pickleability
# ---------------------------------------------------------------------------

def test_state_with_fog_is_picklable():
    s = _plain_state(5, 5)
    u = Unit("nato_inf_l", "NATO", Hex(2, 2))
    s.add_unit(u)
    _ = s.visible_to("NATO")  # populate cache + explored
    data = pickle.dumps(s)
    s2 = pickle.loads(data)
    assert s2.explored == s.explored
    assert s2.turn_number == s.turn_number
