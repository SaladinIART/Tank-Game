"""Tests for capture.py: progress advancement, ownership flip, stale-reset."""
from __future__ import annotations

import pytest

from src.engine.capture import process_captures
from src.engine.hex import Hex
from src.engine.state import Faction, GameState
from src.engine.tile import CAPTURE_TURNS, Tile, load_terrain
from src.engine.unit import Unit, load_units


@pytest.fixture(autouse=True)
def loaded():
    load_terrain()
    load_units()


def _state(
    tile_specs: list[tuple[int, int, str, str | None]],
) -> GameState:
    """
    Build a minimal 2-faction state from ``(q, r, terrain_id, owner)`` tuples.
    ``owner=None`` → neutral.
    """
    nato = Faction(id="NATO",  name="NATO",  color=(0, 0, 200), credits=0, oil=0, is_ai=False)
    brics = Faction(id="BRICS", name="BRICS", color=(200, 0, 0), credits=0, oil=0)
    tiles: dict[Hex, Tile] = {}
    for q, r, tid, owner in tile_specs:
        tiles[Hex(q, r)] = Tile(Hex(q, r), tid, owner_faction=owner)
    return GameState(factions=[nato, brics], tiles=tiles)


# ---------------------------------------------------------------------------
# Basic progress advancement
# ---------------------------------------------------------------------------

def test_engineer_advances_capture_progress():
    """NATO engineer on neutral city → progress increments by 1."""
    s = _state([(0, 0, "city", None)])
    eng = Unit("nato_engineer", "NATO", Hex(0, 0))
    s.add_unit(eng)
    nato = s.faction_by_id("NATO")
    process_captures(s, nato)
    assert s.tiles[Hex(0, 0)].capture_progress == 1


def test_capturing_faction_set_on_first_advance():
    """After first advance the tile's capturing_faction == capturing faction."""
    s = _state([(0, 0, "city", None)])
    s.add_unit(Unit("nato_engineer", "NATO", Hex(0, 0)))
    process_captures(s, s.faction_by_id("NATO"))
    assert s.tiles[Hex(0, 0)].capturing_faction == "NATO"


def test_non_capture_unit_does_not_advance():
    """Regular infantry (can_capture=False) leaves progress at 0."""
    s = _state([(0, 0, "city", None)])
    s.add_unit(Unit("nato_inf_l", "NATO", Hex(0, 0)))
    process_captures(s, s.faction_by_id("NATO"))
    assert s.tiles[Hex(0, 0)].capture_progress == 0


def test_capture_own_tile_no_progress():
    """Engineer on a tile already owned by their faction → no progress."""
    s = _state([(0, 0, "city", "NATO")])
    s.add_unit(Unit("nato_engineer", "NATO", Hex(0, 0)))
    process_captures(s, s.faction_by_id("NATO"))
    assert s.tiles[Hex(0, 0)].capture_progress == 0
    assert s.tiles[Hex(0, 0)].capturing_faction is None


def test_capture_enemy_tile():
    """NATO engineer can capture a BRICS-owned city."""
    s = _state([(0, 0, "city", "BRICS")])
    s.add_unit(Unit("nato_engineer", "NATO", Hex(0, 0)))
    nato = s.faction_by_id("NATO")
    process_captures(s, nato)
    assert s.tiles[Hex(0, 0)].capture_progress == 1
    assert s.tiles[Hex(0, 0)].capturing_faction == "NATO"


# ---------------------------------------------------------------------------
# Capture completion
# ---------------------------------------------------------------------------

def test_capture_flips_ownership_at_capture_turns():
    """After CAPTURE_TURNS advances, tile owner changes to capturing faction."""
    s = _state([(0, 0, "city", None)])
    tile = s.tiles[Hex(0, 0)]
    # Pre-seed progress to one step before completion.
    tile.capture_progress = CAPTURE_TURNS - 1
    tile.capturing_faction = "NATO"
    s.add_unit(Unit("nato_engineer", "NATO", Hex(0, 0)))
    nato = s.faction_by_id("NATO")
    process_captures(s, nato)
    assert tile.owner_faction == "NATO"
    assert tile.capture_progress == 0
    assert tile.capturing_faction is None


def test_flipped_hexes_returned():
    """process_captures returns the list of hexes that flipped ownership."""
    s = _state([(0, 0, "city", None), (1, 0, "oil_well", None)])
    # Both tiles one step away from capture.
    for h in (Hex(0, 0), Hex(1, 0)):
        s.tiles[h].capture_progress = CAPTURE_TURNS - 1
        s.tiles[h].capturing_faction = "NATO"
    s.add_unit(Unit("nato_engineer", "NATO", Hex(0, 0)))
    s.add_unit(Unit("nato_inf_m",    "NATO", Hex(1, 0)))
    flipped = process_captures(s, s.faction_by_id("NATO"))
    assert set(flipped) == {Hex(0, 0), Hex(1, 0)}


def test_income_includes_tile_captured_this_turn():
    """
    A tile flipped during _process_captures (called before _apply_income)
    must contribute its income in the same turn.
    """
    # NATO is faction index 0 (active first).
    # Arrange: BRICS is currently active so we call end_turn to reach NATO's turn.
    s = _state([(0, 0, "city", None)])
    s.active_faction_idx = 1  # BRICS's turn is "now"
    s.tiles[Hex(0, 0)].capture_progress = CAPTURE_TURNS - 1
    s.tiles[Hex(0, 0)].capturing_faction = "NATO"
    s.add_unit(Unit("nato_engineer", "NATO", Hex(0, 0)))
    nato = s.faction_by_id("NATO")
    credits_before = nato.credits
    s.end_turn()  # BRICS → NATO: capture fires, then income
    # city income = 100 credits
    assert nato.credits == credits_before + 100


# ---------------------------------------------------------------------------
# Stale-progress resets
# ---------------------------------------------------------------------------

def test_progress_resets_when_unit_leaves():
    """Unit was on tile last turn (progress=2), moved away — progress should reset."""
    s = _state([(0, 0, "city", None), (1, 0, "plain", None)])
    tile = s.tiles[Hex(0, 0)]
    tile.capture_progress = 2
    tile.capturing_faction = "NATO"
    # Engineer is now on Hex(1,0) — NOT on the city.
    s.add_unit(Unit("nato_engineer", "NATO", Hex(1, 0)))
    process_captures(s, s.faction_by_id("NATO"))
    assert tile.capture_progress == 0
    assert tile.capturing_faction is None


def test_progress_resets_when_killed_before_turn():
    """No NATO unit on the tile at all → stale progress resets."""
    s = _state([(0, 0, "city", None)])
    tile = s.tiles[Hex(0, 0)]
    tile.capture_progress = 1
    tile.capturing_faction = "NATO"
    # NATO has no units anywhere.
    process_captures(s, s.faction_by_id("NATO"))
    assert tile.capture_progress == 0


def test_enemy_arrival_resets_progress():
    """NATO had progress=1; now BRICS engineer is on the tile — BRICS starts from 1."""
    s = _state([(0, 0, "city", None)])
    tile = s.tiles[Hex(0, 0)]
    tile.capture_progress = 1
    tile.capturing_faction = "NATO"  # NATO was capturing but left (or was killed)
    # BRICS engineer is now there.
    s.add_unit(Unit("nato_engineer", "BRICS", Hex(0, 0)))
    process_captures(s, s.faction_by_id("BRICS"))
    assert tile.capture_progress == 1
    assert tile.capturing_faction == "BRICS"


# ---------------------------------------------------------------------------
# Tile.reset_capture
# ---------------------------------------------------------------------------

def test_reset_capture_clears_both_fields():
    tile = Tile(Hex(0, 0), "city", capture_progress=2, capturing_faction="NATO")
    tile.reset_capture()
    assert tile.capture_progress == 0
    assert tile.capturing_faction is None


# ---------------------------------------------------------------------------
# Multiple simultaneous captures
# ---------------------------------------------------------------------------

def test_multiple_engineers_capture_different_tiles():
    """Two engineers capture two different tiles in the same process_captures call."""
    s = _state([
        (0, 0, "city", None),
        (2, 0, "oil_well", None),
    ])
    s.add_unit(Unit("nato_engineer", "NATO", Hex(0, 0)))
    s.add_unit(Unit("nato_inf_m",    "NATO", Hex(2, 0)))
    process_captures(s, s.faction_by_id("NATO"))
    assert s.tiles[Hex(0, 0)].capture_progress == 1
    assert s.tiles[Hex(2, 0)].capture_progress == 1
