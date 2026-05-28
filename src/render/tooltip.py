"""
Hover tooltip bubbles for units and terrain.

Renders a compact stat card near the cursor describing what the mouse is over.
Tooltip content is data-driven from the damage matrix + terrain/unit JSONs
so balance changes propagate automatically.

Public API
----------
- ``unit_tooltip_lines(unit)`` -> list[(text, color)]
- ``terrain_tooltip_lines(tile)`` -> list[(text, color)]
- ``draw_tooltip(surface, lines, anchor, font, screen_size)``  -- positions
   the bubble near the cursor, flipping at screen edges so it's never clipped.
"""
from __future__ import annotations

from typing import Optional

import pygame

from src.engine.combat import base_damage, load_damage_matrix
from src.engine.tile import MOVE_CATEGORIES, Tile, all_terrain
from src.engine.unit import Unit, VALID_UNIT_CLASSES
from src.engine.veterancy import (
    MAX_LEVEL,
    bonuses as rank_bonuses,
    max_hp_for,
    rank_name,
    rank_of,
    xp_for_level,
)

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

C_TITLE     = (255, 235, 130)
C_SUBTITLE  = (210, 210, 230)
C_LABEL     = (170, 180, 200)
C_VALUE     = (230, 230, 230)
C_GOOD      = (140, 230, 140)
C_BAD       = (230, 140, 140)
C_WARN      = (240, 200, 110)
C_HINT      = (160, 200, 240)
C_FACTION   = {
    "NATO":     (140, 180, 230),
    "BRICS":    (230, 150, 140),
    "GUERILLA": (180, 200, 140),
}

BG_COLOR   = (16, 22, 34, 235)
BORDER     = (90, 110, 150)
PADDING    = 10
LINE_GAP   = 2

# ---------------------------------------------------------------------------
# Role hints by unit class -- short tactical descriptions
# ---------------------------------------------------------------------------

ROLE_HINTS: dict[str, str] = {
    "infantry":   "Cheap, occupies tiles. Strong in forests/cities.",
    "engineer":   "Captures cities/oil wells. Send toward enemy HQ.",
    "recon":      "Fast, big vision. Scouts ahead; weak in melee.",
    "vehicle":    "Tank line: strong vs vehicles + recon.",
    "artillery":  "Indirect fire. Cannot counterattack (out of range).",
    "aa":         "Anti-air specialist. Wrecks jets/helis, soft vs ground.",
    "sniper":     "High damage vs infantry. Glass cannon.",
    "jet":        "Air superiority. Watch oil; AA shreds it.",
    "helicopter": "Flying, ignores terrain. Strong all-rounder.",
    "bomber":     "Crushes ground; defenceless vs jets/AA.",
}

# ---------------------------------------------------------------------------
# Best/worst targeting -- computed from damage matrix at first use
# ---------------------------------------------------------------------------

_BEST_VS:  dict[str, list[str]] = {}
_WORST_VS: dict[str, list[str]] = {}


def _ensure_matchups() -> None:
    if _BEST_VS:
        return
    load_damage_matrix()
    for atk in sorted(VALID_UNIT_CLASSES):
        scores = []
        for d in sorted(VALID_UNIT_CLASSES):
            scores.append((d, base_damage(atk, d)))
        # Sort by damage desc
        scores_sorted = sorted(scores, key=lambda x: -x[1])
        # Best: top defenders by base damage (only those with damage >= 6)
        best = [d for d, dmg in scores_sorted if dmg >= 6][:3]
        if not best:
            best = [scores_sorted[0][0]] if scores_sorted else []
        # Worst: bottom (damage 0 = cannot attack, then lowest non-zero)
        zeros = [d for d, dmg in scores if dmg == 0]
        if zeros:
            worst = zeros[:3]
        else:
            worst = [d for d, dmg in sorted(scores, key=lambda x: x[1])[:3]]
        _BEST_VS[atk]  = best
        _WORST_VS[atk] = worst


# ---------------------------------------------------------------------------
# Unit tooltip
# ---------------------------------------------------------------------------

def unit_tooltip_lines(unit: Unit) -> list[tuple[str, tuple[int, int, int]]]:
    """Stat card for a unit instance: name, faction, HP, combat profile, hints."""
    _ensure_matchups()
    ut = unit.unit_type
    lines: list[tuple[str, tuple[int, int, int]]] = []

    # Title + faction + veterancy stars
    fac_col = C_FACTION.get(ut.faction, C_VALUE)
    tier_lbl = f"T{ut.tier}"
    stars = "*" * rank_of(unit.level)         # 0..5 pips
    title = f"{ut.name}  [{tier_lbl}]"
    if stars:
        title += f"  {stars}"
    lines.append((title, C_TITLE))
    lines.append((f"{ut.faction} {ut.unit_class}", fac_col))

    # Veterancy
    rb = rank_bonuses(unit.level)
    if unit.level < MAX_LEVEL:
        next_xp = xp_for_level(unit.level + 1)
        vet_text = f"Lv {unit.level} ({rank_name(unit.level)})  XP {unit.xp}/{next_xp}"
    else:
        vet_text = f"Lv {MAX_LEVEL} ({rank_name(unit.level)})  XP MAX"
    bonus_bits = []
    if rb.atk:    bonus_bits.append(f"+{rb.atk}atk")
    if rb.def_:   bonus_bits.append(f"+{rb.def_}def")
    if rb.hp:     bonus_bits.append(f"+{rb.hp}hp")
    if rb.vision: bonus_bits.append(f"+{rb.vision}vis")
    if bonus_bits:
        vet_text += "  (" + " ".join(bonus_bits) + ")"
    vet_col = C_GOOD if rank_of(unit.level) >= 3 else (
        C_WARN if rank_of(unit.level) >= 1 else C_LABEL
    )
    lines.append((vet_text, vet_col))

    # HP (use veterancy-adjusted max)
    cap_hp = max_hp_for(unit)
    hp_color = C_GOOD if unit.hp >= cap_hp * 0.75 else (
        C_WARN if unit.hp >= cap_hp * 0.4 else C_BAD
    )
    lines.append((f"HP: {unit.hp}/{cap_hp}", hp_color))

    # Combat stats (show base + rank bonus inline if any)
    rng = (f"{ut.range_min}-{ut.range_max}"
           if ut.range_max != ut.range_min else str(ut.range_max))
    indirect = "  (indirect)" if ut.is_indirect() else ""
    atk_eff = ut.atk + rb.atk
    def_eff = ut.def_ + rb.def_
    atk_str = f"{atk_eff}" + (f" ({ut.atk}+{rb.atk})" if rb.atk else "")
    def_str = f"{def_eff}" + (f" ({ut.def_}+{rb.def_})" if rb.def_ else "")
    lines.append((f"ATK {atk_str}  DEF {def_str}  RNG {rng}{indirect}", C_VALUE))

    # Movement
    flying = "  flying" if ut.flying else ""
    amph   = "  amphib" if ut.amphibious else ""
    stealth = "  stealth" if ut.stealth else ""
    cap     = "  capture" if ut.can_capture else ""
    kami    = "  KAMIKAZE" if ut.self_destruct else ""
    tags = flying + amph + stealth + cap + kami
    lines.append((f"MOV {ut.move}  VIS {ut.vision}  ({ut.move_category}){tags}",
                  C_VALUE))

    # Cost
    if ut.cost_credits or ut.cost_oil:
        oil_part = f"  +{ut.cost_oil} oil" if ut.cost_oil else ""
        upkeep   = f"  upkeep {ut.upkeep_oil}/turn" if ut.upkeep_oil else ""
        lines.append((f"Cost: {ut.cost_credits} cr{oil_part}{upkeep}", C_LABEL))

    # Stance
    if unit.stance == "defend":
        lines.append(("STANCE: Hunkered (+2 DEF, no attack)", C_GOOD))

    # Status (action flags)
    if not unit.can_act():
        if unit.is_alive() and unit.stance != "defend":
            lines.append(("(exhausted this turn)", C_LABEL))

    # Matchups
    best  = _BEST_VS.get(ut.unit_class,  [])
    worst = _WORST_VS.get(ut.unit_class, [])
    if best:
        lines.append((f"BEST vs:  {', '.join(best)}", C_GOOD))
    if worst:
        lines.append((f"WEAK vs:  {', '.join(worst)}", C_BAD))

    # Role hint
    hint = ROLE_HINTS.get(ut.unit_class)
    if hint:
        lines.append((hint, C_HINT))

    return lines


# ---------------------------------------------------------------------------
# Terrain tooltip
# ---------------------------------------------------------------------------

TERRAIN_HINTS: dict[str, str] = {
    "plain":     "Open ground. No defence bonus -- bad for infantry.",
    "forest":    "Heavy cover. Blocks vision past it. Ambush spot.",
    "mountain":  "Impassable to vehicles. Blocks line-of-sight.",
    "hills":     "Light cover + extra vision. Good for snipers.",
    "road":      "Cheap movement. Exposes units (no cover).",
    "river":     "Most units blocked. Foot can wade slowly.",
    "bridge":    "Choke point. Hold it to control map flow.",
    "city":      "Strong cover + income. Send engineers here.",
    "oil_well":  "Engineers capture for oil income.",
    "airfield":  "Air staging. High defence; capturable.",
    "hq":        "Faction HQ. Lose it = game over (some modes).",
}


def terrain_tooltip_lines(tile: Tile) -> list[tuple[str, tuple[int, int, int]]]:
    _ensure_matchups()
    tt = tile.terrain
    lines: list[tuple[str, tuple[int, int, int]]] = []

    # Title
    owner_part = ""
    if tile.owner_faction:
        owner_part = f"  [owned by {tile.owner_faction}]"
    elif tt.capturable:
        owner_part = "  [neutral]"
    lines.append((f"{tt.name}{owner_part}", C_TITLE))

    # Defence + vision modifiers
    def_color = C_GOOD if tt.defense_bonus >= 3 else (
        C_VALUE if tt.defense_bonus > 0 else C_LABEL
    )
    vis_sign = f"+{tt.vision_modifier}" if tt.vision_modifier > 0 else str(tt.vision_modifier)
    los = "  (blocks LOS)" if tt.blocks_los else ""
    lines.append((f"DEF +{tt.defense_bonus}  VIS {vis_sign}{los}", def_color))

    # Income
    if tt.income_credits or tt.income_oil:
        bits = []
        if tt.income_credits:
            bits.append(f"+{tt.income_credits} cr/turn")
        if tt.income_oil:
            bits.append(f"+{tt.income_oil} oil/turn")
        lines.append(("Income: " + "  ".join(bits), C_WARN))

    # Capture info
    if tt.capturable:
        if tile.capture_progress > 0 and tile.capturing_faction:
            lines.append(
                (f"Being captured by {tile.capturing_faction}: "
                 f"{tile.capture_progress}/3",
                 C_WARN)
            )
        else:
            lines.append(("Engineers can capture (3 turns).", C_HINT))

    # Move-cost summary by category
    parts = []
    for cat in MOVE_CATEGORIES:
        cost = tt.move_cost.get(cat)
        if cost is None:
            parts.append(f"{cat[:3]}=X")
        else:
            parts.append(f"{cat[:3]}={cost}")
    lines.append(("Move cost: " + " ".join(parts), C_LABEL))

    # Hint
    hint = TERRAIN_HINTS.get(tt.id)
    if hint:
        lines.append((hint, C_HINT))

    return lines


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def draw_tooltip(
    surface: pygame.Surface,
    lines: list[tuple[str, tuple[int, int, int]]],
    anchor: tuple[int, int],
    font: pygame.font.Font,
    screen_size: tuple[int, int],
) -> Optional[pygame.Rect]:
    """Render *lines* as a tooltip bubble near *anchor*.

    Auto-flips horizontally/vertically so the bubble always fits inside
    *screen_size*. Returns the bubble's final rect (or None if empty)."""
    if not lines:
        return None

    # Render each line to a surface up front so we can size the panel.
    surfs = [font.render(txt, True, col) for txt, col in lines]
    line_h = font.get_linesize()
    text_h = len(surfs) * line_h + (len(surfs) - 1) * LINE_GAP
    text_w = max(s.get_width() for s in surfs)

    panel_w = text_w + PADDING * 2
    panel_h = text_h + PADDING * 2

    sw, sh = screen_size
    ax, ay = anchor
    gap = 18

    # Default: anchor below-right of cursor.
    px = ax + gap
    py = ay + gap
    if px + panel_w > sw - 4:
        px = ax - gap - panel_w     # flip to the left
    if px < 4:
        px = 4
    if py + panel_h > sh - 4:
        py = ay - gap - panel_h     # flip above
    if py < 4:
        py = 4

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill(BG_COLOR)
    pygame.draw.rect(panel, BORDER, panel.get_rect(), 1)

    y = PADDING
    for s in surfs:
        panel.blit(s, (PADDING, y))
        y += line_h + LINE_GAP

    rect = pygame.Rect(px, py, panel_w, panel_h)
    surface.blit(panel, (px, py))
    return rect


# ---------------------------------------------------------------------------
# Convenience helpers (sanity-tests use these)
# ---------------------------------------------------------------------------

def best_matchups(unit_class: str) -> list[str]:
    _ensure_matchups()
    return list(_BEST_VS.get(unit_class, []))


def worst_matchups(unit_class: str) -> list[str]:
    _ensure_matchups()
    return list(_WORST_VS.get(unit_class, []))
