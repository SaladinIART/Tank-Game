"""
Tests for CP-26: balance tuning + insane difficulty.

These tests lock in the post-balance-pass numbers so an accidental edit
to ``data/units.json``, the damage matrix, or the AI weights surfaces
immediately in CI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ai.heuristic import DEFAULT_WEIGHTS, _score_move
from src.engine.hex import Hex
from src.engine.scenario import load_scenario
from src.engine.state import GameState
from src.engine.tile import load_terrain
from src.engine.unit import Unit, load_units, get as get_unit_type

import main as game_main


# ---------------------------------------------------------------------------
# Faction unit parity — quantity-over-quality must not become strict-better
# ---------------------------------------------------------------------------

class TestFactionParity:
    """
    Asymmetric design: BRICS units should be *cheaper* than NATO equivalents
    but **no stronger** in raw atk.  This catches buffs that accidentally
    make BRICS strictly better at the same role.
    """

    def setup_method(self):
        load_units()
        self.units = json.load(open("data/units.json"))["unit_types"]
        self.units = [u for u in self.units if isinstance(u, dict) and "id" in u]
        self.by_id = {u["id"]: u for u in self.units}

    def _pair_atk_ok(self, nato_id: str, brics_id: str) -> None:
        n, b = self.by_id[nato_id], self.by_id[brics_id]
        assert b["atk"] <= n["atk"], (
            f"BRICS {brics_id} atk={b['atk']} exceeds NATO {nato_id} atk={n['atk']}"
        )
        assert b["cost_credits"] <= n["cost_credits"], (
            f"BRICS {brics_id} cost={b['cost_credits']} exceeds NATO {nato_id} cost={n['cost_credits']}"
        )

    def test_inf_l_brics_not_stronger(self):
        self._pair_atk_ok("nato_inf_l", "brics_inf_l")

    def test_recon_brics_not_stronger(self):
        self._pair_atk_ok("nato_recon", "brics_recon")

    def test_vehicle_l_brics_not_stronger(self):
        self._pair_atk_ok("nato_vehicle_l", "brics_vehicle_l")

    def test_inf_m_brics_not_stronger(self):
        self._pair_atk_ok("nato_inf_m", "brics_inf_m")

    def test_vehicle_m_brics_not_stronger(self):
        self._pair_atk_ok("nato_vehicle_m", "brics_vehicle_m")


# ---------------------------------------------------------------------------
# Engineers across factions: should be fast + slightly armoured + capture
# ---------------------------------------------------------------------------

class TestEngineerBuff:
    """Post-balance: engineers must be mobile (move>=3) and have def>=1
    so they survive the trek to enemy HQ.  This catches regressions to the
    original slow + glass engineer profile.
    """

    @pytest.mark.parametrize("eng_id", [
        "nato_engineer", "brics_engineer", "guerilla_engineer",
    ])
    def test_engineer_speed_and_defense(self, eng_id):
        load_units()
        ut = get_unit_type(eng_id)
        assert ut.move >= 3, f"{eng_id} too slow (move={ut.move})"
        assert ut.def_ >= 1, f"{eng_id} too fragile (def={ut.def_})"
        assert ut.can_capture, f"{eng_id} cannot capture"


# ---------------------------------------------------------------------------
# AI weights — sane defaults
# ---------------------------------------------------------------------------

class TestAIWeights:
    def test_approach_capture_target_present(self):
        assert "approach_capture_target" in DEFAULT_WEIGHTS
        assert DEFAULT_WEIGHTS["approach_capture_target"] > 0

    def test_suicide_penalty_dominates_kill_bonus(self):
        """Killing one unit should NOT justify dying yourself."""
        assert DEFAULT_WEIGHTS["suicide_penalty"] > DEFAULT_WEIGHTS["attack_kill_bonus"]

    def test_engineer_pull_pulls_to_enemy_hq(self):
        """An engineer's score for moving toward enemy HQ should beat the move_base."""
        load_terrain()
        load_units()
        # Build a minimal state with NATO engineer + BRICS HQ tile.
        from src.engine.tile import Tile
        tiles = {Hex(q, r): Tile(Hex(q, r), "plain") for q in range(20) for r in range(10)}
        tiles[Hex(15, 5)] = Tile(Hex(15, 5), "hq", owner_faction="BRICS")
        from src.engine.state import Faction
        factions = [
            Faction(id="NATO",  name="NATO",  color=(0, 0, 0), credits=500, oil=5),
            Faction(id="BRICS", name="BRICS", color=(0, 0, 0), credits=500, oil=5, is_ai=True),
        ]
        state = GameState(factions=factions, tiles=tiles)
        eng = Unit(type_id="nato_engineer", faction="NATO", hex=Hex(2, 5))
        state.add_unit(eng)

        # Dest closer to enemy HQ should beat dest at start hex distance.
        closer = Hex(5, 5)
        farther = Hex(2, 5)
        s_closer  = _score_move(state, eng, closer,  DEFAULT_WEIGHTS)
        s_farther = _score_move(state, eng, farther, DEFAULT_WEIGHTS)
        assert s_closer > s_farther, (
            f"Engineer pull broken: closer={s_closer:.1f} farther={s_farther:.1f}"
        )


# ---------------------------------------------------------------------------
# Difficulty modifier
# ---------------------------------------------------------------------------

class TestDifficultyModifier:
    def setup_method(self):
        load_terrain()
        load_units()
        self.state, self.meta = load_scenario("data/scenarios/m1.json")
        # Snapshot starting credits for AI factions
        self.before = {f.id: (f.credits, f.oil) for f in self.state.factions if f.is_ai}

    def test_normal_no_change(self):
        game_main._apply_difficulty(self.state, self.meta, "normal")
        for f in self.state.factions:
            if f.is_ai:
                assert (f.credits, f.oil) == self.before[f.id]

    def test_hard_bumps_credits_and_personality(self):
        game_main._apply_difficulty(self.state, self.meta, "hard")
        for f in self.state.factions:
            if f.is_ai:
                pre_c, pre_o = self.before[f.id]
                assert f.credits == pre_c + 400
                assert f.oil     == pre_o + 3
                assert f.id in self.meta["personalities"]
                assert self.meta["personalities"][f.id]["name"] == "aggressive"

    def test_insane_bumps_more_and_predator_personality(self):
        game_main._apply_difficulty(self.state, self.meta, "insane")
        for f in self.state.factions:
            if f.is_ai:
                pre_c, pre_o = self.before[f.id]
                assert f.credits == pre_c + 900
                assert f.oil     == pre_o + 6
                assert f.id in self.meta["personalities"]
                assert self.meta["personalities"][f.id]["name"] == "predator"

    def test_insane_personality_has_predator_weights(self):
        game_main._apply_difficulty(self.state, self.meta, "insane")
        for f in self.state.factions:
            if f.is_ai:
                w = self.meta["personalities"][f.id]["weights"]
                # Predator should be more aggressive than aggressive
                assert w["attack_damage"] > 5.0
                assert w["attack_kill_bonus"] > 80.0
                assert w["approach_enemy_hq"] > 40.0
                assert w["threat_aversion_base"] < 0.2

    def test_insane_strictly_harder_than_hard(self):
        """Insane bumps must exceed Hard bumps."""
        # Hard
        s1, m1 = load_scenario("data/scenarios/m1.json")
        game_main._apply_difficulty(s1, m1, "hard")
        # Insane
        s2, m2 = load_scenario("data/scenarios/m1.json")
        game_main._apply_difficulty(s2, m2, "insane")
        for f1, f2 in zip(s1.factions, s2.factions):
            if f1.is_ai:
                assert f2.credits > f1.credits
                assert f2.oil > f1.oil

    def test_unknown_difficulty_no_op(self):
        game_main._apply_difficulty(self.state, self.meta, "nonsense")
        for f in self.state.factions:
            if f.is_ai:
                assert (f.credits, f.oil) == self.before[f.id]


# ---------------------------------------------------------------------------
# AI personality coverage
# ---------------------------------------------------------------------------

class TestPredatorPersonality:
    """The Insane-tier 'predator' personality must reference real weight keys."""

    def test_predator_keys_are_real(self):
        from src.ai.heuristic import DEFAULT_WEIGHTS
        load_terrain()
        load_units()
        state, meta = load_scenario("data/scenarios/m1.json")
        game_main._apply_difficulty(state, meta, "insane")
        for fid, pd in meta["personalities"].items():
            for k in pd["weights"]:
                assert k in DEFAULT_WEIGHTS, f"Predator overrides unknown weight: {k}"


# ---------------------------------------------------------------------------
# Smoke: insane AI does not crash inside take_turn
# ---------------------------------------------------------------------------

class TestInsaneSmoke:
    def test_insane_3_turns_no_crash(self):
        from src.ai.heuristic import take_turn
        from src.ai.personality import from_dict as personality_from_dict
        state, meta = load_scenario("data/scenarios/m1.json")
        game_main._apply_difficulty(state, meta, "insane")
        # Force both sides AI for the smoke
        for f in state.factions:
            f.is_ai = True
        for _ in range(6):  # 3 rounds = 6 end_turns
            if state.game_over:
                break
            fid = state.active_faction.id
            pd = meta.get("personalities", {}).get(fid)
            pers = personality_from_dict(pd) if pd else None
            take_turn(state, fid, pers)
            state.end_turn()
        # If we got here without exception, the predator AI executes cleanly
        assert state.turn_number >= 1
