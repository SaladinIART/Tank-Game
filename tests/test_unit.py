import pytest
from src.engine.hex import Hex
from src.engine.unit import (
    Unit,
    UnitType,
    all_units,
    get,
    load_units,
    units_for_faction,
    units_for_tier,
)

NATO_EXPECTED = {
    "nato_inf_l", "nato_engineer", "nato_recon",
    "nato_aa_l", "nato_vehicle_l", "nato_inf_m",
    "nato_vehicle_m", "nato_artillery_l", "nato_jet_l",
}


@pytest.fixture(autouse=True)
def ensure_loaded():
    load_units()


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def test_all_nato_types_present():
    ids = set(all_units().keys())
    assert NATO_EXPECTED.issubset(ids)


def test_unit_types_are_correct_class():
    for ut in all_units().values():
        assert isinstance(ut, UnitType)



# ---------------------------------------------------------------------------
# Flags — acceptance criteria
# ---------------------------------------------------------------------------

def test_engineer_can_capture():
    assert get("nato_engineer").can_capture


def test_inf_m_can_capture():
    assert get("nato_inf_m").can_capture


def test_non_engineers_cannot_capture():
    non_cap = {
        "nato_inf_l", "nato_recon", "nato_aa_l",
        "nato_vehicle_l", "nato_vehicle_m", "nato_artillery_l", "nato_jet_l",
    }
    for tid in non_cap:
        assert not get(tid).can_capture, f"{tid} should not capture"


def test_artillery_has_min_range_greater_than_1():
    art = get("nato_artillery_l")
    assert art.range_min > 1, "Artillery must be indirect-fire (range_min > 1)"
    assert art.is_indirect()
    assert not art.in_range(1)
    assert not art.in_range(2)
    assert art.in_range(3)
    assert art.in_range(5)
    assert not art.in_range(6)


def test_jet_is_flying():
    jet = get("nato_jet_l")
    assert jet.flying
    assert jet.move_category == "air"


def test_ground_units_not_flying():
    for tid in ("nato_inf_l", "nato_vehicle_m", "nato_artillery_l"):
        assert not get(tid).flying


def test_recon_has_highest_vision_among_ground():
    ground = [ut for ut in units_for_faction("NATO") if not ut.flying]
    recon = get("nato_recon")
    assert recon.vision == max(ut.vision for ut in ground)


def test_jet_has_highest_vision_overall():
    jet = get("nato_jet_l")
    assert jet.vision == max(ut.vision for ut in units_for_faction("NATO"))


# ---------------------------------------------------------------------------
# Tier filtering
# ---------------------------------------------------------------------------

def test_tier1_units_present_and_correct():
    t1 = {ut.id for ut in units_for_tier("NATO", 1)}
    tier1_expected = {"nato_inf_l", "nato_engineer", "nato_recon", "nato_aa_l", "nato_vehicle_l"}
    assert tier1_expected.issubset(t1)
    # No tier-2 units in tier-1 list.
    for tid in ("nato_vehicle_m", "nato_artillery_l", "nato_jet_l", "nato_inf_m"):
        assert tid not in t1


def test_tier2_includes_tier1():
    t1_ids = {ut.id for ut in units_for_tier("NATO", 1)}
    t2_ids = {ut.id for ut in units_for_tier("NATO", 2)}
    assert t1_ids.issubset(t2_ids)
    assert len(t2_ids) > len(t1_ids)


def test_tier_values_valid():
    for ut in all_units().values():
        assert 1 <= ut.tier <= 3


# ---------------------------------------------------------------------------
# Costs and stats sanity
# ---------------------------------------------------------------------------

def test_heavier_units_cost_more():
    assert get("nato_vehicle_m").cost_credits > get("nato_vehicle_l").cost_credits
    assert get("nato_jet_l").cost_credits > get("nato_vehicle_m").cost_credits


def test_all_units_have_valid_color():
    for ut in all_units().values():
        assert len(ut.color) == 3
        for c in ut.color:
            assert 0 <= c <= 255


def test_hp_is_10_for_all():
    for ut in all_units().values():
        assert ut.hp == 10


# ---------------------------------------------------------------------------
# Unit instance
# ---------------------------------------------------------------------------

def test_unit_instance_creation():
    u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
    assert u.hp == 10
    assert not u.has_moved
    assert not u.has_attacked
    assert u.is_alive()
    assert u.unit_type.id == "nato_inf_l"


def test_unit_unique_ids():
    u1 = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
    u2 = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(1, 0))
    assert u1.uid != u2.uid


def test_unit_reset_turn():
    u = Unit(type_id="nato_recon", faction="NATO", hex=Hex(2, 1))
    u.has_moved = True
    u.has_attacked = True
    assert u.is_exhausted()
    u.reset_turn()
    assert not u.has_moved
    assert not u.has_attacked
    assert not u.is_exhausted()


def test_unit_apply_damage():
    u = Unit(type_id="nato_vehicle_l", faction="NATO", hex=Hex(0, 0))
    u.apply_damage(3)
    assert u.hp == 7
    assert u.is_alive()
    u.apply_damage(10)  # overkill
    assert u.hp == 0
    assert not u.is_alive()


def test_unit_can_act():
    u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
    assert u.can_act()
    u.has_moved = True
    assert u.can_act()   # moved but not attacked yet
    u.has_attacked = True
    assert not u.can_act()


def test_dead_unit_cannot_act():
    u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
    u.hp = 0
    assert not u.can_act()
