"""
Hex coordinate math (pointy-top, axial coordinates).

Convention: pointy-top hexes laid out so that +q goes East and +r goes SouthEast.
Cube coord s = -q - r is implicit; we keep math in 2D axial and derive s when needed.

Reference: https://www.redblobgames.com/grids/hexagons/

Pure functions only. No Pygame dependency. Safe to import in the render layer
and the AI layer alike.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterator

SQRT3 = sqrt(3)


@dataclass(frozen=True)
class Hex:
    q: int
    r: int

    @property
    def s(self) -> int:
        return -self.q - self.r

    def __add__(self, other: "Hex") -> "Hex":
        return Hex(self.q + other.q, self.r + other.r)

    def __sub__(self, other: "Hex") -> "Hex":
        return Hex(self.q - other.q, self.r - other.r)


# Pointy-top neighbour direction vectors. Order: E, NE, NW, W, SW, SE.
DIRECTIONS: tuple[Hex, ...] = (
    Hex(+1, 0),   # E
    Hex(+1, -1),  # NE
    Hex(0, -1),   # NW
    Hex(-1, 0),   # W
    Hex(-1, +1),  # SW
    Hex(0, +1),   # SE
)


def neighbours(h: Hex) -> tuple[Hex, ...]:
    return tuple(h + d for d in DIRECTIONS)


def distance(a: Hex, b: Hex) -> int:
    return (abs(a.q - b.q) + abs(a.r - b.r) + abs(a.s - b.s)) // 2


def hexes_within(center: Hex, radius: int) -> Iterator[Hex]:
    """Every hex within `radius` steps of `center`, inclusive."""
    for dq in range(-radius, radius + 1):
        r_min = max(-radius, -radius - dq)
        r_max = min(radius, radius - dq)
        for dr in range(r_min, r_max + 1):
            yield Hex(center.q + dq, center.r + dr)


def hex_ring(center: Hex, radius: int) -> Iterator[Hex]:
    """Hexes exactly `radius` steps from `center`."""
    if radius == 0:
        yield center
        return
    # Simple correctness-first impl: filter the disk. Cheap for radii < ~20.
    for h in hexes_within(center, radius):
        if distance(center, h) == radius:
            yield h


def _round_axial(qf: float, rf: float) -> Hex:
    """Round fractional axial coords to the nearest integer hex (cube rounding)."""
    sf = -qf - rf
    q = round(qf)
    r = round(rf)
    s = round(sf)
    dq = abs(q - qf)
    dr = abs(r - rf)
    ds = abs(s - sf)
    # The component with the largest rounding error is reconstructed from the others.
    if dq > dr and dq > ds:
        q = -r - s
    elif dr > ds:
        r = -q - s
    return Hex(int(q), int(r))


def hex_line(a: Hex, b: Hex) -> list[Hex]:
    """Hexes along a straight line from a to b (inclusive)."""
    n = distance(a, b)
    if n == 0:
        return [a]
    out: list[Hex] = []
    for i in range(n + 1):
        t = i / n
        qf = a.q + (b.q - a.q) * t
        rf = a.r + (b.r - a.r) * t
        out.append(_round_axial(qf, rf))
    return out


def axial_to_pixel(h: Hex, size: float) -> tuple[float, float]:
    """Pointy-top axial -> pixel center. `size` is corner-to-center radius."""
    x = size * (SQRT3 * h.q + (SQRT3 / 2) * h.r)
    y = size * (1.5 * h.r)
    return (x, y)


def pixel_to_axial(x: float, y: float, size: float) -> Hex:
    """Inverse of axial_to_pixel."""
    qf = ((SQRT3 / 3) * x - (1 / 3) * y) / size
    rf = ((2 / 3) * y) / size
    return _round_axial(qf, rf)
