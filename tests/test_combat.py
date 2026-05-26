"""Tests for combat.py: damage matrix, prediction, counter, removal."""
from __future__ import annotations

import pytest

from src.engine.combat import (
    AttackResult,
    attack_targets,
    base_damage,
    can_attack,
    load_damage_matrix,
    predict_damage,
    predict_exchange,
    resolve_attack,
)
from src.engine.hex import Hex
from src.engine.state import Faction, GameState
from src.engine.tile import Tile, load_terrain
from src.engine.unit import Unit, load_units


@pytest.fixture(autouse=True)
def loaded():
    load_terrain()
    load_units()
    load_damage_matrix()


def _state(*pairs: tuple[tuple[int, int], str]) -> GameState:
    nato = Faction(id="NATO", name="NATO", color=(0, 0, 200), credits=500, oil=5, is_ai=False)
    brics = Faction(id="BRICS", name="BRICS", color=(200, 0, 0), credits=500, oil=5)
    tiles = {Hex(q, r): Tile(Hex(q, r), tid) for (q, r), tid in pairs}
    return GameState(factions=[nato, brics], tiles=tiles)


# ---------------------------------------------------------------------------
# Damage matrix structure
# ---------------------------------------------------------------------------

def test_matrix_loads_basic_entries():
    assert base_damage("infantry", "infantry") > 0
    assert base_damage("infantry", "vehicle") >= 0


def test_aa_strong_vs_jet():
    assert base_damage("aa", "jet") >= 7


def test_ground_cannot_hit_jet():
    # Ground units (no AA/jet/heli) deal 0 to jets.
    assert base_damage("infantry", "jet") == 0
    assert base_damage("vehicle", "jet") == 0
    assert base_damage("artillery", "jet") == 0


def test_artillery_strong_vs_ground():
    assert base_damage("artillery", "infantry") >= 7
    assert base_damage("artillery", "vehicle") >= 6


# ---------------------------------------------------------------------------
# predict_damage
# ---------------------------------------------------------------------------

def test_full_hp_full_attack_on_plain():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    assert predict_damage(s, a, d) == base_damage("infantry", "infantry")


def test_terrain_defense_reduces_damage():
    s = _state(((0, 0), "plain"), ((1, 0), "city"))  # city has def +2
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    plain = base_damage("infantry", "infantry")
    actual = predict_damage(s, a, d)
    assert actual == round(plain * 1.0 * (1 - 2 / 10))
    assert actual < plain


def test_low_hp_attacker_does_less():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    a.hp = 5
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    expected = round(base_damage("infantry", "infantry") * 0.5)
    assert predict_damage(s, a, d) == expected


def test_zero_base_zero_damage():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_jet_l", "BRICS", Hex(1, 0))  # infantry → jet = 0
    s.add_unit(a); s.add_unit(d)
    assert predict_damage(s, a, d) == 0


# ---------------------------------------------------------------------------
# can_attack
# ---------------------------------------------------------------------------

def test_can_attack_adjacent_enemy():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    assert can_attack(s, a, d)


def test_cannot_attack_friendly():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "NATO", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    assert not can_attack(s, a, d)


def test_cannot_attack_out_of_range():
    s = _state(((0, 0), "plain"), ((5, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))  # range 1
    d = Unit("nato_inf_l", "BRICS", Hex(5, 0))
    s.add_unit(a); s.add_unit(d)
    assert not can_attack(s, a, d)


def test_artillery_cannot_attack_adjacent():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_artillery_l", "NATO", Hex(0, 0))  # range 3-5
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    assert not can_attack(s, a, d)


def test_artillery_attacks_at_distance_4():
    s = _state(((0, 0), "plain"), ((4, 0), "plain"))
    a = Unit("nato_artillery_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(4, 0))
    s.add_unit(a); s.add_unit(d)
    assert can_attack(s, a, d)


def test_cannot_attack_if_zero_base():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_jet_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    assert not can_attack(s, a, d)


def test_cannot_attack_when_has_attacked():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    a.has_attacked = True
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    assert not can_attack(s, a, d)


def test_cannot_attack_dead():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    d.hp = 0
    s.add_unit(a); s.add_unit(d)
    assert not can_attack(s, a, d)


# ---------------------------------------------------------------------------
# resolve_attack
# ---------------------------------------------------------------------------

def test_resolve_attack_applies_predicted_damage():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    predicted = predict_damage(s, a, d)
    r = resolve_attack(s, a, d)
    assert r.damage_dealt == predicted
    assert d.hp == 10 - predicted


def test_resolve_attack_sets_has_attacked():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    resolve_attack(s, a, d)
    assert a.has_attacked


def test_resolve_attack_raises_on_illegal():
    s = _state(((0, 0), "plain"), ((5, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(5, 0))
    s.add_unit(a); s.add_unit(d)
    with pytest.raises(ValueError):
        resolve_attack(s, a, d)


def test_killed_defender_removed_from_state():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_vehicle_m", "NATO", Hex(0, 0))  # high atk
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    d.hp = 1
    s.add_unit(a); s.add_unit(d)
    r = resolve_attack(s, a, d)
    assert r.defender_killed
    assert d.uid not in s.units


def test_counter_attack_hits_back():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    r = resolve_attack(s, a, d)
    assert d.is_alive()                 # survives first hit
    assert r.counter_damage > 0
    assert a.hp == 10 - r.counter_damage


def test_no_counter_if_defender_dies():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_vehicle_m", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    d.hp = 1
    s.add_unit(a); s.add_unit(d)
    r = resolve_attack(s, a, d)
    assert r.counter_damage == 0
    assert a.hp == 10


def test_no_counter_if_attacker_out_of_defender_range():
    """Artillery hits infantry from distance 4. Infantry range=1 → no counter."""
    s = _state(((0, 0), "plain"), ((4, 0), "plain"))
    a = Unit("nato_artillery_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(4, 0))
    s.add_unit(a); s.add_unit(d)
    r = resolve_attack(s, a, d)
    assert r.counter_damage == 0
    assert a.hp == 10


def test_counter_uses_defenders_post_hit_hp():
    """Counter damage should scale with defender's HP *after* taking the hit."""
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)

    pred_atk, pred_counter = predict_exchange(s, a, d)
    r = resolve_attack(s, a, d)
    assert r.damage_dealt == pred_atk
    assert r.counter_damage == pred_counter


def test_attacker_dies_in_counter_is_removed():
    """Wounded attacker dies to defender's counter."""
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    a.hp = 1  # one counter-hit and we're done
    d = Unit("nato_vehicle_m", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    r = resolve_attack(s, a, d)
    assert r.attacker_killed
    assert a.uid not in s.units


# ---------------------------------------------------------------------------
# attack_targets
# ---------------------------------------------------------------------------

def test_attack_targets_lists_in_range_enemies():
    s = _state(
        ((0, 0), "plain"), ((1, 0), "plain"),
        ((2, 0), "plain"), ((5, 0), "plain"),
    )
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    d1 = Unit("nato_inf_l", "BRICS", Hex(1, 0))   # in range
    d2 = Unit("nato_inf_l", "BRICS", Hex(5, 0))   # out of range
    friendly = Unit("nato_inf_l", "NATO", Hex(2, 0))
    s.add_unit(a); s.add_unit(d1); s.add_unit(d2); s.add_unit(friendly)
    targets = attack_targets(s, a)
    uids = {t.uid for t in targets}
    assert d1.uid in uids
    assert d2.uid not in uids
    assert friendly.uid not in uids


def test_attack_targets_empty_after_has_attacked():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_inf_l", "NATO", Hex(0, 0))
    a.has_attacked = True
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    assert attack_targets(s, a) == []


# ---------------------------------------------------------------------------
# predict_exchange (UI hook)
# ---------------------------------------------------------------------------

def test_predict_exchange_matches_resolve():
    s = _state(((0, 0), "plain"), ((1, 0), "forest"))
    a = Unit("nato_recon", "NATO", Hex(0, 0))
    d = Unit("nato_vehicle_l", "BRICS", Hex(1, 0))
    s.add_unit(a); s.add_unit(d)
    pred = predict_exchange(s, a, d)
    r = resolve_attack(s, a, d)
    assert pred == (r.damage_dealt, r.counter_damage)


def test_predict_exchange_zero_counter_when_lethal():
    s = _state(((0, 0), "plain"), ((1, 0), "plain"))
    a = Unit("nato_vehicle_m", "NATO", Hex(0, 0))
    d = Unit("nato_inf_l", "BRICS", Hex(1, 0))
    d.hp = 1
    s.add_unit(a); s.add_unit(d)
    atk, counter = predict_exchange(s, a, d)
    assert atk >= 1
    assert counter == 0
