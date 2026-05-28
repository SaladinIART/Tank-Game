"""
Per-unit veterancy: XP -> level -> rank -> stat bonuses.

Inspired by 4X tabletop conversions (Warhammer 40k Gladius style).  Each
unit tracks ``xp`` and ``level`` (capped at ``MAX_LEVEL``).  Levels are
grouped into five **ranks** that grant flat stat bonuses; rank shows up as
pip badges on the unit sprite.

Public API
----------
- ``MAX_LEVEL``                         -- hard cap (25)
- ``XP_PER_LEVEL``                      -- linear curve
- ``level_for_xp(xp)``                  -- pure level lookup
- ``rank_of(level)``                    -- 0..5
- ``bonuses(level)``                    -- atk / def / hp / vision flat adds
- ``award_xp(unit, amount)``            -- in-place; recomputes level + max HP
- ``XP_FOR_DAMAGE / XP_FOR_KILL / ...`` -- per-event grants
"""
from __future__ import annotations

from dataclasses import dataclass

from src.engine.unit import Unit

# ---------------------------------------------------------------------------
# Curve constants
# ---------------------------------------------------------------------------

MAX_LEVEL = 25
XP_PER_LEVEL = 5                     # level N reached at xp = (N-1) * XP_PER_LEVEL
XP_AT_CAP = (MAX_LEVEL - 1) * XP_PER_LEVEL   # 120

# Per-event awards
XP_FOR_DAMAGE = 1                    # per HP dealt to an enemy
XP_FOR_KILL = 10                     # bonus when the hit reduces target to 0
XP_FOR_SURVIVING_COUNTER = 2         # awarded if a counter hits us but we live
XP_FOR_CAPTURE = 8                   # engineer flips a tile


# ---------------------------------------------------------------------------
# Rank table -- (atk, def, max_hp, vision) flat bonuses applied to UnitType
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RankBonus:
    atk: int = 0
    def_: int = 0
    hp: int = 0
    vision: int = 0
    name: str = "Rookie"


RANKS: tuple[RankBonus, ...] = (
    RankBonus(atk=0, def_=0, hp=0, vision=0, name="Rookie"),     # rank 0: lv 1-4
    RankBonus(atk=1, def_=0, hp=0, vision=0, name="Veteran"),    # rank 1: lv 5-9
    RankBonus(atk=1, def_=1, hp=0, vision=0, name="Elite"),      # rank 2: lv 10-14
    RankBonus(atk=2, def_=1, hp=2, vision=0, name="Heroic"),     # rank 3: lv 15-19
    RankBonus(atk=2, def_=2, hp=3, vision=1, name="Legendary"),  # rank 4: lv 20-24
    RankBonus(atk=3, def_=2, hp=5, vision=1, name="Mythic"),     # rank 5: lv 25 (cap)
)


# ---------------------------------------------------------------------------
# Level / rank lookup
# ---------------------------------------------------------------------------

def level_for_xp(xp: int) -> int:
    """Convert cumulative XP to a level in [1, MAX_LEVEL]."""
    if xp <= 0:
        return 1
    lvl = 1 + xp // XP_PER_LEVEL
    return min(MAX_LEVEL, max(1, lvl))


def xp_for_level(level: int) -> int:
    """Cumulative XP needed to *reach* that level (inverse of level_for_xp)."""
    return max(0, (level - 1) * XP_PER_LEVEL)


def rank_of(level: int) -> int:
    """0 (rookie) .. 5 (mythic).  Rank N spans levels [5N .. 5N+4].

    Level 1..4 = rookie (rank 0)
    Level 5..9 = veteran (rank 1)
    Level 10..14 = elite (rank 2)
    Level 15..19 = heroic (rank 3)
    Level 20..24 = legendary (rank 4)
    Level 25     = mythic (rank 5, cap)"""
    if level >= MAX_LEVEL:
        return len(RANKS) - 1
    return min(len(RANKS) - 1, max(0, level // 5))


def bonuses(level: int) -> RankBonus:
    return RANKS[rank_of(level)]


def rank_name(level: int) -> str:
    return RANKS[rank_of(level)].name


def max_hp_for(unit: Unit) -> int:
    """Veterancy-adjusted maximum HP for *unit*."""
    return unit.unit_type.hp + bonuses(unit.level).hp


# ---------------------------------------------------------------------------
# XP awarding
# ---------------------------------------------------------------------------

def award_xp(unit: Unit, amount: int) -> int:
    """Add *amount* to ``unit.xp``, recompute level, top up HP if max grew.

    Returns the unit's new level (so callers can detect level-ups by comparing
    against the pre-call level if they want to fire UI flashes).
    """
    if amount <= 0 or unit.level >= MAX_LEVEL:
        return unit.level

    pre_level = unit.level
    unit.xp = min(XP_AT_CAP, unit.xp + amount)
    new_level = level_for_xp(unit.xp)

    if new_level > pre_level:
        pre_max  = unit.unit_type.hp + bonuses(pre_level).hp
        post_max = unit.unit_type.hp + bonuses(new_level).hp
        # On rank-up, top off HP by the delta in max HP -- so a Heroic-rank
        # unit gets the +2 HP and immediately benefits from it.
        if post_max > pre_max:
            unit.hp = min(post_max, unit.hp + (post_max - pre_max))
        unit.level = new_level

    return unit.level
