"""
Procedural sprite generator for Modern Warfare 4X.

Generates PNG icon assets under ``assets/sprites/`` using pygame drawing
primitives.  Outputs:

  assets/sprites/terrain/<terrain_id>.png   (128 × 128, RGBA)
  assets/sprites/units/<unit_class>.png     (64 × 64,  RGBA)

Run from the project root::

    python tools/gen_sprites.py

The generated images serve as high-quality programmer-art placeholders.  To
swap in Kenney (or any external) art, replace individual PNGs at the same
paths — the sprite cache picks them up automatically.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Allow importing from project root when run directly.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame

pygame.init()

# ---------------------------------------------------------------------------
# Output directories
# ---------------------------------------------------------------------------

TERRAIN_DIR = ROOT / "assets" / "sprites" / "terrain"
UNIT_DIR    = ROOT / "assets" / "sprites" / "units"
TERRAIN_DIR.mkdir(parents=True, exist_ok=True)
UNIT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SIZE_T = 128   # terrain sprites
SIZE_U = 64    # unit sprites


def new_surface(size: int) -> pygame.Surface:
    """Transparent RGBA surface."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


def save(surf: pygame.Surface, path: Path) -> None:
    pygame.image.save(surf, str(path))
    print(f"  wrote {path.relative_to(ROOT)}")


def _hex_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """Pointy-top hexagon polygon points."""
    return [
        (cx + r * math.cos(math.radians(60 * i - 90)),
         cy + r * math.sin(math.radians(60 * i - 90)))
        for i in range(6)
    ]


def draw_hex_bg(surf: pygame.Surface, color: tuple, border: tuple = (0, 0, 0, 200)) -> None:
    """Fill background with a centred hex polygon."""
    n = surf.get_width()
    pts = _hex_points(n // 2, n // 2, n // 2 - 3)
    pygame.draw.polygon(surf, (*color, 255), pts)
    pygame.draw.polygon(surf, border, pts, 2)


# ---------------------------------------------------------------------------
# Terrain sprite generators
# ---------------------------------------------------------------------------

def _t_plain() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (120, 155, 80))
    # Subtle horizontal grass strokes
    c = (90, 130, 55, 150)
    for y in range(35, SIZE_T - 35, 14):
        for x in range(30, SIZE_T - 30, 20):
            pygame.draw.line(s, c, (x, y), (x + 8, y - 5), 2)
            pygame.draw.line(s, c, (x + 4, y), (x + 12, y - 5), 2)
    return s


def _t_forest() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (34, 90, 34))
    # Three tree silhouettes (circles for canopy)
    for cx, cy, r in [(52, 52, 18), (76, 58, 16), (50, 76, 14)]:
        pygame.draw.circle(s, (20, 65, 20, 255), (cx, cy), r)
        pygame.draw.circle(s, (50, 120, 50, 255), (cx - 3, cy - 3), r - 4)
        # Trunk
        pygame.draw.rect(s, (80, 50, 20, 255), (cx - 3, cy + r - 4, 6, 8))
    return s


def _t_mountain() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (100, 90, 80))
    # Two mountain peaks
    for pts, snow in [
        ([(40, 95), (64, 35), (88, 95)], [(55, 52), (64, 35), (73, 52)]),
        ([(20, 95), (46, 55), (72, 95)], [(38, 67), (46, 55), (54, 67)]),
    ]:
        pygame.draw.polygon(s, (130, 120, 105, 255), pts)
        pygame.draw.polygon(s, (80, 80, 80, 255), pts, 2)
        pygame.draw.polygon(s, (230, 235, 245, 255), snow)
    return s


def _t_road() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (155, 145, 120))
    # Road surface band (vertical)
    cx = SIZE_T // 2
    pygame.draw.rect(s, (175, 168, 145, 255), (cx - 14, 10, 28, SIZE_T - 20))
    # Dashed centre line
    for y in range(20, SIZE_T - 20, 16):
        pygame.draw.rect(s, (230, 215, 60, 200), (cx - 2, y, 4, 8))
    # Edges
    pygame.draw.line(s, (120, 112, 90, 255), (cx - 14, 10), (cx - 14, SIZE_T - 10), 2)
    pygame.draw.line(s, (120, 112, 90, 255), (cx + 14, 10), (cx + 14, SIZE_T - 10), 2)
    return s


def _t_river() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (40, 110, 190))
    # Animated-looking wave lines
    cx = SIZE_T // 2
    for y in range(30, SIZE_T - 25, 16):
        pts = []
        for x in range(cx - 24, cx + 26, 4):
            wave = math.sin((x - cx) * 0.25 + y * 0.1) * 5
            pts.append((x, y + wave))
        if len(pts) >= 2:
            pygame.draw.lines(s, (160, 210, 255, 200), False, pts, 2)
    return s


def _t_bridge() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (40, 110, 190))
    cx = SIZE_T // 2
    # Bridge deck
    pygame.draw.rect(s, (150, 110, 65, 255), (cx - 18, 18, 36, SIZE_T - 36))
    # Planks
    for y in range(22, SIZE_T - 22, 9):
        pygame.draw.rect(s, (120, 85, 45, 255), (cx - 16, y, 32, 5))
    # Railings
    for dx in (-14, 14):
        pygame.draw.line(s, (90, 60, 30, 255), (cx + dx, 18), (cx + dx, SIZE_T - 18), 3)
    return s


def _t_city() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (140, 130, 120))
    # Buildings: 3 rectangles with flat roofs
    buildings = [
        (38, 55, 24, 40, (175, 165, 150)),
        (66, 45, 22, 50, (165, 158, 142)),
        (52, 60, 18, 35, (190, 180, 165)),
    ]
    for bx, by, bw, bh, col in buildings:
        pygame.draw.rect(s, (*col, 255), (bx, by, bw, bh))
        pygame.draw.rect(s, (80, 75, 70, 255), (bx, by, bw, bh), 2)
        # Windows
        for wx in range(bx + 4, bx + bw - 4, 8):
            for wy in range(by + 5, by + bh - 4, 10):
                col_w = (255, 230, 100, 200) if (wx + wy) % 20 < 10 else (50, 50, 70, 180)
                pygame.draw.rect(s, col_w, (wx, wy, 4, 4))
    return s


def _t_oil_well() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (70, 70, 55))
    cx = SIZE_T // 2
    # Derrick structure
    legs = [(cx - 18, 98), (cx + 18, 98), (cx - 6, 40), (cx + 6, 40)]
    pygame.draw.line(s, (60, 55, 45, 255), legs[0], legs[2], 4)
    pygame.draw.line(s, (60, 55, 45, 255), legs[1], legs[3], 4)
    pygame.draw.line(s, (60, 55, 45, 255), (cx - 18, 98), (cx + 18, 98), 4)
    # Cross-braces
    for y in range(55, 90, 18):
        t = (y - 40) / 60
        w = int(12 + t * 12)
        pygame.draw.line(s, (90, 80, 60, 255), (cx - w, y), (cx + w, y + 6), 2)
        pygame.draw.line(s, (90, 80, 60, 255), (cx + w, y), (cx - w, y + 6), 2)
    # Crown
    pygame.draw.line(s, (80, 75, 60, 255), (cx - 6, 40), (cx + 6, 40), 5)
    # Oil drip
    pygame.draw.circle(s, (20, 20, 20, 220), (cx, 105), 8)
    pygame.draw.circle(s, (40, 40, 35, 180), (cx, 108), 5)
    return s


def _t_airfield() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (150, 145, 130))
    cx, cy = SIZE_T // 2, SIZE_T // 2
    # Runway
    pygame.draw.rect(s, (120, 115, 105, 255), (cx - 8, 20, 16, SIZE_T - 40))
    # Threshold markings
    for y in range(26, SIZE_T - 26, 10):
        pygame.draw.rect(s, (240, 240, 240, 200), (cx - 6, y, 12, 4))
    # Taxiway circle
    pygame.draw.circle(s, (120, 115, 105, 255), (cx, cy), 24, 0)
    pygame.draw.circle(s, (200, 200, 190, 180), (cx, cy), 24, 2)
    # Wind arrow
    pygame.draw.line(s, (200, 50, 50, 230), (cx, cy + 16), (cx, cy - 16), 3)
    pygame.draw.polygon(s, (200, 50, 50, 230), [
        (cx, cy - 20), (cx - 6, cy - 10), (cx + 6, cy - 10)
    ])
    return s


def _t_hq() -> pygame.Surface:
    s = new_surface(SIZE_T)
    draw_hex_bg(s, (55, 70, 110))
    cx = SIZE_T // 2
    # Main HQ building
    bx, by, bw, bh = cx - 20, 40, 40, 50
    pygame.draw.rect(s, (80, 100, 160, 255), (bx, by, bw, bh))
    pygame.draw.rect(s, (160, 180, 240, 255), (bx, by, bw, bh), 2)
    # Roof
    pygame.draw.polygon(s, (110, 130, 200, 255), [
        (bx - 4, by), (cx, by - 16), (bx + bw + 4, by)
    ])
    # Door
    pygame.draw.rect(s, (30, 40, 70, 255), (cx - 6, by + bh - 18, 12, 18))
    # Flagpole + flag
    pygame.draw.line(s, (200, 200, 200, 255), (cx, by - 16), (cx, by - 40), 2)
    pygame.draw.polygon(s, (220, 50, 50, 255), [
        (cx, by - 40), (cx + 16, by - 33), (cx, by - 26)
    ])
    # "HQ" text
    font = pygame.font.SysFont("consolas", 20, bold=True)
    lbl  = font.render("HQ", True, (220, 240, 255))
    s.blit(lbl, (cx - lbl.get_width() // 2, by + 12))
    return s


# ---------------------------------------------------------------------------
# Unit sprite generators  (64 × 64, white/grey icons on transparent bg)
# Each icon is drawn as a white silhouette that the renderer tints at runtime.
# ---------------------------------------------------------------------------

def _icon_infantry() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Helmet
    pygame.draw.circle(s, (230, 230, 230, 255), (cx, cy - 12), 10)
    # Body
    pygame.draw.rect(s, (210, 210, 210, 255), (cx - 8, cy - 4, 16, 16))
    # Legs
    pygame.draw.line(s, (210, 210, 210, 255), (cx - 4, cy + 12), (cx - 6, cy + 22), 4)
    pygame.draw.line(s, (210, 210, 210, 255), (cx + 4, cy + 12), (cx + 6, cy + 22), 4)
    # Rifle
    pygame.draw.line(s, (255, 255, 255, 255), (cx + 8, cy - 8), (cx + 8, cy + 14), 3)
    return s


def _icon_engineer() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Hard hat
    pygame.draw.circle(s, (240, 200, 60, 255), (cx, cy - 12), 10)
    pygame.draw.ellipse(s, (240, 200, 60, 255), (cx - 14, cy - 16, 28, 8))
    # Body
    pygame.draw.rect(s, (210, 210, 210, 255), (cx - 8, cy - 4, 16, 16))
    # Wrench
    for dx, dy in [(-2, 0), (2, 0)]:
        pygame.draw.circle(s, (255, 255, 255, 255), (cx + 14 + dx, cy + 2 + dy), 4, 2)
    pygame.draw.line(s, (255, 255, 255, 255), (cx + 11, cy + 2), (cx + 3, cy + 12), 3)
    return s


def _icon_recon() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Binoculars shape: two circles connected
    for dx in (-8, 8):
        pygame.draw.circle(s, (230, 230, 230, 255), (cx + dx, cy), 8, 3)
        pygame.draw.circle(s, (180, 220, 255, 200), (cx + dx, cy), 5)
    pygame.draw.rect(s, (200, 200, 200, 255), (cx - 4, cy - 3, 8, 6))
    # Strap
    pygame.draw.arc(s, (200, 200, 200, 255),
                    (cx - 12, cy - 22, 24, 20), 0, math.pi, 3)
    return s


def _icon_vehicle() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Tank hull
    pygame.draw.rect(s, (200, 200, 200, 255), (cx - 18, cy - 4, 36, 18))
    # Turret
    pygame.draw.rect(s, (220, 220, 220, 255), (cx - 10, cy - 12, 20, 12))
    # Barrel
    pygame.draw.rect(s, (255, 255, 255, 255), (cx + 10, cy - 8, 14, 5))
    # Tracks
    pygame.draw.rect(s, (180, 180, 180, 255), (cx - 20, cy + 12, 40, 6))
    pygame.draw.rect(s, (180, 180, 180, 255), (cx - 20, cy - 6, 40, 4))
    # Track rollers
    for rx in range(cx - 16, cx + 18, 8):
        pygame.draw.circle(s, (200, 200, 200, 255), (rx, cy + 16), 4, 2)
    return s


def _icon_artillery() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Howitzer body
    pygame.draw.rect(s, (200, 200, 200, 255), (cx - 12, cy, 24, 14))
    # Barrel (angled up)
    pygame.draw.line(s, (230, 230, 230, 255), (cx, cy), (cx + 20, cy - 16), 6)
    # Wheels
    pygame.draw.circle(s, (200, 200, 200, 255), (cx - 10, cy + 14), 8, 3)
    pygame.draw.circle(s, (200, 200, 200, 255), (cx + 10, cy + 14), 8, 3)
    # Muzzle
    pygame.draw.circle(s, (255, 255, 255, 255), (cx + 20, cy - 16), 4)
    return s


def _icon_aa() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Mount
    pygame.draw.rect(s, (200, 200, 200, 255), (cx - 10, cy + 6, 20, 12))
    # Twin barrels pointing up
    for bx in (cx - 5, cx + 5):
        pygame.draw.rect(s, (230, 230, 230, 255), (bx - 2, cy - 14, 4, 22))
    # Radar dish
    pygame.draw.arc(s, (220, 220, 220, 255),
                    (cx + 8, cy - 4, 16, 10), 0, math.pi, 3)
    pygame.draw.line(s, (200, 200, 200, 255), (cx + 16, cy - 4), (cx + 16, cy + 8), 2)
    # Missiles
    for dx, angle in [(-14, -30), (14, 30)]:
        x2 = cx + dx + int(12 * math.cos(math.radians(90 + angle)))
        y2 = cy - 16 + int(12 * math.sin(math.radians(90 + angle)))
        pygame.draw.line(s, (255, 200, 50, 255), (cx + dx, cy - 4), (x2, y2), 3)
    return s


def _icon_sniper() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Crosshair
    for pts in [((cx - 18, cy), (cx - 6, cy)), ((cx + 6, cy), (cx + 18, cy)),
                ((cx, cy - 18), (cx, cy - 6)), ((cx, cy + 6), (cx, cy + 18))]:
        pygame.draw.line(s, (230, 230, 230, 255), *pts, 2)
    pygame.draw.circle(s, (230, 230, 230, 255), (cx, cy), 8, 2)
    pygame.draw.circle(s, (255, 80, 80, 200), (cx, cy), 3)
    # Rifle silhouette
    pygame.draw.line(s, (200, 200, 200, 255), (cx - 20, cy + 12), (cx + 22, cy + 12), 4)
    pygame.draw.rect(s, (200, 200, 200, 255), (cx - 4, cy + 8, 8, 8))
    return s


def _icon_jet() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Fuselage
    pygame.draw.polygon(s, (230, 230, 230, 255), [
        (cx + 20, cy), (cx - 16, cy - 4), (cx - 20, cy), (cx - 16, cy + 4)
    ])
    # Delta wings
    pygame.draw.polygon(s, (210, 210, 210, 255), [
        (cx + 4, cy), (cx - 14, cy - 18), (cx - 18, cy)
    ])
    pygame.draw.polygon(s, (210, 210, 210, 255), [
        (cx + 4, cy), (cx - 14, cy + 18), (cx - 18, cy)
    ])
    # Tail fins
    pygame.draw.polygon(s, (200, 200, 200, 255), [
        (cx - 14, cy), (cx - 20, cy - 8), (cx - 20, cy)
    ])
    pygame.draw.polygon(s, (200, 200, 200, 255), [
        (cx - 14, cy), (cx - 20, cy + 8), (cx - 20, cy)
    ])
    # Cockpit
    pygame.draw.ellipse(s, (150, 210, 255, 200), (cx + 6, cy - 4, 10, 8))
    return s


def _icon_helicopter() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Main rotor blades (X shape)
    for angle in (0, 90):
        x2a = cx + int(22 * math.cos(math.radians(angle)))
        y2a = cy + int(22 * math.sin(math.radians(angle)))
        x2b = cx - int(22 * math.cos(math.radians(angle)))
        y2b = cy - int(22 * math.sin(math.radians(angle)))
        pygame.draw.line(s, (220, 220, 220, 255), (x2a, y2a), (x2b, y2b), 4)
    # Hub
    pygame.draw.circle(s, (255, 255, 255, 255), (cx, cy), 4)
    # Body
    pygame.draw.ellipse(s, (200, 200, 200, 255), (cx - 12, cy + 4, 24, 12))
    # Tail boom
    pygame.draw.line(s, (190, 190, 190, 255), (cx - 12, cy + 10), (cx - 26, cy + 14), 4)
    # Tail rotor
    pygame.draw.line(s, (210, 210, 210, 255), (cx - 26, cy + 8), (cx - 26, cy + 20), 3)
    return s


def _icon_bomber() -> pygame.Surface:
    s = new_surface(SIZE_U)
    cx, cy = SIZE_U // 2, SIZE_U // 2
    # Fuselage
    pygame.draw.ellipse(s, (210, 210, 210, 255), (cx - 20, cy - 5, 40, 10))
    # Wide swept wings
    pygame.draw.polygon(s, (200, 200, 200, 255), [
        (cx - 10, cy - 2), (cx + 6, cy - 2), (cx + 2, cy - 20), (cx - 20, cy - 16)
    ])
    pygame.draw.polygon(s, (200, 200, 200, 255), [
        (cx - 10, cy + 2), (cx + 6, cy + 2), (cx + 2, cy + 20), (cx - 20, cy + 16)
    ])
    # Bomb-bay doors hint
    pygame.draw.line(s, (140, 140, 140, 255), (cx - 8, cy), (cx + 8, cy), 2)
    # Cockpit blister
    pygame.draw.ellipse(s, (150, 210, 255, 180), (cx + 8, cy - 4, 10, 8))
    return s


# ---------------------------------------------------------------------------
# Dispatch tables
# ---------------------------------------------------------------------------

TERRAIN_GENERATORS: dict[str, object] = {
    "plain":    _t_plain,
    "forest":   _t_forest,
    "mountain": _t_mountain,
    "road":     _t_road,
    "river":    _t_river,
    "bridge":   _t_bridge,
    "city":     _t_city,
    "oil_well": _t_oil_well,
    "airfield": _t_airfield,
    "hq":       _t_hq,
}

UNIT_GENERATORS: dict[str, object] = {
    "infantry":   _icon_infantry,
    "engineer":   _icon_engineer,
    "recon":      _icon_recon,
    "vehicle":    _icon_vehicle,
    "artillery":  _icon_artillery,
    "aa":         _icon_aa,
    "sniper":     _icon_sniper,
    "jet":        _icon_jet,
    "helicopter": _icon_helicopter,
    "bomber":     _icon_bomber,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("Generating terrain sprites...")
    for terrain_id, gen in TERRAIN_GENERATORS.items():
        surf = gen()
        save(surf, TERRAIN_DIR / f"{terrain_id}.png")

    print("Generating unit sprites...")
    for unit_class, gen in UNIT_GENERATORS.items():
        surf = gen()
        save(surf, UNIT_DIR / f"{unit_class}.png")

    print(f"Done. {len(TERRAIN_GENERATORS)} terrain + {len(UNIT_GENERATORS)} unit sprites.")
    pygame.quit()


if __name__ == "__main__":
    main()
