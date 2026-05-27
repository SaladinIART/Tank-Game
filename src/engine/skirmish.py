"""
Skirmish mode — map template loader and GameState builder.

Usage
-----
1. Load a canned map template or generate one with ``procgen.generate_map``.
2. Call ``build_skirmish_state(tiles, hq_positions, player_faction, ai_factions,
   victory_types)`` to get a fully configured GameState.
3. Start playing.

Map template JSON format
------------------------
::

    {
      "name":              "Plains",
      "description":       "...",
      "width":             16,
      "height":            12,
      "default_terrain":   "plain",
      "hq_positions":      [[1,1],[14,10],[1,10]],
      "tiles": [
        {"hex": [q, r], "terrain": "forest"},
        {"comment": "..."}        <- skipped
      ]
    }

Victory types
-------------
``"destroy_hq"``
    Win by capturing every enemy HQ.  Always usable.

``"hold_cities"``
    Win by holding 2 neutral cities for 8 consecutive turns.
    Only installed if the map has ≥ 2 neutral cities.

``"capture_oil"``
    Win by owning all oil wells on the map.
    Only installed if the map has ≥ 1 oil well.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.engine.hex import Hex
from src.engine.state import Faction, GameState
from src.engine.tile import Tile
from src.engine.unit import Unit
from src.engine.victory import (
    DestroyHQ,
    HoldTiles,
    OwnAllOfTerrain,
    VictoryConfig,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIRMISH_CREDITS = 600
SKIRMISH_OIL     = 8

_FACTION_COLORS: dict[str, tuple[int, int, int]] = {
    "NATO":     (30, 80, 200),
    "BRICS":    (200, 30, 30),
    "GUERILLA": (130, 140, 70),
}

_FACTION_NAMES: dict[str, str] = {
    "NATO":     "NATO",
    "BRICS":    "BRICS",
    "GUERILLA": "Guerilla",
}

# 3 T1 starter units per faction: infantry + engineer + recon equivalent
_STARTER_UNIT_IDS: dict[str, list[str]] = {
    "NATO":     ["nato_inf_l",         "nato_engineer",      "nato_recon"],
    "BRICS":    ["brics_inf_l",        "brics_engineer",     "brics_recon"],
    "GUERILLA": ["guerilla_irregular", "guerilla_engineer",  "guerilla_scout"],
}

# Axial neighbour offsets (pointy-top hex)
_NEIGHBOURS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


# ---------------------------------------------------------------------------
# Map template loader
# ---------------------------------------------------------------------------

def load_skirmish_map(path: "str | Path") -> tuple[dict[Hex, Tile], list[tuple[int, int]], dict]:
    """
    Load a skirmish map template JSON.

    Returns
    -------
    tiles
        ``dict[Hex, Tile]`` covering the full grid (no HQ tiles — those are
        added by ``build_skirmish_state``).
    hq_positions
        List of ``(q, r)`` tuples for up to 3 faction slots.
    meta
        Dict with ``"name"``, ``"description"``, ``"width"``, ``"height"``.
    """
    from src.engine.tile import load_terrain
    load_terrain()   # idempotent

    p = Path(path)
    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))

    width           = int(data.get("width",  20))
    height          = int(data.get("height", 14))
    default_terrain = data.get("default_terrain", "plain")
    raw_hq          = data.get("hq_positions", [[1, 1], [width - 2, height - 2], [1, height - 2]])
    hq_positions    = [tuple(pos) for pos in raw_hq]

    # Fill default
    tiles: dict[Hex, Tile] = {
        Hex(q, r): Tile(Hex(q, r), default_terrain)
        for q in range(width)
        for r in range(height)
    }

    # Override with listed tiles
    for td in data.get("tiles", []):
        if "hex" not in td:
            continue
        q, r = td["hex"]
        h = Hex(q, r)
        tiles[h] = Tile(hex=h, terrain_id=td["terrain"], owner_faction=td.get("owner"))

    meta = {
        "name":        data.get("name", "Custom"),
        "description": data.get("description", ""),
        "width":       width,
        "height":      height,
    }
    return tiles, hq_positions, meta


# ---------------------------------------------------------------------------
# GameState builder
# ---------------------------------------------------------------------------

def build_skirmish_state(
    tiles: dict[Hex, Tile],
    hq_positions: list[tuple[int, int]],
    player_faction: str,
    ai_factions: list[str],
    victory_types: list[str],
) -> GameState:
    """
    Construct a fully-wired GameState ready to play.

    Parameters
    ----------
    tiles
        Map tile dict (without HQ tiles — placed here).
    hq_positions
        HQ position per faction slot: index 0 = player, 1+ = AI.
        If fewer positions than factions, remaining factions are skipped.
    player_faction
        Faction ID for the human player.
    ai_factions
        Faction IDs for AI opponents (1 or 2 factions).
    victory_types
        Subset of ``{"destroy_hq", "hold_cities", "capture_oil"}``.
        Only applicable conditions are installed.
    """
    all_fids = [player_faction] + list(ai_factions)

    # ── Factions ─────────────────────────────────────────────────────────
    factions = [
        Faction(
            id=fid,
            name=_FACTION_NAMES.get(fid, fid),
            color=_FACTION_COLORS.get(fid, (128, 128, 128)),
            credits=SKIRMISH_CREDITS,
            oil=SKIRMISH_OIL,
            tier=1,
            is_ai=(i > 0),
        )
        for i, fid in enumerate(all_fids)
    ]

    # ── Working tile copy + place HQ tiles ───────────────────────────────
    working: dict[Hex, Tile] = dict(tiles)
    for i, fid in enumerate(all_fids):
        if i >= len(hq_positions):
            break
        q, r = hq_positions[i]
        h = Hex(q, r)
        working[h] = Tile(hex=h, terrain_id="hq", owner_faction=fid)
        # Place a faction-owned city adjacent to HQ (if plain)
        city_offset = (1, 0) if q < 5 else (-1, 0)
        ch = Hex(q + city_offset[0], r + city_offset[1])
        if ch in working and working[ch].terrain_id == "plain":
            working[ch] = Tile(hex=ch, terrain_id="city", owner_faction=fid)

    state = GameState(factions=factions, tiles=working)

    # ── Starting units ────────────────────────────────────────────────────
    for i, fid in enumerate(all_fids):
        if i >= len(hq_positions):
            break
        hq_hex  = Hex(*hq_positions[i])
        type_ids = _STARTER_UNIT_IDS.get(fid, [])
        placed  = 0
        for dq, dr in _NEIGHBOURS:
            if placed >= len(type_ids):
                break
            nh = Hex(hq_hex.q + dq, hq_hex.r + dr)
            if nh not in state.tiles:
                continue
            t = state.tiles[nh]
            if t.terrain_id in ("river", "mountain") or state.unit_at(nh) is not None:
                continue
            unit = Unit(type_id=type_ids[placed], faction=fid, hex=nh)
            state.add_unit(unit)
            placed += 1

    # ── Victory configs ───────────────────────────────────────────────────
    # Pre-compute available objectives
    neutral_cities = [
        h for h, t in state.tiles.items()
        if t.terrain_id == "city" and t.owner_faction is None
    ]
    all_oil_wells = [
        h for h, t in state.tiles.items()
        if t.terrain_id == "oil_well"
    ]

    for fid in all_fids:
        others = [f for f in all_fids if f != fid]
        win_conds: list = []

        if "destroy_hq" in victory_types:
            for other in others:
                win_conds.append(DestroyHQ(target_faction=other))

        if "hold_cities" in victory_types and len(neutral_cities) >= 2:
            win_conds.append(
                HoldTiles(target_hexes=list(neutral_cities[:2]), turns_required=8)
            )

        if "capture_oil" in victory_types and all_oil_wells:
            win_conds.append(OwnAllOfTerrain(terrain_id="oil_well"))

        state.victory_configs[fid] = VictoryConfig(
            win_conditions=win_conds,
            win_mode="any",
            lose_conditions=[DestroyHQ(target_faction=fid)],
            lose_mode="any",
        )

    return state
