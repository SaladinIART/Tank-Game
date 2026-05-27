"""
Tests for CP-23: Skirmish mode.
Covers map loading, procgen, GameState builder, victory condition installation.
"""
from __future__ import annotations

import pytest
from pathlib import Path

from src.engine.hex import Hex
from src.engine.tile import Tile, load_terrain
from src.engine.procgen import generate_map
from src.engine.skirmish import load_skirmish_map, build_skirmish_state
from src.engine.victory import Outcome, DestroyHQ, HoldTiles, OwnAllOfTerrain

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA = Path("data/skirmish")


def _two_player_state(map_path, victory_types=None):
    tiles, hq_pos, meta = load_skirmish_map(map_path)
    return build_skirmish_state(
        tiles=tiles,
        hq_positions=hq_pos,
        player_faction="NATO",
        ai_factions=["BRICS"],
        victory_types=victory_types or ["destroy_hq"],
    )


def _three_player_state(map_path, victory_types=None):
    tiles, hq_pos, meta = load_skirmish_map(map_path)
    return build_skirmish_state(
        tiles=tiles,
        hq_positions=hq_pos,
        player_faction="NATO",
        ai_factions=["BRICS", "GUERILLA"],
        victory_types=victory_types or ["destroy_hq"],
    )


# ---------------------------------------------------------------------------
# load_skirmish_map — canned maps
# ---------------------------------------------------------------------------

class TestLoadSkirmishMapPlains:
    PATH = DATA / "map_plains.json"

    def test_returns_tiles_dict(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert isinstance(tiles, dict)
        assert len(tiles) > 0

    def test_correct_dimensions(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert meta["width"] == 16
        assert meta["height"] == 12
        assert len(tiles) == 16 * 12

    def test_has_three_hq_positions(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert len(hq_pos) == 3

    def test_meta_name(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert meta["name"] == "Plains"

    def test_has_neutral_cities(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        cities = [t for t in tiles.values() if t.terrain_id == "city"]
        assert len(cities) >= 2

    def test_has_oil_wells(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        oils = [t for t in tiles.values() if t.terrain_id == "oil_well"]
        assert len(oils) >= 1


class TestLoadSkirmishMapValley:
    PATH = DATA / "map_valley.json"

    def test_correct_dimensions(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert meta["width"] == 20
        assert meta["height"] == 14

    def test_has_rivers(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        rivers = [t for t in tiles.values() if t.terrain_id == "river"]
        assert len(rivers) >= 4

    def test_has_bridges(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        bridges = [t for t in tiles.values() if t.terrain_id == "bridge"]
        assert len(bridges) >= 2

    def test_meta_name(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert meta["name"] == "Valley"


class TestLoadSkirmishMapFrontier:
    PATH = DATA / "map_frontier.json"

    def test_correct_dimensions(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert meta["width"] == 24
        assert meta["height"] == 16

    def test_has_mountains(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        mountains = [t for t in tiles.values() if t.terrain_id == "mountain"]
        assert len(mountains) >= 8

    def test_has_roads(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        roads = [t for t in tiles.values() if t.terrain_id == "road"]
        assert len(roads) >= 4

    def test_meta_name(self):
        load_terrain()
        tiles, hq_pos, meta = load_skirmish_map(self.PATH)
        assert meta["name"] == "Frontier"


# ---------------------------------------------------------------------------
# generate_map (procgen)
# ---------------------------------------------------------------------------

class TestProcgenMap:
    def test_returns_dict_with_expected_keys(self):
        result = generate_map(seed=42)
        assert "tiles" in result
        assert "hq_positions" in result
        assert "width" in result
        assert "height" in result
        assert "seed" in result

    def test_tile_count_matches_dimensions(self):
        result = generate_map(width=20, height=14, seed=1)
        assert len(result["tiles"]) == 20 * 14

    def test_seeded_deterministic(self):
        r1 = generate_map(seed=12345)
        r2 = generate_map(seed=12345)
        terrains1 = {h: t.terrain_id for h, t in r1["tiles"].items()}
        terrains2 = {h: t.terrain_id for h, t in r2["tiles"].items()}
        assert terrains1 == terrains2

    def test_different_seeds_differ(self):
        r1 = generate_map(seed=1)
        r2 = generate_map(seed=2)
        terrains1 = {h: t.terrain_id for h, t in r1["tiles"].items()}
        terrains2 = {h: t.terrain_id for h, t in r2["tiles"].items()}
        assert terrains1 != terrains2

    def test_three_hq_positions(self):
        result = generate_map(seed=7)
        assert len(result["hq_positions"]) == 3

    def test_hq_safety_cleared(self):
        """HQ hexes must be plain so builder can overwrite with 'hq'."""
        result = generate_map(seed=99)
        for hq_q, hq_r in result["hq_positions"]:
            h = Hex(hq_q, hq_r)
            assert result["tiles"][h].terrain_id == "plain"

    def test_has_some_terrain_variety(self):
        result = generate_map(seed=42)
        terrain_types = {t.terrain_id for t in result["tiles"].values()}
        # Should have at least plain + one of mountain/forest/river
        assert "plain" in terrain_types
        assert len(terrain_types) > 1

    def test_seed_stored_in_result(self):
        result = generate_map(seed=555)
        assert result["seed"] == 555

    def test_autoseed_assigned(self):
        result = generate_map()
        assert isinstance(result["seed"], int)


# ---------------------------------------------------------------------------
# build_skirmish_state — structure
# ---------------------------------------------------------------------------

class TestBuildSkirmishStateBasic:
    def setup_method(self):
        load_terrain()
        self.tiles, self.hq_pos, _ = load_skirmish_map(DATA / "map_plains.json")

    def test_two_player_factions_count(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        assert len(state.factions) == 2

    def test_three_player_factions_count(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS", "GUERILLA"], ["destroy_hq"])
        assert len(state.factions) == 3

    def test_player_is_not_ai(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        nato = next(f for f in state.factions if f.id == "NATO")
        assert nato.is_ai is False

    def test_ai_factions_are_ai(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS", "GUERILLA"], ["destroy_hq"])
        brics = next(f for f in state.factions if f.id == "BRICS")
        grl = next(f for f in state.factions if f.id == "GUERILLA")
        assert brics.is_ai is True
        assert grl.is_ai is True

    def test_hq_tiles_placed(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        hq_tiles = [t for t in state.tiles.values() if t.terrain_id == "hq"]
        assert len(hq_tiles) == 2  # NATO + BRICS

    def test_hq_owned_by_correct_faction(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        nato_hq = state.tiles[Hex(*self.hq_pos[0])]
        brics_hq = state.tiles[Hex(*self.hq_pos[1])]
        assert nato_hq.owner_faction == "NATO"
        assert brics_hq.owner_faction == "BRICS"

    def test_starting_units_placed(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        nato_units = [u for u in state.units.values() if u.faction == "NATO"]
        brics_units = [u for u in state.units.values() if u.faction == "BRICS"]
        assert len(nato_units) >= 1
        assert len(brics_units) >= 1

    def test_starter_unit_type_ids(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        nato_type_ids = {u.type_id for u in state.units.values() if u.faction == "NATO"}
        # At least one of the NATO starter types should be present
        assert any(t in nato_type_ids for t in ["nato_inf_l", "nato_engineer", "nato_recon"])

    def test_factions_have_starting_credits(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        for f in state.factions:
            assert f.credits == 600

    def test_outcomes_all_pending(self):
        """outcomes dict starts empty (PENDING is the default when absent)."""
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        for fid in ["NATO", "BRICS"]:
            # Before any end_turn call, outcomes is empty or PENDING — not WON/LOST.
            outcome = state.outcomes.get(fid)
            assert outcome in (None, Outcome.PENDING)


# ---------------------------------------------------------------------------
# build_skirmish_state — victory conditions
# ---------------------------------------------------------------------------

class TestBuildSkirmishVictory:
    def setup_method(self):
        load_terrain()
        self.tiles, self.hq_pos, _ = load_skirmish_map(DATA / "map_plains.json")

    def test_destroy_hq_installed(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        cfg = state.victory_configs["NATO"]
        destroy_hq_conds = [c for c in cfg.win_conditions if isinstance(c, DestroyHQ)]
        assert len(destroy_hq_conds) == 1
        assert destroy_hq_conds[0].target_faction == "BRICS"

    def test_hold_cities_installed_when_enough_neutral_cities(self):
        """Plains map has ≥2 neutral cities so hold_cities should be installed."""
        state = build_skirmish_state(
            self.tiles, self.hq_pos, "NATO", ["BRICS"], ["hold_cities"]
        )
        cfg = state.victory_configs["NATO"]
        hold = [c for c in cfg.win_conditions if isinstance(c, HoldTiles)]
        assert len(hold) == 1
        assert hold[0].turns_required == 8

    def test_capture_oil_installed_when_oil_wells_exist(self):
        """Plains map has ≥1 oil well so capture_oil should be installed."""
        state = build_skirmish_state(
            self.tiles, self.hq_pos, "NATO", ["BRICS"], ["capture_oil"]
        )
        cfg = state.victory_configs["NATO"]
        oil = [c for c in cfg.win_conditions if isinstance(c, OwnAllOfTerrain)]
        assert len(oil) == 1
        assert oil[0].terrain_id == "oil_well"

    def test_multiple_victory_types(self):
        state = build_skirmish_state(
            self.tiles, self.hq_pos, "NATO", ["BRICS"],
            ["destroy_hq", "hold_cities", "capture_oil"]
        )
        cfg = state.victory_configs["NATO"]
        assert len(cfg.win_conditions) >= 2

    def test_lose_condition_is_own_hq_destroyed(self):
        state = build_skirmish_state(self.tiles, self.hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        cfg = state.victory_configs["NATO"]
        lose_dhq = [c for c in cfg.lose_conditions if isinstance(c, DestroyHQ)]
        assert any(c.target_faction == "NATO" for c in lose_dhq)

    def test_three_player_each_has_own_victory_config(self):
        state = build_skirmish_state(
            self.tiles, self.hq_pos, "NATO", ["BRICS", "GUERILLA"], ["destroy_hq"]
        )
        for fid in ["NATO", "BRICS", "GUERILLA"]:
            assert fid in state.victory_configs

    def test_three_player_nato_must_destroy_both_opponents(self):
        state = build_skirmish_state(
            self.tiles, self.hq_pos, "NATO", ["BRICS", "GUERILLA"], ["destroy_hq"]
        )
        cfg = state.victory_configs["NATO"]
        targets = {c.target_faction for c in cfg.win_conditions if isinstance(c, DestroyHQ)}
        assert "BRICS" in targets
        assert "GUERILLA" in targets


# ---------------------------------------------------------------------------
# build_skirmish_state — end_turn smoke test
# ---------------------------------------------------------------------------

class TestSkirmishEndTurn:
    def test_end_turn_no_crash(self):
        load_terrain()
        tiles, hq_pos, _ = load_skirmish_map(DATA / "map_plains.json")
        state = build_skirmish_state(tiles, hq_pos, "NATO", ["BRICS"], ["destroy_hq"])
        initial_turn = state.turn_number
        state.end_turn()
        assert state.turn_number >= initial_turn

    def test_procgen_state_end_turn(self):
        load_terrain()
        result = generate_map(seed=77)
        state = build_skirmish_state(
            result["tiles"], result["hq_positions"],
            "NATO", ["BRICS"], ["destroy_hq"]
        )
        state.end_turn()
        assert state.turn_number >= 1
