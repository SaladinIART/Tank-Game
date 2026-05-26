import pytest
from src.engine.hex import Hex
from src.engine.tile import (
    CAPTURE_TURNS,
    MOVE_CATEGORIES,
    Tile,
    TerrainType,
    all_terrain,
    get,
    load_terrain,
)


@pytest.fixture(autouse=True)
def ensure_loaded():
    load_terrain()


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def test_all_expected_terrain_ids_present():
    t = all_terrain()
    for tid in ("plain", "forest", "mountain", "road", "river", "bridge",
                "city", "oil_well", "airfield", "hq"):
        assert tid in t, f"Missing terrain id: {tid}"


def test_terrain_types_are_correct_type():
    for t in all_terrain().values():
        assert isinstance(t, TerrainType)


# ---------------------------------------------------------------------------
# Passability — acceptance criteria from plan
# ---------------------------------------------------------------------------

def test_vehicle_cannot_enter_mountain():
    mountain = get("mountain")
    assert not mountain.passable("tracked"), "Tracked should be blocked by mountain"
    assert not mountain.passable("wheeled"), "Wheeled should be blocked by mountain"
    assert not mountain.passable("towed"),   "Towed should be blocked by mountain"


def test_infantry_can_enter_mountain():
    mountain = get("mountain")
    assert mountain.passable("foot"), "Infantry (foot) must be able to enter mountain"


def test_air_can_always_enter_mountain():
    assert get("mountain").passable("air")


def test_river_blocks_all_ground_units():
    river = get("river")
    for cat in ("foot", "wheeled", "tracked", "towed"):
        assert not river.passable(cat), f"{cat} should not cross river"


def test_river_passable_by_air():
    assert get("river").passable("air")


def test_bridge_passable_by_all():
    bridge = get("bridge")
    for cat in MOVE_CATEGORIES:
        assert bridge.passable(cat), f"Bridge must be passable by {cat}"


def test_move_cost_none_for_impassable():
    assert get("mountain").get_move_cost("tracked") is None
    assert get("river").get_move_cost("foot") is None


def test_move_cost_positive_for_passable():
    plain = get("plain")
    for cat in MOVE_CATEGORIES:
        cost = plain.get_move_cost(cat)
        assert cost is not None and cost >= 1


# ---------------------------------------------------------------------------
# Terrain properties
# ---------------------------------------------------------------------------

def test_mountain_has_highest_defense():
    mountain_def = get("mountain").defense_bonus
    for tid, t in all_terrain().items():
        if tid != "hq":
            assert mountain_def >= t.defense_bonus

def test_mountain_blocks_los():
    assert get("mountain").blocks_los
    assert not get("plain").blocks_los
    assert not get("forest").blocks_los


def test_forest_slows_vehicles_but_not_air():
    forest = get("forest")
    assert forest.get_move_cost("tracked") > forest.get_move_cost("foot")
    assert forest.get_move_cost("air") == 1


def test_capturable_tiles():
    expected_capturable = {"city", "oil_well", "airfield", "hq"}
    for tid, t in all_terrain().items():
        if tid in expected_capturable:
            assert t.capturable, f"{tid} should be capturable"
        else:
            assert not t.capturable, f"{tid} should not be capturable"


def test_income_sources():
    assert get("city").income_credits == 100
    assert get("city").income_oil == 0
    assert get("oil_well").income_oil == 2
    assert get("oil_well").income_credits == 0
    assert get("hq").income_credits == 200
    assert get("airfield").income_credits == 50
    assert get("plain").income_credits == 0
    assert get("plain").income_oil == 0


def test_hq_flag():
    assert get("hq").is_hq
    for tid in ("city", "oil_well", "airfield", "plain"):
        assert not get(tid).is_hq


def test_all_terrain_have_valid_color():
    for t in all_terrain().values():
        assert len(t.color) == 3
        for c in t.color:
            assert 0 <= c <= 255


# ---------------------------------------------------------------------------
# Tile dataclass
# ---------------------------------------------------------------------------

def test_tile_terrain_property():
    tile = Tile(hex=Hex(0, 0), terrain_id="city")
    assert tile.terrain.id == "city"
    assert tile.terrain.capturable


def test_tile_defaults_neutral():
    tile = Tile(hex=Hex(1, -1), terrain_id="plain")
    assert tile.is_neutral()
    assert tile.owner_faction is None
    assert tile.capture_progress == 0


def test_tile_ownership():
    tile = Tile(hex=Hex(0, 0), terrain_id="city", owner_faction="NATO")
    assert not tile.is_neutral()
    assert tile.owner_faction == "NATO"


def test_tile_capture_reset():
    tile = Tile(hex=Hex(0, 0), terrain_id="city", owner_faction="NATO", capture_progress=2)
    tile.reset_capture()
    assert tile.capture_progress == 0
