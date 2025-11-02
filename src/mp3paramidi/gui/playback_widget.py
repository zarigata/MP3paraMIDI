"""
Playback widget for MP3paraMIDI.

This module provides a playback control widget for MIDI preview
with play/pause/stop controls, volume, and position tracking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
)

from ..midi.playback import MidiPlayer, PlaybackState, PlaybackError


class PlaybackWidget(QWidget):
    """
    Playback control widget for MIDI preview.
    
    Provides play/pause/stop controls, volume slider, position tracking,
    and time display. Integrates with MidiPlayer for audio playback.
    """
    
    # Signals
    playback_requested = pyqtSignal(Path)
    playback_stopped = pyqtSignal()
    
    def __init__(self, parent=None):
        """
        Initialize playback widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.midi_player: Optional[MidiPlayer] = None
        self.current_midi_path: Optional[Path] = None
        self.total_duration: float = 0.0  # Could be estimated from MIDI
        
        self._setup_ui()
        self._connect_signals()
        
        # Initially disable controls until MIDI is loaded
        self.set_enabled(False)
    
    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # File info
        self.file_label = QLabel("No MIDI file loaded")
        self.file_label.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(self.file_label)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        
        # Play/Pause button
        self.play_pause_button = QPushButton("▶️ Play")
        self.play_pause_button.setMinimumWidth(80)
        controls_layout.addWidget(self.play_pause_button)
        
        # Stop button
        self.stop_button = QPushButton("⏹️ Stop")
        self.stop_button.setMinimumWidth(80)
        controls_layout.addWidget(self.stop_button)
        
        # Volume control
        controls_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(100)
        controls_layout.addWidget(self.volume_slider)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Position controls
        position_layout = QVBoxLayout()
        
        # Position slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)  # 0-1000 for percentage
        self.position_slider.setValue(0)
        position_layout.addWidget(self.position_slider)
        
        # Time label
        time_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-family: monospace;")
        time_layout.addStretch()
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        position_layout.addLayout(time_layout)
        
        layout.addLayout(position_layout)
    
    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.play_pause_button.clicked.connect(self._on_play_pause_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.position_slider.sliderPressed.connect(self._on_position_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_position_slider_released)
    
    def load_midi(self, midi_path: Path) -> None:
        """
        Load a MIDI file for playback.
        
        Args:
            midi_path: Path to MIDI file
        """
        try:
            # Create MIDI player if needed
            if self.midi_player is None:
                self.midi_player = MidiPlayer()
                self._connect_player_signals()
            
            # Load the MIDI file
            self.midi_player.load_midi(midi_path)
            self.current_midi_path = midi_path
            
            # Update UI
            self.file_label.setText(f"📄 {midi_path.name}")
            self.set_enabled(True)
            self._update_ui_for_state(PlaybackState.STOPPED)
            
            # Reset position
            self.position_slider.setValue(0)
            self.time_label.setText("00:00 / 00:00")
            
        except PlaybackError as e:
            self._show_error(f"Failed to load MIDI file: {e}")
    
    def _connect_player_signals(self) -> None:
        """Connect signals from the MIDI player."""
        if self.midi_player:
            self.midi_player.state_changed.connect(self._on_state_changed)
            self.midi_player.position_changed.connect(self._update_position)
            self.midi_player.playback_finished.connect(self._on_playback_finished)
            self.midi_player.error_occurred.connect(self._on_error)
    
    def _on_play_pause_clicked(self) -> None:
        """Handle play/pause button click."""
        if not self.midi_player:
            return
            
        try:
            if self.midi_player.state == PlaybackState.PLAYING:
                self.midi_player.pause()
            else:
                self.midi_player.play()
        except PlaybackError as e:
            self._show_error(f"Playback error: {e}")
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self.midi_player:
            self.midi_player.stop()
    
    def _on_volume_changed(self, value: int) -> None:
        """
        Handle volume slider change.
        
        Args:
            value: Volume value (0-100)
        """
        if self.midi_player:
            volume = value / 100.0
            self.midi_player.set_volume(volume)
    
    def _on_position_slider_pressed(self) -> None:
        """Handle position slider press (disable position updates)."""
        # Disable automatic position updates while user is dragging
        self._user_seeking = True
    
    def _on_position_slider_released(self) -> None:
        """Handle position slider release (seek to position)."""
        if self.midi_player and hasattr(self, '_user_seeking'):
            # Calculate position from slider percentage
            percentage = self.position_slider.value() / 1000.0
            # Note: Seeking may not work with MIDI playback in pygame
            # This is a limitation of pygame.mixer.music
            delattr(self, '_user_seeking')
    
    @pyqtSlot(PlaybackState)
    def _on_state_changed(self, state: PlaybackState) -> None:
        """
        Handle playback state change.
        
        Args:
            state: New playback state
        """
        self._update_ui_for_state(state)
    
    @pyqtSlot(float)
    def _update_position(self, position: float) -> None:
        """
        Update position display during playback.
        
        Args:
            position: Current position in seconds
        """
        if hasattr(self, '_user_seeking'):
            return  # Don't update while user is seeking
            
        # Update position slider (as percentage if we don't know total duration)
        if self.total_duration > 0:
            percentage = (position / self.total_duration) * 1000
            self.position_slider.setValue(int(percentage))
        else:
            # If we don't know duration, just show progress
            # Use a reasonable maximum for display
            max_display = 300  # 5 minutes
            percentage = min((position / max_display) * 1000, 1000)
            self.position_slider.setValue(int(percentage))
        
        # Update time label
        current_str = self._format_time(position)
        total_str = self._format_time(self.total_duration) if self.total_duration > 0 else "??:??"
        self.time_label.setText(f"{current_str} / {total_str}")
    
    @pyqtSlot()
    def _on_playback_finished(self) -> None:
        """Handle playback completion."""
        self._update_ui_for_state(PlaybackState.STOPPED)
        self.position_slider.setValue(0)
        self.time_label.setText("00:00 / 00:00")
    
    @pyqtSlot(str)
    def _on_error(self, error_msg: str) -> None:
        """
        Handle playback error.
        
        Args:
            error_msg: Error message
        """
        self._show_error(error_msg)
        self._update_ui_for_state(PlaybackState.STOPPED)
    
    def _update_ui_for_state(self, state: PlaybackState) -> None:
        """
        Update UI elements based on playback state.
        
        Args:
            state: Current playback state
        """
        if state == PlaybackState.PLAYING:
            self.play_pause_button.setText("⏸️ Pause")
        elif state == PlaybackState.PAUSED:
            self.play_pause_button.setText("▶️ Resume")
        else:  # STOPPED
            self.play_pause_button.setText("▶️ Play")
    
    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable all playback controls.
        
        Args:
            enabled: True to enable controls, False to disable
        """
        self.play_pause_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.volume_slider.setEnabled(enabled)
        self.position_slider.setEnabled(enabled)
    
    def cleanup(self) -> None:
        """Clean up resources and stop playback."""
        if self.midi_player:
            self.midi_player.cleanup()
            self.midi_player = None
    
    def _format_time(self, seconds: float) -> str:
        """
        Format time in seconds as MM:SS string.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        if seconds < 0:
            return "00:00"
            
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _show_error(self, message: str) -> None:
        """
        Show error message to user.
        
        Args:
            message: Error message to display
        """
        from PyQt6.QtWidgets import QMessageBox
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Playback Error")
        msg_box.setText(message)
        msg_box.exec()
