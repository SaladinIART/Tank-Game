"""
Unit movement: Dijkstra reachability + shortest-path reconstruction.

Rules:
  - Cost per step = terrain.move_cost[unit.move_category]; None = impassable.
  - Flying units pay 1 per hex regardless of terrain.
  - Cannot pass through or stop on enemy-occupied hexes.
  - Can pass through friendly hexes but cannot stop on them.
  - Result excludes the unit's own hex (already there).
  - **Zone of Control (engagement)**: if the unit starts adjacent to any
    enemy, its movement budget is capped at ``ENGAGED_MOVE_LIMIT`` (1 hex).
    Flying units are exempt -- they always have full movement.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Optional

from src.engine.hex import Hex, neighbours
from src.engine.state import GameState
from src.engine.unit import Unit


# When adjacent to any enemy, movement is restricted to this many hexes.
ENGAGED_MOVE_LIMIT = 1


@dataclass
class Movement:
    """Cached result of compute_movement() for one unit."""
    reachable: dict[Hex, int]                          # dest → MP cost; stoppable only
    prev: dict[Hex, Optional[Hex]] = field(repr=False) # predecessor map for path reconstruction
    engaged: bool = False                              # True if movement was ZoC-capped

    def path_to(self, destination: Hex) -> list[Hex]:
        """
        Return path from start to destination (both inclusive).
        Returns [] if destination is not in the Dijkstra tree (unreachable).
        """
        if destination not in self.prev:
            return []
        path: list[Hex] = []
        h: Optional[Hex] = destination
        while h is not None:
            path.append(h)
            h = self.prev[h]
        path.reverse()
        return path


def is_engaged(state: GameState, unit: Unit) -> bool:
    """True if any enemy unit sits on a hex adjacent to *unit*.

    Flying units don't count as engaged (they can disengage in three dimensions
    -- justifies their faster manoeuvre)."""
    if unit.unit_type.flying:
        return False
    for nb in neighbours(unit.hex):
        other = state.unit_at(nb)
        if other is not None and other.faction != unit.faction:
            return True
    return False


def compute_movement(state: GameState, unit: Unit) -> Movement:
    """
    Compute all stoppable destinations and the predecessor map for *unit*.

    The returned Movement is valid as long as the map tiles and unit positions
    do not change.  Re-compute after any move or turn boundary.
    """
    cat = unit.unit_type.move_category
    mp = unit.unit_type.move
    flying = unit.unit_type.flying

    # Zone of Control: engaged units can only step 1 hex this turn.
    engaged = is_engaged(state, unit)
    if engaged:
        mp = min(mp, ENGAGED_MOVE_LIMIT)

    INF = 10 ** 9
    dist: dict[Hex, int] = {unit.hex: 0}
    prev: dict[Hex, Optional[Hex]] = {unit.hex: None}
    # (cost, q, r) tuples avoid requiring Hex.__lt__ for heap ordering.
    heap: list[tuple[int, int, int]] = [(0, unit.hex.q, unit.hex.r)]

    while heap:
        cost, q, r = heapq.heappop(heap)
        h = Hex(q, r)
        if cost > dist.get(h, INF):
            continue  # stale entry

        for nb in neighbours(h):
            if nb not in state.tiles:
                continue

            terrain = state.tiles[nb].terrain
            step_cost: Optional[int] = 1 if flying else terrain.get_move_cost(cat)
            if step_cost is None:
                continue  # impassable terrain for this move category

            new_cost = cost + step_cost
            if new_cost > mp:
                continue  # movement budget exceeded

            # Cannot pass through enemy units at all.
            occupant = state.unit_at(nb)
            if occupant is not None and occupant.faction != unit.faction:
                continue

            if new_cost < dist.get(nb, INF):
                dist[nb] = new_cost
                prev[nb] = h
                heapq.heappush(heap, (new_cost, nb.q, nb.r))

    # Stoppable = reached AND not occupied by any unit (incl. friendly)
    reachable: dict[Hex, int] = {
        h: c
        for h, c in dist.items()
        if h != unit.hex and state.unit_at(h) is None
    }

    return Movement(reachable=reachable, prev=prev, engaged=engaged)
