"""
MIDI playback module for MP3paraMIDI.

This module provides MIDI playback functionality using pygame.mixer
with support for play/pause/stop controls and position tracking.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Optional

import pygame
from PyQt6.QtCore import QObject, pyqtSignal


class PlaybackState(Enum):
    """Playback state enumeration."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class PlaybackError(Exception):
    """Exception raised for playback-related errors."""
    pass


class MidiPlayer(QObject):
    """
    MIDI player using pygame.mixer for audio playback.
    
    Provides non-blocking playback controls with Qt signals for state updates.
    Note: SoundFont may be required on Linux/macOS for MIDI playback.
    """
    
    # Signals
    state_changed = pyqtSignal(PlaybackState)
    position_changed = pyqtSignal(float)  # Position in seconds
    playback_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, soundfont_path: Optional[Path] = None):
        """
        Initialize MIDI player.
        
        Args:
            soundfont_path: Optional path to SoundFont file (Linux/macOS)
            
        Raises:
            PlaybackError: If pygame.mixer initialization fails
        """
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.soundfont_path = soundfont_path
        self.current_file: Optional[Path] = None
        self.state = PlaybackState.STOPPED
        self._position_thread: Optional[threading.Thread] = None
        self._stop_position_thread = False
        
        try:
            # Initialize pygame.mixer
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            
            # Set SoundFont if provided (Linux/macOS only)
            if soundfont_path and soundfont_path.exists():
                try:
                    pygame.mixer.music.set_soundfont(str(soundfont_path))
                    self.logger.info(f"Loaded SoundFont: {soundfont_path}")
                except AttributeError:
                    # set_soundfont not available on all platforms
                    self.logger.debug("SoundFont setting not supported on this platform")
                    
        except pygame.error as e:
            raise PlaybackError(f"Failed to initialize pygame.mixer: {e}")
    
    def load_midi(self, midi_path: Path) -> None:
        """
        Load a MIDI file for playback.
        
        Args:
            midi_path: Path to MIDI file
            
        Raises:
            PlaybackError: If file loading fails
        """
        if not midi_path.exists():
            raise PlaybackError(f"MIDI file not found: {midi_path}")
        
        if not midi_path.suffix.lower() in ['.mid', '.midi']:
            raise PlaybackError(f"Invalid MIDI file extension: {midi_path.suffix}")
        
        try:
            pygame.mixer.music.load(str(midi_path))
            self.current_file = midi_path
            self.logger.info(f"Loaded MIDI file: {midi_path}")
        except pygame.error as e:
            raise PlaybackError(f"Failed to load MIDI file: {e}")
    
    def play(self) -> None:
        """
        Start or resume playback.
        
        Raises:
            PlaybackError: If no file is loaded or playback fails
        """
        if not self.current_file:
            raise PlaybackError("No MIDI file loaded")
        
        if self.state == PlaybackState.PAUSED:
            pygame.mixer.music.unpause()
        else:
            pygame.mixer.music.play()
        
        self.state = PlaybackState.PLAYING
        self.state_changed.emit(self.state)
        
        # Start position tracking thread
        self._start_position_tracking()
        
        self.logger.info("Started MIDI playback")
    
    def pause(self) -> None:
        """Pause playback."""
        if self.state == PlaybackState.PLAYING:
            pygame.mixer.music.pause()
            self.state = PlaybackState.PAUSED
            self.state_changed.emit(self.state)
            self._stop_position_thread = True
            self.logger.info("Paused MIDI playback")
    
    def stop(self) -> None:
        """Stop playback and reset position."""
        pygame.mixer.music.stop()
        self.state = PlaybackState.STOPPED
        self.state_changed.emit(self.state)
        self._stop_position_thread = True
        self.position_changed.emit(0.0)
        self.logger.info("Stopped MIDI playback")
    
    def is_playing(self) -> bool:
        """
        Check if playback is currently active.
        
        Returns:
            True if playing, False otherwise
        """
        return pygame.mixer.music.get_busy() and self.state == PlaybackState.PLAYING
    
    def get_position(self) -> float:
        """
        Get current playback position in seconds.
        
        Returns:
            Current position in seconds
        """
        # pygame.mixer.music.get_pos() returns milliseconds since playback started
        pos_ms = pygame.mixer.music.get_pos()
        if pos_ms == -1:
            return 0.0
        return pos_ms / 1000.0
    
    def set_volume(self, volume: float) -> None:
        """
        Set playback volume.
        
        Args:
            volume: Volume level between 0.0 and 1.0
        """
        volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(volume)
    
    def _start_position_tracking(self) -> None:
        """Start the position tracking thread."""
        self._stop_position_thread = False
        
        if self._position_thread and self._position_thread.is_alive():
            return  # Thread already running
        
        self._position_thread = threading.Thread(target=self._position_tracking_loop, daemon=True)
        self._position_thread.start()
    
    def _position_tracking_loop(self) -> None:
        """Background thread for tracking playback position."""
        while not self._stop_position_thread and self.state == PlaybackState.PLAYING:
            if self.is_playing():
                position = self.get_position()
                self.position_changed.emit(position)
                
                # Check if playback finished
                if not pygame.mixer.music.get_busy():
                    self.state = PlaybackState.STOPPED
                    self.state_changed.emit(self.state)
                    self.playback_finished.emit()
                    break
            
            time.sleep(0.1)  # Update every 100ms
    
    def cleanup(self) -> None:
        """Clean up resources and stop playback."""
        self.stop()
        pygame.mixer.quit()
        self.logger.info("Cleaned up MIDI player")
    
    @classmethod
    def check_midi_support(cls) -> bool:
        """
        Check if MIDI playback is supported.
        
        Returns:
            True if MIDI playback is supported
        """
        try:
            pygame.mixer.init()
            pygame.mixer.quit()
            return True
        except pygame.error:
            return False
    
    @classmethod
    def find_soundfont(cls) -> Optional[Path]:
        """
        Search for SoundFont files in common locations.
        
        Returns:
            Path to SoundFont file if found, None otherwise
        """
        common_paths = [
            Path("/usr/share/sounds/sf2"),
            Path("/usr/share/soundfonts"),
            Path("~/.local/share/sounds/sf2").expanduser(),
            Path("~/.local/share/soundfonts").expanduser(),
        ]
        
        sf2_files = ["FluidR3_GM.sf2", "default.sf2", "TimGM6mb.sf2"]
        
        for base_path in common_paths:
            if not base_path.exists():
                continue
                
            for sf2_file in sf2_files:
                sf2_path = base_path / sf2_file
                if sf2_path.exists():
                    return sf2_path
        
        return None
