"""
Tests for src/render/tooltip.py -- hover bubbles for units + terrain.

We don't render to a visible screen here; we just verify that:
  - line builders produce non-empty, well-formed (text, color) tuples
  - best/worst matchups are pulled from the real damage matrix
  - tooltip draw fits within screen bounds and never extends off-edge
"""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.engine.hex import Hex  # noqa: E402
from src.engine.tile import Tile, load_terrain  # noqa: E402
from src.engine.unit import Unit, load_units  # noqa: E402
from src.render.tooltip import (  # noqa: E402
    best_matchups,
    draw_tooltip,
    terrain_tooltip_lines,
    unit_tooltip_lines,
    worst_matchups,
)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_module(module):
    pygame.init()
    load_terrain()
    load_units()


def teardown_module(module):
    pygame.quit()


# ---------------------------------------------------------------------------
# Unit tooltip content
# ---------------------------------------------------------------------------

class TestUnitTooltipLines:
    def test_nato_inf_l_includes_basics(self):
        u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
        lines = unit_tooltip_lines(u)
        text = "\n".join(t for t, _ in lines).lower()
        assert "nato" in text
        assert "infantry" in text
        assert "hp" in text and "10" in text
        assert "atk" in text and "def" in text and "mov" in text

    def test_engineer_shows_capture_tag(self):
        u = Unit(type_id="nato_engineer", faction="NATO", hex=Hex(0, 0))
        text = "\n".join(t for t, _ in unit_tooltip_lines(u)).lower()
        assert "capture" in text

    def test_kamikaze_shows_kamikaze_tag(self):
        u = Unit(type_id="guerilla_kamikaze", faction="GUERILLA", hex=Hex(0, 0))
        text = "\n".join(t for t, _ in unit_tooltip_lines(u)).upper()
        assert "KAMIKAZE" in text

    def test_stealth_unit_shows_stealth_tag(self):
        u = Unit(type_id="guerilla_drone_recon", faction="GUERILLA", hex=Hex(0, 0))
        text = "\n".join(t for t, _ in unit_tooltip_lines(u)).lower()
        assert "stealth" in text

    def test_artillery_marks_indirect(self):
        u = Unit(type_id="brics_hypersonic", faction="BRICS", hex=Hex(0, 0))
        text = "\n".join(t for t, _ in unit_tooltip_lines(u)).lower()
        assert "indirect" in text

    def test_includes_best_and_weak_lines(self):
        u = Unit(type_id="nato_aa_l", faction="NATO", hex=Hex(0, 0))
        text = "\n".join(t for t, _ in unit_tooltip_lines(u))
        assert "BEST vs:" in text
        assert "WEAK vs:" in text

    def test_lines_are_text_color_tuples(self):
        u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0))
        for entry in unit_tooltip_lines(u):
            assert isinstance(entry, tuple) and len(entry) == 2
            txt, col = entry
            assert isinstance(txt, str) and txt
            assert isinstance(col, tuple) and len(col) == 3
            assert all(0 <= c <= 255 for c in col)

    def test_low_hp_shows_warning_color(self):
        u = Unit(type_id="nato_inf_l", faction="NATO", hex=Hex(0, 0), hp=2)
        lines = unit_tooltip_lines(u)
        # HP line starts with "HP:"; colour should be reddish (more R than G).
        hp_line = next(t for t in lines if t[0].startswith("HP:"))
        hp_color = hp_line[1]
        assert hp_color[0] > hp_color[1], (
            f"Low HP should render warning red, got {hp_color}"
        )


# ---------------------------------------------------------------------------
# Matchup correctness from the real matrix
# ---------------------------------------------------------------------------

class TestMatchups:
    def test_aa_best_includes_air(self):
        best = best_matchups("aa")
        # AA does 8-9 vs jet/helicopter/bomber -- at least one must be air
        assert any(b in ("jet", "helicopter", "bomber") for b in best)

    def test_infantry_weak_vs_jet(self):
        # Infantry does 0 vs jet -- jet must show up in weak list
        assert "jet" in worst_matchups("infantry")

    def test_bomber_weak_vs_air(self):
        # Bomber does 0 vs jet -- jet must show up in weak list
        worst = worst_matchups("bomber")
        assert "jet" in worst

    def test_all_unit_classes_have_matchups(self):
        from src.engine.unit import VALID_UNIT_CLASSES
        for cls in VALID_UNIT_CLASSES:
            assert best_matchups(cls), f"No best matchups for {cls}"
            assert worst_matchups(cls), f"No worst matchups for {cls}"


# ---------------------------------------------------------------------------
# Terrain tooltip content
# ---------------------------------------------------------------------------

class TestTerrainTooltipLines:
    def test_city_shows_capturable_and_income(self):
        tile = Tile(hex=Hex(0, 0), terrain_id="city")
        text = "\n".join(t for t, _ in terrain_tooltip_lines(tile)).lower()
        assert "city" in text
        assert "neutral" in text or "owned" in text
        assert "capture" in text
        assert "income" in text or "cr/turn" in text

    def test_mountain_shows_blocks_los(self):
        tile = Tile(hex=Hex(0, 0), terrain_id="mountain")
        text = "\n".join(t for t, _ in terrain_tooltip_lines(tile)).lower()
        assert "blocks los" in text

    def test_forest_shows_move_cost(self):
        tile = Tile(hex=Hex(0, 0), terrain_id="forest")
        text = "\n".join(t for t, _ in terrain_tooltip_lines(tile)).lower()
        assert "move cost" in text

    def test_owned_tile_shows_owner(self):
        tile = Tile(hex=Hex(0, 0), terrain_id="city", owner_faction="NATO")
        text = "\n".join(t for t, _ in terrain_tooltip_lines(tile))
        assert "NATO" in text

    def test_river_shows_x_for_blocked_categories(self):
        tile = Tile(hex=Hex(0, 0), terrain_id="river")
        text = "\n".join(t for t, _ in terrain_tooltip_lines(tile))
        # River blocks at least one category -- expect "X" in move-cost summary
        assert "=X" in text


# ---------------------------------------------------------------------------
# Tooltip rendering (positioning + edge flipping)
# ---------------------------------------------------------------------------

class TestDrawTooltip:
    def setup_method(self):
        self.screen = pygame.Surface((800, 600))
        self.font = pygame.font.SysFont("consolas", 14)

    def _lines(self):
        return [("Hello world", (255, 255, 255)), ("Line 2", (200, 200, 200))]

    def test_fits_when_anchored_near_top_left(self):
        rect = draw_tooltip(
            self.screen, self._lines(), (10, 10), self.font, (800, 600)
        )
        assert rect is not None
        assert 0 <= rect.left and rect.right <= 800
        assert 0 <= rect.top and rect.bottom <= 600

    def test_flips_left_when_anchored_near_right_edge(self):
        rect = draw_tooltip(
            self.screen, self._lines(), (790, 300), self.font, (800, 600)
        )
        assert rect is not None
        assert rect.right <= 800

    def test_flips_up_when_anchored_near_bottom_edge(self):
        rect = draw_tooltip(
            self.screen, self._lines(), (400, 595), self.font, (800, 600)
        )
        assert rect is not None
        assert rect.bottom <= 600

    def test_empty_lines_returns_none(self):
        rect = draw_tooltip(
            self.screen, [], (50, 50), self.font, (800, 600)
        )
        assert rect is None
