"""
Capture mechanic — engineer-capable units occupying capturable tiles advance a
per-tile progress counter each turn-start.

Rules
-----
- Only units with ``unit_type.can_capture == True`` (engineer, mech infantry)
  contribute to capture progress.
- Progress is faction-specific: if a different faction's unit was previously
  advancing the counter, progress resets to 0 and the new faction starts from 1.
- When no eligible unit from the capturing faction is present at turn-start
  (unit moved away or was killed), progress resets.
- At ``CAPTURE_TURNS`` the tile ownership flips to the capturing faction; the
  new tile immediately contributes income during the same turn-start.

Turn flow hook
--------------
``process_captures(state, faction)`` is called by ``GameState._process_captures``
at the *start* of each faction's turn — before ``_apply_income`` — so a freshly
captured tile contributes income in that same turn.

TODO CP-18: Guerilla captured oil_well → 2-turn recapture lock (stealth update).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.engine.tile import CAPTURE_TURNS

if TYPE_CHECKING:
    from src.engine.hex import Hex
    from src.engine.state import Faction, GameState


def process_captures(state: "GameState", faction: "Faction") -> list["Hex"]:
    """
    Advance capture progress for *faction* at turn start.

    Returns a list of hexes where ownership flipped this call (useful for
    logging and future UI animation hooks).
    """
    from src.engine.hex import Hex  # concrete import for the return-type list  # noqa: F401

    flipped: list[Hex] = []

    # Hexes where this faction has at least one can_capture unit right now.
    capturing_hexes: set[Hex] = {
        u.hex
        for u in state.units_of(faction.id)
        if u.unit_type.can_capture
    }

    # ── Pass 1: reset stale progress ─────────────────────────────────────────
    # Capturable tiles that this faction was previously advancing but no longer
    # has an eligible unit on (unit moved away or was killed last turn).
    for tile in state.tiles.values():
        if (
            tile.terrain.capturable
            and tile.capturing_faction == faction.id
            and tile.hex not in capturing_hexes
        ):
            tile.reset_capture()  # clears progress and capturing_faction

    # ── Pass 2: advance capture ───────────────────────────────────────────────
    for h in capturing_hexes:
        tile = state.tiles.get(h)
        if tile is None or not tile.terrain.capturable:
            continue
        if tile.owner_faction == faction.id:
            # Already ours — clear any stale progress silently.
            if tile.capture_progress > 0:
                tile.reset_capture()
            continue

        # Neutral or enemy tile — advance capture.
        if tile.capturing_faction != faction.id:
            # Interrupting another faction (or starting fresh) → reset counter.
            tile.capture_progress = 0
            tile.capturing_faction = faction.id

        tile.capture_progress += 1

        if tile.capture_progress >= CAPTURE_TURNS:
            # Ownership flip — set_tile_owner also calls reset_capture().
            state.set_tile_owner(h, faction.id)
            flipped.append(h)
            # XP reward for the engineer(s) sitting on the flipped tile.
            from src.engine.veterancy import XP_FOR_CAPTURE, award_xp
            for u in state.units_of(faction.id):
                if u.unit_type.can_capture and u.hex == h:
                    award_xp(u, XP_FOR_CAPTURE)

    return flipped
