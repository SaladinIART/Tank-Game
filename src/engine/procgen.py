"""
Procedural skirmish map generator.

``generate_map(width, height, seed)`` returns a ready-to-use tile dict plus HQ
positions for up to 3 factions.  The output is deterministic for a fixed seed,
ensuring the "Random" map can be stored in a save file and replayed identically.

Algorithm
---------
1. Fill with plains.
2. Mountain clusters — 3 random clusters, each 2-5 tiles, avoiding edges.
3. Forest patches — 4 random patches, each 2-6 tiles, on plain only.
4. River — a vertical column walk across the map with one bridge in the middle.
5. Neutral terrain — 3 cities + 2 oil wells on plain tiles.
6. Clear 2-tile safety radius around each HQ position so units can spawn cleanly.
"""
from __future__ import annotations

import random
from typing import Optional

from src.engine.hex import Hex
from src.engine.tile import Tile


def generate_map(
    width: int = 20,
    height: int = 14,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a random skirmish map.

    Returns a dict with keys:
      ``"tiles"``         — ``dict[Hex, Tile]`` covering the full grid.
      ``"hq_positions"``  — ``list[(q, r)]`` for up to 3 faction slots.
      ``"width"``         — map width.
      ``"height"``        — map height.
      ``"seed"``          — the seed used (for storage / replay).
    """
    if seed is None:
        seed = random.randint(0, 99_999)
    rng = random.Random(seed)

    # ── 1. Base fill ──────────────────────────────────────────────────────
    tiles: dict[Hex, Tile] = {
        Hex(q, r): Tile(Hex(q, r), "plain")
        for q in range(width)
        for r in range(height)
    }

    # ── 2. Mountain clusters ──────────────────────────────────────────────
    for _ in range(3):
        cx = rng.randint(3, width - 4)
        cy = rng.randint(2, height - 3)
        for _ in range(rng.randint(2, 5)):
            mq = cx + rng.randint(-2, 2)
            mr = cy + rng.randint(-2, 2)
            if 2 <= mq < width - 2 and 1 <= mr < height - 1:
                tiles[Hex(mq, mr)] = Tile(Hex(mq, mr), "mountain")

    # ── 3. Forest patches ─────────────────────────────────────────────────
    for _ in range(4):
        cx = rng.randint(2, width - 3)
        cy = rng.randint(2, height - 3)
        for _ in range(rng.randint(2, 6)):
            fq = cx + rng.randint(-2, 2)
            fr = cy + rng.randint(-2, 2)
            h = Hex(fq, fr)
            if 1 <= fq < width - 1 and 1 <= fr < height - 1:
                if tiles.get(h) and tiles[h].terrain_id == "plain":
                    tiles[h] = Tile(h, "forest")

    # ── 4. River (column walk + one bridge) ───────────────────────────────
    rq = rng.randint(width // 3, 2 * width // 3)
    bridge_r = rng.randint(height // 3, 2 * height // 3)
    for r in range(height):
        rq = max(1, min(width - 2, rq + rng.randint(-1, 1)))
        h = Hex(rq, r)
        if tiles[h].terrain_id in ("plain", "road"):
            terrain = "bridge" if r == bridge_r else "river"
            tiles[h] = Tile(h, terrain)

    # ── 5. Neutral cities + oil wells ────────────────────────────────────
    candidates = [
        (q, r)
        for q in range(2, width - 2)
        for r in range(2, height - 2)
        if tiles[Hex(q, r)].terrain_id == "plain"
    ]
    rng.shuffle(candidates)
    objective_terrains = ["city", "city", "city", "oil_well", "oil_well"]
    placed = 0
    for q, r in candidates:
        if placed >= len(objective_terrains):
            break
        h = Hex(q, r)
        # Spread objectives out — skip if neighbour is already an objective
        near_obj = any(
            tiles.get(Hex(q + dq, r + dr), Tile(Hex(0, 0), "plain")).terrain_id
            in ("city", "oil_well")
            for dq, dr in [(0, 1), (1, 0), (0, -1), (-1, 0)]
        )
        if not near_obj:
            tiles[h] = Tile(h, objective_terrains[placed])
            placed += 1

    # ── 6. HQ positions + safety clear ───────────────────────────────────
    hq_positions: list[tuple[int, int]] = [
        (1, 1),
        (width - 2, height - 2),
        (1, height - 2),
    ]
    for hq_q, hq_r in hq_positions:
        for dq in range(-2, 3):
            for dr in range(-2, 3):
                nh = Hex(hq_q + dq, hq_r + dr)
                if nh in tiles and tiles[nh].terrain_id in ("mountain", "river"):
                    tiles[nh] = Tile(nh, "plain")
        # Ensure HQ hex itself is plain (builder will overwrite with "hq")
        tiles[Hex(hq_q, hq_r)] = Tile(Hex(hq_q, hq_r), "plain")

    return {
        "tiles":         tiles,
        "hq_positions":  hq_positions,
        "width":         width,
        "height":        height,
        "seed":          seed,
    }
