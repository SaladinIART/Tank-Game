"""
Audio manager for Modern Warfare 4X.

Responsibilities
----------------
- Load and play short SFX clips from ``assets/sfx/<name>.wav``.
- Loop faction-themed background music from ``assets/music/<faction_id>.wav``.
- Expose master volume (0.0–1.0) and a mute toggle.
- Gracefully handle any missing files or uninitialised mixer — all public
  methods are safe to call even when audio isn't available.
- Provide a ``handle_focus_change(gained)`` hook so the main loop can pause /
  resume music when the window loses / regains focus (eliminates tab-switch
  audio glitches on some platforms).

Usage
-----
::

    mgr = SoundManager()          # call once at startup
    mgr.play_sfx("attack")        # fire-and-forget
    mgr.play_music("NATO")        # loops until stopped or faction changes
    mgr.toggle_mute()             # M key handler
    mgr.set_volume(0.4)           # 0.0 … 1.0

SFX names recognised
--------------------
``"move"``       — unit moves to a new hex
``"attack"``     — an attack is resolved
``"capture"``    — tile ownership flips
``"build"``      — unit produced at HQ
``"end_turn"``   — end-turn action
``"win"``        — player victory
``"lose"``       — player defeat

Any unrecognised name is silently ignored (no crash).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pygame

SFX_DIR   = Path("assets/sfx")
MUSIC_DIR = Path("assets/music")

# Channels (pygame.mixer.Channel indices)
_CH_SFX   = 0   # re-used for every short clip (fine for non-overlapping sfx)
_CH_WIN   = 1   # dedicated channel so win/lose don't overlap regular sfx

# Default volumes
_DEFAULT_MASTER   = 0.70
_DEFAULT_MUSIC    = 0.45
_DEFAULT_SFX      = 0.80


class SoundManager:
    """Manages all game audio.

    Instantiate once and keep alive for the lifetime of the application.
    If pygame.mixer cannot be initialised (headless, no audio device, etc.)
    the object is created in *silent mode* and every call becomes a no-op.
    """

    def __init__(self) -> None:
        self._ready          = False
        self._muted          = False
        self._master_vol     = _DEFAULT_MASTER
        self._music_vol      = _DEFAULT_MUSIC
        self._sfx_vol        = _DEFAULT_SFX
        self._current_faction: Optional[str] = None

        # Cache of loaded Sound objects keyed by sfx name
        self._sfx: dict[str, Optional[pygame.mixer.Sound]] = {}

        self._init_mixer()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_mixer(self) -> None:
        if not pygame.get_init():
            pygame.init()
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=1024)
            pygame.mixer.set_num_channels(4)
            self._ready = True
        except pygame.error:
            self._ready = False  # silent mode

    # ------------------------------------------------------------------
    # SFX
    # ------------------------------------------------------------------

    def _load_sfx(self, name: str) -> Optional[pygame.mixer.Sound]:
        """Load (or return cached) a Sound object, or None if absent."""
        if name not in self._sfx:
            path = SFX_DIR / f"{name}.wav"
            if path.is_file():
                try:
                    self._sfx[name] = pygame.mixer.Sound(str(path))
                except pygame.error:
                    self._sfx[name] = None
            else:
                self._sfx[name] = None
        return self._sfx[name]

    def play_sfx(self, name: str) -> None:
        """Play a sound effect.  Silent if mixer not ready, muted, or file missing."""
        if not self._ready or self._muted:
            return
        snd = self._load_sfx(name)
        if snd is None:
            return
        vol = self._sfx_vol * self._master_vol
        snd.set_volume(vol)
        # Win/lose use a dedicated channel so they can't be cut off by rapid sfx.
        if name in ("win", "lose"):
            ch = pygame.mixer.Channel(_CH_WIN)
            ch.play(snd)
        else:
            ch = pygame.mixer.Channel(_CH_SFX)
            ch.play(snd)

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    def play_music(self, faction_id: str) -> None:
        """Start looping the faction's background track.

        If the same faction is already playing, this is a no-op (avoids restart
        on every turn-start).
        """
        if not self._ready:
            return
        if faction_id == self._current_faction:
            return
        path = MUSIC_DIR / f"{faction_id}.wav"
        if not path.is_file():
            # Try lowercase variant (GUERILLA → guerilla)
            path = MUSIC_DIR / f"{faction_id.lower()}.wav"
        if not path.is_file():
            return
        try:
            pygame.mixer.music.load(str(path))
            vol = (0.0 if self._muted else self._music_vol * self._master_vol)
            pygame.mixer.music.set_volume(vol)
            pygame.mixer.music.play(-1)   # -1 = loop indefinitely
            self._current_faction = faction_id
        except pygame.error:
            pass

    def stop_music(self) -> None:
        """Halt any playing music track."""
        if not self._ready:
            return
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self._current_faction = None

    # ------------------------------------------------------------------
    # Volume / mute
    # ------------------------------------------------------------------

    def set_volume(self, master: float) -> None:
        """Set master volume in [0.0, 1.0]."""
        self._master_vol = max(0.0, min(1.0, master))
        self._apply_volume()

    def toggle_mute(self) -> None:
        """Toggle global mute."""
        self._muted = not self._muted
        self._apply_volume()

    @property
    def is_muted(self) -> bool:
        return self._muted

    @property
    def master_volume(self) -> float:
        return self._master_vol

    def _apply_volume(self) -> None:
        if not self._ready:
            return
        try:
            music_vol = 0.0 if self._muted else self._music_vol * self._master_vol
            pygame.mixer.music.set_volume(music_vol)
        except pygame.error:
            pass

    # ------------------------------------------------------------------
    # Focus change (tab-switch glitch prevention)
    # ------------------------------------------------------------------

    def handle_focus_change(self, gained: bool) -> None:
        """Pause music when window loses focus; resume when it regains it.

        Call from the main event loop on ``pygame.ACTIVEEVENT``.
        """
        if not self._ready:
            return
        try:
            if gained:
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.pause()
        except pygame.error:
            pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def quit(self) -> None:
        """Release mixer resources."""
        if self._ready:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except pygame.error:
                pass
            self._ready = False
