"""
GameState: the central data model.

Holds factions, all tiles, all live units, and the turn cursor. Mutated by
movement / combat / capture / build (later CPs) and read by AI / render / save.

Pickle-serialisable end-to-end: no Pygame surfaces, no open file handles, no
unpicklable objects. This is the contract that lets CP-15 save/load work.

Turn flow
---------
The factions list is the turn order. `active_faction_idx` is whose turn it is.
`end_turn()` advances the cursor and, when it wraps back to 0, increments
`turn_number`. Each time a new faction's turn begins, _on_turn_start runs:
  1. income  — credits + oil from owned tiles
  2. upkeep  — oil deducted per living unit's upkeep_oil
  3. reset   — that faction's units' has_moved / has_attacked cleared
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

from src.engine.hex import Hex
from src.engine.tile import Tile
from src.engine.unit import Unit


@dataclass
class Faction:
    id: str
    name: str
    color: tuple[int, int, int]
    credits: int = 0
    oil: int = 0
    tier: int = 1          # current tech tier: 1..3
    defeated: bool = False
    is_ai: bool = True

    def can_afford(self, credits: int, oil: int) -> bool:
        return self.credits >= credits and self.oil >= oil

    def pay(self, credits: int, oil: int) -> None:
        if not self.can_afford(credits, oil):
            raise ValueError(
                f"{self.id} cannot pay {credits}cr + {oil}oil "
                f"(has {self.credits}cr, {self.oil}oil)"
            )
        self.credits -= credits
        self.oil -= oil


@dataclass
class GameState:
    factions: list[Faction]
    tiles: dict[Hex, Tile]
    units: dict[int, Unit] = field(default_factory=dict)   # keyed by uid
    active_faction_idx: int = 0
    turn_number: int = 1
    # Fog of war:
    #   explored[fid]       — every hex this faction has ever seen (persistent).
    #   _visible_cache[fid] — current-frame visible set, recomputed lazily.
    explored: dict[str, set[Hex]] = field(default_factory=dict)
    _visible_cache: dict[str, set[Hex]] = field(
        default_factory=dict, repr=False, compare=False
    )

    # ------------------------------------------------------------------
    # Active-faction queries
    # ------------------------------------------------------------------

    @property
    def active_faction(self) -> Faction:
        return self.factions[self.active_faction_idx]

    def faction_by_id(self, fid: str) -> Faction:
        for f in self.factions:
            if f.id == fid:
                return f
        raise KeyError(f"No faction with id={fid}")

    # ------------------------------------------------------------------
    # Unit queries
    # ------------------------------------------------------------------

    def units_of(self, faction_id: str) -> list[Unit]:
        return [u for u in self.units.values() if u.faction == faction_id and u.is_alive()]

    def enemy_units_of(self, faction_id: str) -> list[Unit]:
        return [u for u in self.units.values() if u.faction != faction_id and u.is_alive()]

    def unit_at(self, h: Hex) -> Optional[Unit]:
        for u in self.units.values():
            if u.is_alive() and u.hex == h:
                return u
        return None

    # ------------------------------------------------------------------
    # Tile queries
    # ------------------------------------------------------------------

    def tiles_owned_by(self, faction_id: str) -> list[Tile]:
        return [t for t in self.tiles.values() if t.owner_faction == faction_id]

    def hq_of(self, faction_id: str) -> Optional[Tile]:
        for t in self.tiles.values():
            if t.owner_faction == faction_id and t.terrain.is_hq:
                return t
        return None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_unit(self, unit: Unit) -> None:
        if unit.uid in self.units:
            raise ValueError(f"Unit uid {unit.uid} already registered")
        self.units[unit.uid] = unit
        self.invalidate_fog()

    def remove_unit(self, uid: int) -> None:
        if uid in self.units:
            self.units.pop(uid, None)
            self.invalidate_fog()

    def move_unit(self, uid: int, dest: Hex) -> None:
        u = self.units[uid]
        if self.unit_at(dest) is not None:
            raise ValueError(f"Destination {dest} occupied")
        u.hex = dest
        self.invalidate_fog()

    def set_tile_owner(self, h: Hex, faction_id: Optional[str]) -> None:
        self.tiles[h].owner_faction = faction_id
        self.tiles[h].reset_capture()

    # ------------------------------------------------------------------
    # Fog of war
    # ------------------------------------------------------------------

    def visible_to(self, faction_id: str) -> set[Hex]:
        """
        Currently-visible hex set for *faction_id*. Cached until invalidate_fog().
        Calling this also merges the result into explored[faction_id].
        """
        cached = self._visible_cache.get(faction_id)
        if cached is not None:
            return cached
        # Lazy import to break the state ↔ fog circular dependency.
        from src.engine.fog import compute_visible
        vis = compute_visible(self, faction_id)
        self._visible_cache[faction_id] = vis
        self.explored.setdefault(faction_id, set()).update(vis)
        return vis

    def invalidate_fog(self, faction_id: Optional[str] = None) -> None:
        """Drop cached visibility for one faction, or all if None."""
        if faction_id is None:
            self._visible_cache.clear()
        else:
            self._visible_cache.pop(faction_id, None)

    # ------------------------------------------------------------------
    # Turn flow
    # ------------------------------------------------------------------

    def end_turn(self) -> None:
        """Advance to the next non-defeated faction and run its turn-start hooks."""
        n = len(self.factions)
        for _ in range(n):
            self.active_faction_idx = (self.active_faction_idx + 1) % n
            if self.active_faction_idx == 0:
                self.turn_number += 1
            if not self.active_faction.defeated:
                break
        self._on_turn_start(self.active_faction)
        # Force fog recomputation at turn boundary for every faction.
        self.invalidate_fog()

    def _on_turn_start(self, faction: Faction) -> None:
        self._process_captures(faction)   # before income so flipped tiles contribute
        self._apply_income(faction)
        self._apply_upkeep(faction)
        self._reset_units(faction)

    def _process_captures(self, faction: Faction) -> None:
        """Advance capture progress for can_capture units at turn start."""
        from src.engine.capture import process_captures
        process_captures(self, faction)

    def _apply_income(self, faction: Faction) -> None:
        for tile in self.tiles_owned_by(faction.id):
            terrain = tile.terrain
            faction.credits += terrain.income_credits
            faction.oil += terrain.income_oil

    def _apply_upkeep(self, faction: Faction) -> None:
        total = sum(u.unit_type.upkeep_oil for u in self.units_of(faction.id))
        faction.oil = max(0, faction.oil - total)

    def _reset_units(self, faction: Faction) -> None:
        for u in self.units_of(faction.id):
            u.reset_turn()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def iter_units_at(self, hexes: Iterable[Hex]) -> Iterator[Unit]:
        hexset = set(hexes)
        for u in self.units.values():
            if u.is_alive() and u.hex in hexset:
                yield u
