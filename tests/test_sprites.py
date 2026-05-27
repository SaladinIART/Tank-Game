"""
Tests for CP-24: sprite cache and renderer integration.

These tests run headlessly — pygame.display.init() is NOT called so they work
in CI without a display.  The sprite loader must work in this environment because
it lazy-loads on first request (no display required for pygame.image operations
once ``pygame.init()`` has been called at import time via the test setup).
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pygame

# Initialise pygame in non-display mode before any test runs.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame.init()

from src.render.sprites import (
    SpriteCache,
    clear_cache,
    get_terrain_sprite,
    get_unit_sprite,
    SPRITE_DIR,
)

TERRAIN_IDS = [
    "plain", "forest", "mountain", "road", "river",
    "bridge", "city", "oil_well", "airfield", "hq",
]
UNIT_CLASSES = [
    "infantry", "engineer", "recon", "vehicle",
    "artillery", "aa", "sniper", "jet", "helicopter", "bomber",
]


# ---------------------------------------------------------------------------
# SpriteCache unit tests
# ---------------------------------------------------------------------------

class TestSpriteCache:
    def setup_method(self):
        self.cache = SpriteCache()

    def test_missing_file_returns_none(self, tmp_path):
        result = self.cache._load(tmp_path / "nonexistent.png", 32)
        assert result is None

    def test_missing_cached_as_none(self, tmp_path):
        path = tmp_path / "nonexistent.png"
        self.cache._load(path, 32)
        self.cache._load(path, 32)   # second call — should not raise
        assert self.cache._cache[(str(path), 32)] is None

    def test_valid_png_loads_and_scales(self, tmp_path):
        # Create a small real PNG using pygame
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        surf.fill((255, 0, 0, 255))
        path = tmp_path / "test.png"
        pygame.image.save(surf, str(path))

        result = self.cache._load(path, 32)
        assert result is not None
        assert result.get_size() == (32, 32)

    def test_cache_returns_same_object(self, tmp_path):
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        surf.fill((0, 255, 0, 255))
        path = tmp_path / "test2.png"
        pygame.image.save(surf, str(path))

        r1 = self.cache._load(path, 48)
        r2 = self.cache._load(path, 48)
        assert r1 is r2

    def test_different_sizes_cached_separately(self, tmp_path):
        surf = pygame.Surface((128, 128), pygame.SRCALPHA)
        surf.fill((0, 0, 255, 255))
        path = tmp_path / "test3.png"
        pygame.image.save(surf, str(path))

        r32 = self.cache._load(path, 32)
        r64 = self.cache._load(path, 64)
        assert r32 is not r64
        assert r32.get_size() == (32, 32)
        assert r64.get_size() == (64, 64)

    def test_clear_flushes_cache(self, tmp_path):
        surf = pygame.Surface((64, 64))
        path = tmp_path / "test4.png"
        pygame.image.save(surf, str(path))
        self.cache._load(path, 32)
        assert len(self.cache._cache) == 1
        self.cache.clear()
        assert len(self.cache._cache) == 0

    def test_terrain_sprite_path(self, tmp_path):
        # Patch SPRITE_DIR to tmp_path
        (tmp_path / "terrain").mkdir()
        surf = pygame.Surface((128, 128), pygame.SRCALPHA)
        pygame.image.save(surf, str(tmp_path / "terrain" / "forest.png"))
        with patch("src.render.sprites._TERRAIN_DIR", tmp_path / "terrain"):
            result = self.cache.terrain_sprite("forest", 64)
        assert result is not None

    def test_unit_sprite_path(self, tmp_path):
        (tmp_path / "units").mkdir()
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.image.save(surf, str(tmp_path / "units" / "infantry.png"))
        with patch("src.render.sprites._UNIT_DIR", tmp_path / "units"):
            result = self.cache.unit_sprite("infantry", 32)
        assert result is not None


# ---------------------------------------------------------------------------
# Generated sprite assets exist and load correctly
# ---------------------------------------------------------------------------

class TestGeneratedSprites:
    """These tests require that ``tools/gen_sprites.py`` has been run first."""

    def test_terrain_sprites_exist(self):
        missing = [
            tid for tid in TERRAIN_IDS
            if not (SPRITE_DIR / "terrain" / f"{tid}.png").exists()
        ]
        assert not missing, f"Missing terrain sprites: {missing}"

    def test_unit_sprites_exist(self):
        missing = [
            uc for uc in UNIT_CLASSES
            if not (SPRITE_DIR / "units" / f"{uc}.png").exists()
        ]
        assert not missing, f"Missing unit sprites: {missing}"

    def test_terrain_sprites_load_at_size_64(self):
        clear_cache()
        for tid in TERRAIN_IDS:
            result = get_terrain_sprite(tid, 64)
            assert result is not None, f"terrain sprite '{tid}' failed to load"
            assert result.get_size() == (64, 64)

    def test_unit_sprites_load_at_size_32(self):
        clear_cache()
        for uc in UNIT_CLASSES:
            result = get_unit_sprite(uc, 32)
            assert result is not None, f"unit sprite '{uc}' failed to load"
            assert result.get_size() == (32, 32)

    def test_terrain_sprites_have_alpha(self):
        clear_cache()
        for tid in TERRAIN_IDS:
            spr = get_terrain_sprite(tid, 32)
            assert spr is not None
            # Surface should have per-pixel alpha (SRCALPHA was set at gen time)
            assert spr.get_flags() & pygame.SRCALPHA or spr.get_masks()[3] != 0, \
                f"terrain '{tid}' sprite has no alpha channel"

    def test_module_level_helpers_return_surface(self):
        clear_cache()
        assert get_terrain_sprite("forest", 48) is not None
        assert get_unit_sprite("vehicle", 24) is not None

    def test_unknown_terrain_returns_none(self):
        result = get_terrain_sprite("nonexistent_biome_xyz", 32)
        assert result is None

    def test_unknown_unit_class_returns_none(self):
        result = get_unit_sprite("space_marine", 32)
        assert result is None

    def test_clear_cache_invalidates(self):
        get_terrain_sprite("plain", 32)
        clear_cache()
        # After clear, next call reloads from disk (no error)
        result = get_terrain_sprite("plain", 32)
        assert result is not None
