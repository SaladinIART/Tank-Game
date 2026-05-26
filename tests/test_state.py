import pickle

import pytest

from src.engine.hex import Hex
from src.engine.state import Faction, GameState
from src.engine.tile import Tile, load_terrain
from src.engine.unit import Unit, load_units


@pytest.fixture(autouse=True)
def ensure_loaded():
    load_terrain()
    load_units()


def _make_state(with_units: bool = True) -> GameState:
    nato = Faction(id="NATO", name="NATO", color=(30, 80, 200), credits=500, oil=5, is_ai=False)
    brics = Faction(id="BRICS", name="BRICS", color=(200, 30, 30), credits=500, oil=5)

    tiles = {
        Hex(0, 0): Tile(Hex(0, 0), "hq", owner_faction="NATO"),
        Hex(1, 0): Tile(Hex(1, 0), "city", owner_faction="NATO"),
        Hex(2, 0): Tile(Hex(2, 0), "oil_well", owner_faction="NATO"),
        Hex(3, 0): Tile(Hex(3, 0), "plain"),
        Hex(0, 1): Tile(Hex(0, 1), "hq", owner_faction="BRICS"),
        Hex(1, 1): Tile(Hex(1, 1), "city", owner_faction="BRICS"),
    }

    state = GameState(factions=[nato, brics], tiles=tiles)

    if with_units:
        state.add_unit(Unit(type_id="nato_inf_l",  faction="NATO", hex=Hex(0, 0)))
        state.add_unit(Unit(type_id="nato_recon",  faction="NATO", hex=Hex(1, 0)))
        state.add_unit(Unit(type_id="nato_jet_l",  faction="NATO", hex=Hex(2, 0)))

    return state


# ---------------------------------------------------------------------------
# Active faction + queries
# ---------------------------------------------------------------------------

def test_initial_active_faction_is_first():
    s = _make_state()
    assert s.active_faction.id == "NATO"
    assert s.turn_number == 1


def test_faction_by_id():
    s = _make_state()
    assert s.faction_by_id("BRICS").name == "BRICS"
    with pytest.raises(KeyError):
        s.faction_by_id("MARS")


def test_units_of_filters_by_faction_and_alive():
    s = _make_state()
    assert len(s.units_of("NATO")) == 3
    assert s.units_of("BRICS") == []
    list(s.units.values())[0].hp = 0
    assert len(s.units_of("NATO")) == 2  # dead one excluded


def test_unit_at_returns_correct_unit():
    s = _make_state()
    u = s.unit_at(Hex(0, 0))
    assert u is not None and u.type_id == "nato_inf_l"
    assert s.unit_at(Hex(99, 99)) is None


def test_tiles_owned_by():
    s = _make_state()
    nato_tiles = s.tiles_owned_by("NATO")
    assert len(nato_tiles) == 3
    assert all(t.owner_faction == "NATO" for t in nato_tiles)


def test_hq_of():
    s = _make_state()
    hq = s.hq_of("NATO")
    assert hq is not None
    assert hq.hex == Hex(0, 0)
    assert s.hq_of("BRICS").hex == Hex(0, 1)


# ---------------------------------------------------------------------------
# Turn rotation
# ---------------------------------------------------------------------------

def test_end_turn_rotates_active_faction():
    s = _make_state()
    assert s.active_faction.id == "NATO"
    s.end_turn()
    assert s.active_faction.id == "BRICS"


def test_end_turn_wraps_and_increments_turn_number():
    s = _make_state()
    assert s.turn_number == 1
    s.end_turn()  # NATO -> BRICS
    assert s.turn_number == 1
    s.end_turn()  # BRICS -> NATO (wrap)
    assert s.turn_number == 2
    assert s.active_faction.id == "NATO"


def test_end_turn_skips_defeated_faction():
    s = _make_state()
    s.factions[1].defeated = True  # BRICS defeated
    s.end_turn()
    # Should skip BRICS and wrap back to NATO
    assert s.active_faction.id == "NATO"
    assert s.turn_number == 2


# ---------------------------------------------------------------------------
# Income, upkeep, action reset (on turn start)
# ---------------------------------------------------------------------------

def test_income_credited_to_new_active_faction():
    s = _make_state(with_units=False)
    brics_before = s.factions[1].credits
    s.end_turn()  # NATO ends; BRICS turn starts → BRICS gets income
    brics_after = s.factions[1].credits
    # BRICS owns: hq(200) + city(100) = 300 credits per turn
    assert brics_after - brics_before == 300


def test_oil_income_credited_to_new_active_faction():
    s = _make_state(with_units=False)
    # Give BRICS an oil well too.
    s.tiles[Hex(2, 1)] = Tile(Hex(2, 1), "oil_well", owner_faction="BRICS")
    brics_oil_before = s.factions[1].oil
    s.end_turn()
    brics_oil_after = s.factions[1].oil
    # oil_well gives 2 oil/turn; BRICS has no units so no upkeep
    assert brics_oil_after - brics_oil_before == 2


def test_upkeep_deducted_from_oil_on_turn_start():
    s = _make_state()  # NATO has recon (1) + jet (2) = 3 oil upkeep
    # Wrap around to NATO again to trigger turn start.
    s.end_turn()  # → BRICS
    nato_oil_before = s.factions[0].oil
    s.end_turn()  # → NATO (turn start: income then upkeep)
    nato_oil_after = s.factions[0].oil
    # Income: hq(0 oil) + city(0 oil) + oil_well(2 oil) = +2
    # Upkeep: nato_recon(1) + nato_jet_l(2) = -3
    # inf_l upkeep 0
    # Net: +2 - 3 = -1
    assert nato_oil_after - nato_oil_before == -1


def test_oil_clamped_to_zero_when_upkeep_exceeds():
    s = _make_state()
    # Drain oil to almost nothing.
    s.factions[0].oil = 0
    # Cycle back to NATO turn.
    s.end_turn()  # → BRICS
    s.end_turn()  # → NATO; income +2, upkeep -3, but oil was 0, so income=2, upkeep zeroes
    assert s.factions[0].oil == 0


def test_unit_action_flags_reset_on_own_turn_start():
    s = _make_state()
    u = s.units_of("NATO")[0]
    u.has_moved = True
    u.has_attacked = True
    # Cycle: NATO -> BRICS -> NATO
    s.end_turn()
    s.end_turn()
    assert not u.has_moved
    assert not u.has_attacked


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def test_add_unit_rejects_duplicate_uid():
    s = _make_state()
    existing = list(s.units.values())[0]
    dup = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(5, 5))
    dup.uid = existing.uid
    with pytest.raises(ValueError):
        s.add_unit(dup)


def test_move_unit_rejects_occupied_destination():
    s = _make_state()
    a = s.units_of("NATO")[0]
    b = s.units_of("NATO")[1]
    with pytest.raises(ValueError):
        s.move_unit(a.uid, b.hex)


def test_move_unit_updates_position():
    s = _make_state()
    u = s.units_of("NATO")[0]
    s.move_unit(u.uid, Hex(3, 0))
    assert u.hex == Hex(3, 0)
    assert s.unit_at(Hex(3, 0)) is u


def test_set_tile_owner_resets_capture():
    s = _make_state()
    s.tiles[Hex(3, 0)].capture_progress = 2
    s.set_tile_owner(Hex(3, 0), "NATO")
    assert s.tiles[Hex(3, 0)].owner_faction == "NATO"
    assert s.tiles[Hex(3, 0)].capture_progress == 0


def test_remove_unit_is_idempotent():
    s = _make_state()
    u = s.units_of("NATO")[0]
    s.remove_unit(u.uid)
    s.remove_unit(u.uid)  # no error
    assert s.unit_at(u.hex) is None


# ---------------------------------------------------------------------------
# Faction.pay / can_afford
# ---------------------------------------------------------------------------

def test_faction_can_afford():
    f = Faction(id="X", name="X", color=(0, 0, 0), credits=100, oil=5)
    assert f.can_afford(50, 3)
    assert not f.can_afford(150, 3)
    assert not f.can_afford(50, 10)


def test_faction_pay_deducts():
    f = Faction(id="X", name="X", color=(0, 0, 0), credits=100, oil=5)
    f.pay(40, 2)
    assert f.credits == 60
    assert f.oil == 3


def test_faction_pay_raises_when_insufficient():
    f = Faction(id="X", name="X", color=(0, 0, 0), credits=100, oil=5)
    with pytest.raises(ValueError):
        f.pay(200, 0)


# ---------------------------------------------------------------------------
# Serialisation (acceptance: no Pygame surfaces, fully picklable)
# ---------------------------------------------------------------------------

def test_state_is_picklable_and_roundtrips():
    s = _make_state()
    s.end_turn()  # mutate a bit to test non-default state
    data = pickle.dumps(s)
    s2 = pickle.loads(data)
    assert s2.active_faction.id == s.active_faction.id
    assert s2.turn_number == s.turn_number
    assert len(s2.units) == len(s.units)
    assert len(s2.tiles) == len(s.tiles)
    # Spot-check a unit's identity
    orig_uids = sorted(s.units.keys())
    new_uids = sorted(s2.units.keys())
    assert orig_uids == new_uids
