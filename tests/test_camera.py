import pytest
from src.engine.hex import Hex
from src.render.camera import Camera

W, H = 1280, 720


@pytest.fixture
def cam():
    return Camera(W, H, hex_size=36.0, offset_x=60.0, offset_y=60.0)


def test_world_screen_roundtrip(cam):
    for wx, wy in [(0, 0), (100, -50), (-300, 200)]:
        sx, sy = cam.world_to_screen(wx, wy)
        wx2, wy2 = cam.screen_to_world(sx, sy)
        assert abs(wx2 - wx) < 1e-9
        assert abs(wy2 - wy) < 1e-9


def test_hex_to_screen_then_back(cam):
    for h in [Hex(0, 0), Hex(5, -3), Hex(-2, 4)]:
        sx, sy = cam.hex_to_screen(h)
        h2 = cam.screen_to_hex(sx, sy)
        assert h2 == h


def test_zoom_keeps_anchor_fixed(cam):
    # Zoom anchored at a hex's own center → that hex must stay at the same screen pos.
    anchor_hex = Hex(3, 3)
    sx, sy = cam.hex_to_screen(anchor_hex)

    cam.zoom(1.5, sx, sy)

    sx_after, sy_after = cam.hex_to_screen(anchor_hex)
    assert abs(sx_after - sx) < 0.5
    assert abs(sy_after - sy) < 0.5


def test_zoom_clamps_to_min(cam):
    for _ in range(30):
        cam.zoom(0.5, W / 2, H / 2)
    assert cam.hex_size >= 14.0


def test_zoom_clamps_to_max(cam):
    for _ in range(30):
        cam.zoom(2.0, W / 2, H / 2)
    assert cam.hex_size <= 80.0


def test_hex_size_default():
    cam = Camera(W, H)
    assert cam.hex_size == 36.0
