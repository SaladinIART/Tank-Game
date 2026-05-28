"""
Tests for veterancy, healing (passive + active medic), and Zone-of-Control
movement restriction.
"""
from __future__ import annotations

import pytest

from src.engine.combat import (
    load_damage_matrix,
    predict_damage,
    resolve_attack,
)
from src.engine.hex import Hex
from src.engine.movement import compute_movement, is_engaged
from src.engine.stance_actions import (
    adjacent_friendly_patients,
    can_medic,
    medic_heal,
)
from src.engine.state import Faction, GameState
from src.engine.tile import Tile, load_terrain
from src.engine.unit import Unit, load_units
from src.engine.veterancy import (
    MAX_LEVEL,
    XP_FOR_CAPTURE,
    XP_FOR_DAMAGE,
    XP_FOR_KILL,
    XP_PER_LEVEL,
    award_xp,
    bonuses,
    level_for_xp,
    max_hp_for,
    rank_of,
)


@pytest.fixture(autouse=True)
def _load():
    load_terrain()
    load_units()
    load_damage_matrix()


def _two_unit_state(
    a_hex: Hex = Hex(0, 0),
    d_hex: Hex = Hex(1, 0),
):
    factions = [
        Faction(id="NATO",  name="NATO",  color=(0, 0, 0), credits=0, oil=0, is_ai=False),
        Faction(id="BRICS", name="BRICS", color=(0, 0, 0), credits=0, oil=0, is_ai=True),
    ]
    tiles = {Hex(q, r): Tile(Hex(q, r), "plain") for q in range(10) for r in range(10)}
    state = GameState(factions=factions, tiles=tiles)
    a = Unit(type_id="nato_inf_m", faction="NATO",  hex=a_hex, hp=10)
    d = Unit(type_id="brics_inf_m", faction="BRICS", hex=d_hex, hp=10)
    state.add_unit(a); state.add_unit(d)
    return state, a, d


# ---------------------------------------------------------------------------
# Veterancy: pure level / rank curve
# ---------------------------------------------------------------------------

class TestLevelCurve:
    def test_initial_xp_is_level_1(self):
        assert level_for_xp(0) == 1

    def test_xp_per_level_threshold(self):
        assert level_for_xp(XP_PER_LEVEL) == 2
        assert level_for_xp(XP_PER_LEVEL * 2) == 3

    def test_level_caps_at_max(self):
        assert level_for_xp(10 ** 6) == MAX_LEVEL

    def test_rank_buckets(self):
        # 5 levels per rank, 6 ranks
        assert rank_of(1)  == 0
        assert rank_of(4)  == 0
        assert rank_of(5)  == 1
        assert rank_of(10) == 2
        assert rank_of(15) == 3
        assert rank_of(20) == 4
        assert rank_of(25) == 5

    def test_max_level_rank_is_mythic(self):
        rb = bonuses(MAX_LEVEL)
        assert rb.name == "Mythic"
        assert rb.atk >= 3


# ---------------------------------------------------------------------------
# award_xp behaviour
# ---------------------------------------------------------------------------

class TestAwardXp:
    def test_basic_award_raises_level(self):
        u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
        assert u.level == 1
        award_xp(u, XP_PER_LEVEL)
        assert u.level == 2

    def test_xp_caps_at_max_level(self):
        u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
        award_xp(u, 10 ** 6)
        assert u.level == MAX_LEVEL
        # Further awards no-op
        before_xp = u.xp
        award_xp(u, 100)
        assert u.xp == before_xp

    def test_levelup_tops_up_hp_by_rank_delta(self):
        u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0), hp=5)
        # Push past level 15 (rank 3 → +2 hp)
        award_xp(u, XP_PER_LEVEL * 14)   # level 15
        assert u.level == 15
        # Max HP went up by 2 (rank 3) so heal-on-rankup adds 2.
        assert u.hp == 7

    def test_no_xp_for_zero_amount(self):
        u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
        award_xp(u, 0)
        assert u.level == 1 and u.xp == 0


# ---------------------------------------------------------------------------
# Combat awards XP correctly
# ---------------------------------------------------------------------------

class TestCombatXp:
    def test_attacker_gains_xp_per_damage(self):
        state, a, d = _two_unit_state()
        dmg = predict_damage(state, a, d)
        assert dmg > 0
        result = resolve_attack(state, a, d)
        # Attacker should have at least dmg XP from the hit
        assert a.xp >= dmg * XP_FOR_DAMAGE

    def test_killing_blow_grants_bonus(self):
        state, a, d = _two_unit_state()
        d.hp = 1                          # one-hit kill
        resolve_attack(state, a, d)
        assert d.uid not in state.units
        assert a.xp >= XP_FOR_KILL

    def test_high_rank_attacker_does_more_damage(self):
        state, a, d = _two_unit_state()
        a.level = 25; a.xp = 200
        boosted = predict_damage(state, a, d)
        # Reset attacker to rank 0 by direct field tweak (testing only)
        a.level = 1; a.xp = 0
        baseline = predict_damage(state, a, d)
        assert boosted > baseline


# ---------------------------------------------------------------------------
# Passive healing on owned capturable tiles
# ---------------------------------------------------------------------------

class TestPassiveHealing:
    def test_wounded_unit_on_owned_city_heals(self):
        state, a, _ = _two_unit_state(a_hex=Hex(2, 2))
        state.tiles[Hex(2, 2)] = Tile(Hex(2, 2), "city", owner_faction="NATO")
        a.hp = 3
        # End and re-start NATO turn to fire _on_turn_start.
        state.end_turn(); state.end_turn()
        assert a.hp == 5      # +2

    def test_no_heal_on_enemy_owned_tile(self):
        state, a, _ = _two_unit_state(a_hex=Hex(2, 2))
        state.tiles[Hex(2, 2)] = Tile(Hex(2, 2), "city", owner_faction="BRICS")
        a.hp = 3
        state.end_turn(); state.end_turn()
        assert a.hp == 3

    def test_no_heal_on_plain_terrain(self):
        state, a, _ = _two_unit_state(a_hex=Hex(2, 2))
        a.hp = 3
        state.end_turn(); state.end_turn()
        assert a.hp == 3

    def test_heal_caps_at_max_hp(self):
        state, a, _ = _two_unit_state(a_hex=Hex(2, 2))
        state.tiles[Hex(2, 2)] = Tile(Hex(2, 2), "city", owner_faction="NATO")
        a.hp = 9
        state.end_turn(); state.end_turn()
        assert a.hp == 10  # not 11

    def test_heal_respects_veterancy_max_hp(self):
        state, a, _ = _two_unit_state(a_hex=Hex(2, 2))
        state.tiles[Hex(2, 2)] = Tile(Hex(2, 2), "city", owner_faction="NATO")
        a.level = 25
        a.hp = max_hp_for(a) - 1  # one shy of cap
        state.end_turn(); state.end_turn()
        assert a.hp == max_hp_for(a)


# ---------------------------------------------------------------------------
# Engineer "medic" active heal
# ---------------------------------------------------------------------------

class TestMedicAction:
    def _engineer_and_patient(self):
        factions = [
            Faction(id="NATO",  name="NATO",  color=(0, 0, 0), credits=0, oil=0, is_ai=False),
            Faction(id="BRICS", name="BRICS", color=(0, 0, 0), credits=0, oil=0, is_ai=True),
        ]
        tiles = {Hex(q, r): Tile(Hex(q, r), "plain") for q in range(6) for r in range(6)}
        state = GameState(factions=factions, tiles=tiles)
        eng = Unit(type_id="nato_engineer", faction="NATO", hex=Hex(2, 2), hp=10)
        pat = Unit(type_id="nato_inf_l",   faction="NATO", hex=Hex(3, 2), hp=4)
        state.add_unit(eng); state.add_unit(pat)
        return state, eng, pat

    def test_can_medic_when_adjacent_and_wounded(self):
        state, eng, pat = self._engineer_and_patient()
        assert can_medic(state, eng, pat)

    def test_cannot_medic_non_adjacent(self):
        state, eng, pat = self._engineer_and_patient()
        pat.hex = Hex(5, 5)
        assert not can_medic(state, eng, pat)

    def test_cannot_medic_full_hp(self):
        state, eng, pat = self._engineer_and_patient()
        pat.hp = 10
        assert not can_medic(state, eng, pat)

    def test_cannot_medic_enemy(self):
        state, eng, pat = self._engineer_and_patient()
        pat.faction = "BRICS"
        assert not can_medic(state, eng, pat)

    def test_medic_consumes_attack_slot(self):
        state, eng, pat = self._engineer_and_patient()
        medic_heal(state, eng, pat)
        assert eng.has_attacked

    def test_medic_heals_capped_amount(self):
        state, eng, pat = self._engineer_and_patient()
        before = pat.hp
        healed = medic_heal(state, eng, pat)
        assert healed > 0
        assert pat.hp == before + healed

    def test_non_engineer_cannot_medic(self):
        state, eng, pat = self._engineer_and_patient()
        # Replace engineer with regular infantry
        eng2 = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(2, 2), hp=10)
        state.units.pop(eng.uid)
        state.units[eng2.uid] = eng2
        assert not can_medic(state, eng2, pat)

    def test_adjacent_patients_list(self):
        state, eng, pat = self._engineer_and_patient()
        patients = adjacent_friendly_patients(state, eng)
        assert pat in patients


# ---------------------------------------------------------------------------
# Zone of Control: engaged units restricted to 1 hex
# ---------------------------------------------------------------------------

class TestEngagement:
    def test_unit_alone_not_engaged(self):
        state, a, d = _two_unit_state(a_hex=Hex(0, 0), d_hex=Hex(8, 8))
        assert not is_engaged(state, a)

    def test_unit_adjacent_to_enemy_is_engaged(self):
        state, a, d = _two_unit_state(a_hex=Hex(0, 0), d_hex=Hex(1, 0))
        assert is_engaged(state, a)
        assert is_engaged(state, d)

    def test_engaged_movement_capped_at_1_hex(self):
        state, a, d = _two_unit_state(a_hex=Hex(2, 2), d_hex=Hex(3, 2))
        mv = compute_movement(state, a)
        assert mv.engaged is True
        # Every reachable hex must be at most 1 step from origin
        for h, cost in mv.reachable.items():
            assert cost <= 1

    def test_disengaged_full_movement(self):
        state, a, _ = _two_unit_state(a_hex=Hex(2, 2), d_hex=Hex(9, 9))
        mv = compute_movement(state, a)
        assert mv.engaged is False
        # nato_inf_m has move=3
        max_cost = max(mv.reachable.values()) if mv.reachable else 0
        assert max_cost >= 2, "Disengaged infantry should reach 2+ hexes deep"

    def test_friendly_adjacent_does_not_engage(self):
        state, a, d = _two_unit_state()
        # Replace enemy with friendly
        d.faction = "NATO"
        assert not is_engaged(state, a)

    def test_flying_unit_never_engaged(self):
        state, a, d = _two_unit_state(a_hex=Hex(2, 2), d_hex=Hex(3, 2))
        # Swap NATO inf for a jet
        state.units.pop(a.uid)
        jet = Unit(type_id="nato_jet_l", faction="NATO", hex=Hex(2, 2), hp=10)
        state.units[jet.uid] = jet
        assert jet.unit_type.flying
        assert not is_engaged(state, jet)


# ---------------------------------------------------------------------------
# Save round-trip preserves level + xp
# ---------------------------------------------------------------------------

class TestSaveRoundTrip:
    def test_level_xp_persist(self, tmp_path):
        from src.persistence.save import load_state, save_state
        state, a, _ = _two_unit_state()
        a.level = 12; a.xp = 60
        path = tmp_path / "lvl_save.json"
        save_state(state, path, scenario_slug="test")
        loaded, _ = load_state(path)
        assert loaded.units[a.uid].level == 12
        assert loaded.units[a.uid].xp == 60

    def test_legacy_save_defaults_to_level_1(self, tmp_path):
        import json
        from src.persistence.save import load_state, save_state
        state, _, _ = _two_unit_state()
        path = tmp_path / "legacy.json"
        save_state(state, path, scenario_slug="test")
        data = json.loads(path.read_text(encoding="utf-8"))
        for u in data["units"]:
            u.pop("level", None); u.pop("xp", None)
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded, _ = load_state(path)
        for u in loaded.units.values():
            assert u.level == 1 and u.xp == 0
