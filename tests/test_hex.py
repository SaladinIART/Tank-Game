from src.engine.hex import (
    DIRECTIONS,
    Hex,
    axial_to_pixel,
    distance,
    hex_line,
    hex_ring,
    hexes_within,
    neighbours,
    pixel_to_axial,
)


def test_hex_arithmetic_and_s():
    h = Hex(2, -1)
    assert h.s == -1
    assert h + Hex(1, 1) == Hex(3, 0)
    assert h - Hex(1, 1) == Hex(1, -2)
    assert Hex(0, 0).s == 0


def test_directions_unique_and_unit_distance():
    assert len(DIRECTIONS) == 6
    assert len(set(DIRECTIONS)) == 6
    for d in DIRECTIONS:
        assert distance(Hex(0, 0), d) == 1


def test_neighbours_six_unique_adjacent():
    n = neighbours(Hex(0, 0))
    assert len(n) == 6
    assert len(set(n)) == 6
    for nb in n:
        assert distance(Hex(0, 0), nb) == 1


def test_distance_known_pairs():
    assert distance(Hex(0, 0), Hex(0, 0)) == 0
    assert distance(Hex(0, 0), Hex(3, -1)) == 3
    assert distance(Hex(-2, 2), Hex(2, -2)) == 4
    # symmetric
    assert distance(Hex(1, 2), Hex(-3, 0)) == distance(Hex(-3, 0), Hex(1, 2))


def test_hexes_within_counts():
    # Disk of radius N has 3N^2 + 3N + 1 hexes.
    for n in range(0, 6):
        expected = 3 * n * n + 3 * n + 1
        assert len(list(hexes_within(Hex(0, 0), n))) == expected


def test_hex_ring_counts_and_distances():
    assert list(hex_ring(Hex(0, 0), 0)) == [Hex(0, 0)]
    for n in range(1, 6):
        ring = list(hex_ring(Hex(0, 0), n))
        assert len(ring) == 6 * n
        for h in ring:
            assert distance(Hex(0, 0), h) == n


def test_hex_line_endpoints_length_and_continuity():
    a, b = Hex(0, 0), Hex(3, -1)
    line = hex_line(a, b)
    assert line[0] == a
    assert line[-1] == b
    assert len(line) == distance(a, b) + 1
    # Consecutive hexes are adjacent (or equal at degenerate edge).
    for i in range(len(line) - 1):
        assert distance(line[i], line[i + 1]) <= 1


def test_hex_line_zero_distance():
    a = Hex(5, -3)
    assert hex_line(a, a) == [a]


def test_pixel_roundtrip_for_integer_hexes():
    size = 40.0
    for q in range(-6, 7):
        for r in range(-6, 7):
            h = Hex(q, r)
            x, y = axial_to_pixel(h, size)
            assert pixel_to_axial(x, y, size) == h


def test_pixel_to_axial_picks_closest_when_jittered():
    # Tiny perturbations should still land on the same hex.
    size = 40.0
    h = Hex(2, -3)
    x, y = axial_to_pixel(h, size)
    for dx, dy in [(2.0, 0.0), (-2.0, 0.0), (0.0, 2.0), (0.0, -2.0)]:
        assert pixel_to_axial(x + dx, y + dy, size) == h
