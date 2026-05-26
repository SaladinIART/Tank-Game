"""
Terrain types and map tiles.

Terrain definitions live in data/terrain.json and are loaded once into a global
registry via load_terrain(). Tile is a mutable per-hex container (terrain + owner
+ capture progress); TerrainType is immutable metadata.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.engine.hex import Hex

MOVE_CATEGORIES: tuple[str, ...] = ("foot", "wheeled", "tracked", "towed", "air")
CAPTURE_TURNS = 3  # turns an engineer must occupy a tile to flip ownership

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


@dataclass(frozen=True)
class TerrainType:
    id: str
    name: str
    move_cost: dict[str, Optional[int]]  # None = impassable for that category
    defense_bonus: int
    vision_modifier: int       # added to a unit's base vision radius
    blocks_los: bool           # opaque to line-of-sight (mountains)
    capturable: bool           # engineer can flip ownership
    income_credits: int        # credits per turn when owned
    income_oil: int            # oil per turn when owned
    color: tuple[int, int, int]  # (R, G, B) for programmer-art rendering
    is_hq: bool = False        # losing own HQ = game-over in some victory modes

    def passable(self, category: str) -> bool:
        return self.move_cost.get(category) is not None

    def get_move_cost(self, category: str) -> Optional[int]:
        return self.move_cost.get(category)


@dataclass
class Tile:
    hex: Hex
    terrain_id: str
    owner_faction: Optional[str] = None    # None = neutral
    capture_progress: int = 0              # turns this tile has been occupied by capturing_faction
    capturing_faction: Optional[str] = None  # which faction is currently capturing

    @property
    def terrain(self) -> TerrainType:
        return get(self.terrain_id)

    def is_neutral(self) -> bool:
        return self.owner_faction is None

    def reset_capture(self) -> None:
        self.capture_progress = 0
        self.capturing_faction = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[str, TerrainType] = {}


def load_terrain(path: Optional[Path] = None) -> dict[str, TerrainType]:
    """Load terrain definitions from JSON, populate the global registry, return it."""
    if path is None:
        path = _DATA_DIR / "terrain.json"
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    _registry.clear()
    for entry in raw["terrain_types"]:
        # JSON null → Python None for impassable move costs.
        move_cost: dict[str, Optional[int]] = {
            k: (None if v is None else int(v))
            for k, v in entry["move_cost"].items()
        }
        color = tuple(entry["color"])
        tt = TerrainType(
            id=entry["id"],
            name=entry["name"],
            move_cost=move_cost,
            defense_bonus=int(entry["defense_bonus"]),
            vision_modifier=int(entry["vision_modifier"]),
            blocks_los=bool(entry["blocks_los"]),
            capturable=bool(entry["capturable"]),
            income_credits=int(entry["income_credits"]),
            income_oil=int(entry["income_oil"]),
            color=(int(color[0]), int(color[1]), int(color[2])),
            is_hq=bool(entry.get("is_hq", False)),
        )
        _registry[tt.id] = tt
    return _registry


def get(terrain_id: str) -> TerrainType:
    if not _registry:
        load_terrain()
    return _registry[terrain_id]


def all_terrain() -> dict[str, TerrainType]:
    if not _registry:
        load_terrain()
    return dict(_registry)
