"""
Sprite cache and loader for hex terrain icons + unit class icons.

All sprites live under ``assets/sprites/``:

    assets/sprites/terrain/<terrain_id>.png   — transparent hex icons (128 × 128)
    assets/sprites/units/<unit_class>.png     — unit class icons (64 × 64)

Sprites are loaded on first request, scaled to the caller's *size*, and cached
under a ``(path, size)`` key so each pixel-size variant is only created once.

When a sprite file is absent the helpers return ``None`` and the renderer falls
back to its polygon / circle + letter programmer-art path — meaning the game
always runs even with no assets installed.

To swap in Kenney (or any other) art packs, simply drop PNG files at the paths
above that match the terrain / unit-class IDs in ``data/terrain.json`` and
``data/units.json``.  The cache is automatically invalidated on the next call
to ``clear_cache()``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pygame

# Root directory for all sprite assets (relative to project root, which is
# also the pygame working directory when the game is launched).
SPRITE_DIR = Path("assets/sprites")

# Sub-directories
_TERRAIN_DIR = SPRITE_DIR / "terrain"
_UNIT_DIR    = SPRITE_DIR / "units"


class SpriteCache:
    """Loads, scales, and caches pygame Surfaces from PNG files.

    Thread-safety: not required — pygame is single-threaded by design.
    """

    def __init__(self) -> None:
        # key → (path, target_size_px)  value → Surface | None
        self._cache: dict[tuple[str, int], Optional[pygame.Surface]] = {}

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _load(self, path: Path, size: int) -> Optional[pygame.Surface]:
        key = (str(path), size)
        if key not in self._cache:
            if path.is_file():
                try:
                    raw = pygame.image.load(str(path))
                    # convert_alpha() requires an active display; fall back to
                    # the raw surface (still RGBA) when running headless.
                    try:
                        raw = raw.convert_alpha()
                    except pygame.error:
                        pass  # headless / no display — raw load still works
                    self._cache[key] = pygame.transform.smoothscale(raw, (size, size))
                except Exception:
                    self._cache[key] = None
            else:
                self._cache[key] = None
        return self._cache[key]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def terrain_sprite(self, terrain_id: str, size: int) -> Optional[pygame.Surface]:
        """Return a *size × size* surface for *terrain_id*, or ``None``."""
        return self._load(_TERRAIN_DIR / f"{terrain_id}.png", size)

    def unit_sprite(self, unit_class: str, size: int) -> Optional[pygame.Surface]:
        """Return a *size × size* surface for *unit_class*, or ``None``."""
        return self._load(_UNIT_DIR / f"{unit_class}.png", size)

    def clear(self) -> None:
        """Flush all cached entries (useful after hot-swapping assets)."""
        self._cache.clear()


# ---------------------------------------------------------------------------
# Module-level shared instance — single cache per process
# ---------------------------------------------------------------------------

_shared_cache = SpriteCache()


def get_terrain_sprite(terrain_id: str, size: int) -> Optional[pygame.Surface]:
    """Return scaled terrain icon surface, or ``None`` if not found."""
    return _shared_cache.terrain_sprite(terrain_id, size)


def get_unit_sprite(unit_class: str, size: int) -> Optional[pygame.Surface]:
    """Return scaled unit icon surface, or ``None`` if not found."""
    return _shared_cache.unit_sprite(unit_class, size)


def clear_cache() -> None:
    """Flush the shared sprite cache."""
    _shared_cache.clear()
