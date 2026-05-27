"""
Tests for CP-25: SoundManager.

All tests run headlessly with SDL_AUDIODRIVER=dummy so no real audio device
is needed.  We verify the public API contract (no crashes, correct state
transitions) without actually playing sound.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import pygame

# Headless audio via SDL dummy driver
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame.init()

from src.audio.sounds import SoundManager, SFX_DIR, MUSIC_DIR

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr():
    """Fresh SoundManager per test."""
    m = SoundManager()
    yield m
    m.quit()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestSoundManagerInit:
    def test_creates_without_crash(self, mgr):
        assert mgr is not None

    def test_not_muted_by_default(self, mgr):
        assert mgr.is_muted is False

    def test_default_volume_positive(self, mgr):
        assert 0.0 < mgr.master_volume <= 1.0

    def test_quit_is_idempotent(self, mgr):
        mgr.quit()
        mgr.quit()   # double-quit must not raise


# ---------------------------------------------------------------------------
# Volume & mute
# ---------------------------------------------------------------------------

class TestVolumeAndMute:
    def test_toggle_mute_flips_state(self, mgr):
        initial = mgr.is_muted
        mgr.toggle_mute()
        assert mgr.is_muted is not initial

    def test_toggle_twice_restores(self, mgr):
        initial = mgr.is_muted
        mgr.toggle_mute()
        mgr.toggle_mute()
        assert mgr.is_muted == initial

    def test_set_volume_clamps_above(self, mgr):
        mgr.set_volume(5.0)
        assert mgr.master_volume == 1.0

    def test_set_volume_clamps_below(self, mgr):
        mgr.set_volume(-3.0)
        assert mgr.master_volume == 0.0

    def test_set_volume_stores_value(self, mgr):
        mgr.set_volume(0.3)
        assert abs(mgr.master_volume - 0.3) < 1e-6


# ---------------------------------------------------------------------------
# SFX loading
# ---------------------------------------------------------------------------

class TestSFXLoading:
    def test_play_unknown_name_does_not_crash(self, mgr):
        mgr.play_sfx("nonexistent_sound_xyz")

    def test_play_when_muted_does_not_crash(self, mgr):
        mgr.toggle_mute()
        mgr.play_sfx("move")

    def test_play_all_sfx_names_no_crash(self, mgr):
        for name in ("move", "attack", "capture", "build", "end_turn", "win", "lose"):
            mgr.play_sfx(name)   # may or may not find the file — must not crash


# ---------------------------------------------------------------------------
# Generated SFX files exist
# ---------------------------------------------------------------------------

class TestGeneratedSFX:
    EXPECTED_SFX = ["move", "attack", "capture", "build", "end_turn", "win", "lose"]
    EXPECTED_MUSIC = ["NATO", "BRICS", "GUERILLA"]

    def test_sfx_files_exist(self):
        missing = [n for n in self.EXPECTED_SFX
                   if not (SFX_DIR / f"{n}.wav").exists()]
        assert not missing, f"Missing SFX files: {missing}"

    def test_music_files_exist(self):
        missing = [f for f in self.EXPECTED_MUSIC
                   if not (MUSIC_DIR / f"{f}.wav").exists()]
        assert not missing, f"Missing music files: {missing}"

    def test_sfx_are_valid_wav(self):
        import wave
        for name in self.EXPECTED_SFX:
            path = SFX_DIR / f"{name}.wav"
            with wave.open(str(path)) as wf:
                assert wf.getnframes() > 0, f"{name}.wav has no frames"
                assert wf.getsampwidth() == 2

    def test_music_are_valid_wav(self):
        import wave
        for faction in self.EXPECTED_MUSIC:
            path = MUSIC_DIR / f"{faction}.wav"
            with wave.open(str(path)) as wf:
                assert wf.getnframes() > 0, f"{faction}.wav has no frames"
                # Music should be at least 3 seconds
                dur = wf.getnframes() / wf.getframerate()
                assert dur >= 3.0, f"{faction}.wav is only {dur:.1f}s"

    def test_sfx_durations_sane(self):
        import wave
        for name in self.EXPECTED_SFX:
            path = SFX_DIR / f"{name}.wav"
            with wave.open(str(path)) as wf:
                dur = wf.getnframes() / wf.getframerate()
                assert 0.05 <= dur <= 3.0, f"{name}.wav duration {dur:.2f}s out of range"


# ---------------------------------------------------------------------------
# Music control
# ---------------------------------------------------------------------------

class TestMusicControl:
    def test_play_music_no_crash(self, mgr):
        mgr.play_music("NATO")

    def test_play_music_unknown_faction_no_crash(self, mgr):
        mgr.play_music("ATLANTIS")

    def test_stop_music_no_crash(self, mgr):
        mgr.play_music("BRICS")
        mgr.stop_music()

    def test_play_same_faction_twice_no_crash(self, mgr):
        mgr.play_music("GUERILLA")
        mgr.play_music("GUERILLA")   # should be a no-op, not crash


# ---------------------------------------------------------------------------
# Focus change
# ---------------------------------------------------------------------------

class TestFocusChange:
    def test_focus_gained_no_crash(self, mgr):
        mgr.handle_focus_change(gained=True)

    def test_focus_lost_no_crash(self, mgr):
        mgr.handle_focus_change(gained=False)

    def test_focus_cycle_no_crash(self, mgr):
        mgr.play_music("NATO")
        mgr.handle_focus_change(gained=False)
        mgr.handle_focus_change(gained=True)
