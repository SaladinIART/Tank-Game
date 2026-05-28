"""
Player-facing action helpers for the stance system + retreat.

Used by main.py to apply unit-level orders that the player issues from
the selected-unit panel or via keyboard (D = defend, R = retreat).

The engine core stays UI-free; these helpers are pure mutations over the
GameState.

Public API
----------
- ``set_defend(state, unit)``       -- hunker-down stance (+def, ends action)
- ``clear_stance(state, unit)``     -- back to normal attack stance
- ``retreat(state, unit)``          -- move toward own HQ, consume action
- ``actionable_units(state, fid)``  -- list of own units that can still act
"""
from __future__ import annotations

from typing import Optional

from src.engine.hex import Hex, distance
from src.engine.movement import compute_movement
from src.engine.state import GameState
from src.engine.unit import STANCE_ATTACK, STANCE_DEFEND, Unit


# ---------------------------------------------------------------------------
# Stance
# ---------------------------------------------------------------------------

def set_defend(state: GameState, unit: Unit) -> None:
    """Switch *unit* to defend stance and consume its remaining actions.

    Defend persists through the enemy turn; ``Unit.reset_turn`` clears it
    at the start of this faction's next turn.

    Raises ``ValueError`` if *unit* is dead or belongs to no faction tile.
    """
    if not unit.is_alive():
        raise ValueError("Cannot order a dead unit to defend.")
    unit.stance = STANCE_DEFEND
    unit.has_moved = True
    unit.has_attacked = True


def clear_stance(state: GameState, unit: Unit) -> None:
    """Undo defend stance.  Does NOT refund the consumed action -- by design,
    so a player can't toggle defend back and forth to game the system."""
    unit.stance = STANCE_ATTACK


# ---------------------------------------------------------------------------
# Retreat
# ---------------------------------------------------------------------------

def _own_hq_hex(state: GameState, faction_id: str) -> Optional[Hex]:
    hq = state.hq_of(faction_id)
    return hq.hex if hq is not None else None


def retreat_destination(state: GameState, unit: Unit) -> Optional[Hex]:
    """Best reachable hex when fleeing toward own HQ, or None if can't move.

    Pure: does not mutate state.  Pick the reachable hex with the smallest
    distance to friendly HQ, tie-breaking on lowest threat (= shortest hex
    distance from the most threatening visible enemy).  Falls back to the
    unit's current hex if HQ is unreachable.
    """
    if unit.has_moved:
        return None
    hq_hex = _own_hq_hex(state, unit.faction)
    if hq_hex is None:
        return None
    movement = compute_movement(state, unit)
    reachable = [h for h in movement.reachable if state.unit_at(h) is None or h == unit.hex]
    if not reachable:
        return None

    enemies = [u for u in state.units.values() if u.faction != unit.faction]
    def _enemy_threat(h: Hex) -> int:
        # Higher = more dangerous.  Closer enemies count more (1/dist+1).
        if not enemies:
            return 0
        return sum(1.0 / (distance(h, e.hex) + 1) for e in enemies)

    # Prefer least distance to HQ, then least threat.
    def _key(h: Hex) -> tuple[int, float]:
        return (distance(h, hq_hex), _enemy_threat(h))

    return min(reachable, key=_key)


def retreat(state: GameState, unit: Unit) -> Optional[Hex]:
    """Move *unit* toward its faction's HQ; consume action.  Returns dest or None.

    Counter-attacks (if engaged) still happen because counter logic doesn't
    require ``has_moved/has_attacked == False``.
    """
    dest = retreat_destination(state, unit)
    if dest is None or dest == unit.hex:
        unit.has_moved = True
        unit.has_attacked = True
        return None
    state.move_unit(unit.uid, dest)
    unit.has_moved = True
    unit.has_attacked = True
    return dest


# ---------------------------------------------------------------------------
# End-turn reminder
# ---------------------------------------------------------------------------

def actionable_units(state: GameState, faction_id: str) -> list[Unit]:
    """Own units that still have an action this turn."""
    return [u for u in state.units_of(faction_id) if u.can_act()]


# ---------------------------------------------------------------------------
# Active heal -- engineer "medic" ability
# ---------------------------------------------------------------------------

MEDIC_HEAL_AMOUNT = 3


def can_medic(state: GameState, healer: Unit, patient: Unit) -> bool:
    """True iff *healer* (an engineer-class unit) can heal *patient* this turn."""
    if not healer.is_alive() or not patient.is_alive():
        return False
    if healer is patient:
        return False
    if not healer.unit_type.can_capture:   # only engineer-class can medic
        return False
    if healer.has_attacked:                # healing uses the attack slot
        return False
    if patient.faction != healer.faction:
        return False
    if distance(healer.hex, patient.hex) != 1:
        return False
    from src.engine.veterancy import max_hp_for
    return patient.hp < max_hp_for(patient)


def medic_heal(state: GameState, healer: Unit, patient: Unit) -> int:
    """Heal *patient* by ``MEDIC_HEAL_AMOUNT`` (capped); consume healer action.

    Returns the actual amount healed (could be < MEDIC_HEAL_AMOUNT if near
    cap, or 0 if the heal would have been a no-op).  Raises ``ValueError``
    if ``can_medic`` rejects the pairing.
    """
    if not can_medic(state, healer, patient):
        raise ValueError("Illegal medic action.")
    from src.engine.veterancy import max_hp_for
    cap = max_hp_for(patient)
    before = patient.hp
    patient.hp = min(cap, patient.hp + MEDIC_HEAL_AMOUNT)
    healer.has_attacked = True              # uses the attack slot, not the move
    return patient.hp - before


def adjacent_friendly_patients(state: GameState, healer: Unit) -> list[Unit]:
    """Adjacent allies that would benefit from a medic action right now."""
    return [u for u in state.units.values() if can_medic(state, healer, u)]
