"""
Tempo and beat detection module for MP3paraMIDI.

This module provides tempo detection using librosa's beat tracking algorithms
to estimate BPM and beat positions in audio data.
"""

from __future__ import annotations

import logging
import numpy as np
import librosa
from dataclasses import dataclass
from typing import Tuple

from .loader import AudioData


@dataclass
class TempoInfo:
    """Information about detected tempo and beats."""
    tempo: float                    # BPM
    beat_times: np.ndarray          # Beat positions in seconds
    confidence: float               # 0-1 confidence score
    time_signature: Tuple[int, int] = (4, 4)  # Default to 4/4
    is_constant_tempo: bool = True  # Whether tempo is constant


class TempoDetector:
    """
    Tempo detector using librosa beat tracking algorithms.
    
    Detects tempo, beat positions, and provides confidence scoring.
    Note: Time signature detection is not supported - defaults to 4/4.
    """
    
    def __init__(self, aggregate_tempo: bool = True, start_bpm: float = 120.0):
        """
        Initialize tempo detector.
        
        Args:
            aggregate_tempo: If True, return single BPM (mean/median)
            start_bpm: Initial BPM estimate for beat tracking
        """
        self.aggregate_tempo = aggregate_tempo
        self.start_bpm = start_bpm
        self.logger = logging.getLogger(__name__)
    
    def detect_tempo(self, audio_data: AudioData) -> TempoInfo:
        """
        Detect tempo and beats from audio data.
        
        Args:
            audio_data: AudioData object containing audio signal
            
        Returns:
            TempoInfo with detected tempo, beats, and confidence
        """
        # Convert to mono if needed
        if audio_data.data.ndim > 1:
            y = librosa.to_mono(audio_data.data.T)
        else:
            y = audio_data.data
            
        sr = audio_data.sample_rate
        
        # Use librosa beat tracking
        tempo, beat_times = librosa.beat.beat_track(
            y=y,
            sr=sr,
            units='time',
            start_bpm=self.start_bpm
        )
        
        # Handle tempo array (librosa 0.11.0+ returns array)
        if isinstance(tempo, np.ndarray):
            if self.aggregate_tempo:
                # Use median for robustness
                tempo_value = float(np.median(tempo))
            else:
                tempo_value = float(tempo[0])  # Use first estimate
        else:
            tempo_value = float(tempo)
            
        
        # Estimate confidence based on beat regularity
        confidence = self._estimate_confidence(beat_times)
        
        self.logger.info(
            f"Detected tempo: {tempo_value:.1f} BPM, "
            f"beats: {len(beat_times)}, confidence: {confidence:.2f}"
        )
        
        return TempoInfo(
            tempo=tempo_value,
            beat_times=beat_times,
            confidence=confidence,
            time_signature=(4, 4),  # Default - librosa doesn't detect this
            is_constant_tempo=self.aggregate_tempo
        )
    
    def detect_time_varying_tempo(self, audio_data: AudioData) -> TempoInfo:
        """
        Detect time-varying tempo using dynamic tempo tracking.
        
        Args:
            audio_data: AudioData object
            
        Returns:
            TempoInfo with dynamic tempo estimates
        """
        # Convert to mono if needed
        if audio_data.data.ndim > 1:
            y = librosa.to_mono(audio_data.data.T)
        else:
            y = audio_data.data
            
        sr = audio_data.sample_rate
        
        # Use dynamic tempo tracking
        tempo = librosa.feature.tempo(
            y=y, 
            sr=sr, 
            aggregate=None,  # Don't aggregate
            start_bpm=self.start_bpm
        )
        
        # Get beats for the first tempo estimate
        _, beat_times = librosa.beat.beat_track(
            y=y,
            sr=sr,
            units='time',
            start_bpm=self.start_bpm
        )
        
        # Use mean tempo as representative value
        tempo_value = float(np.mean(tempo))
        confidence = self._estimate_confidence(beat_times)
        
        return TempoInfo(
            tempo=tempo_value,
            beat_times=beat_times,
            confidence=confidence,
            time_signature=(4, 4),
            is_constant_tempo=False
        )
    
    def get_tempo_curve(self, audio_data: AudioData, hop_length: int = 512) -> np.ndarray:
        """
        Get frame-by-frame tempo estimates for visualization.
        
        Args:
            audio_data: AudioData object
            hop_length: Hop length for analysis frames
            
        Returns:
            Array of tempo estimates per frame
        """
        # Convert to mono if needed
        if audio_data.data.ndim > 1:
            y = librosa.to_mono(audio_data.data.T)
        else:
            y = audio_data.data
            
        sr = audio_data.sample_rate
        
        # Get dynamic tempo estimates
        tempo_curve = librosa.feature.tempo(
            y=y, 
            sr=sr, 
            aggregate=None,
            hop_length=hop_length,
            start_bpm=self.start_bpm
        )
        
        return tempo_curve.flatten()
    
    def _estimate_confidence(self, beat_times: np.ndarray) -> float:
        """
        Estimate confidence based on beat regularity.
        
        Args:
            beat_times: Array of beat times in seconds
            
        Returns:
            Confidence score between 0 and 1
        """
        if len(beat_times) < 2:
            return 0.0
            
        # Calculate inter-beat intervals
        intervals = np.diff(beat_times)
        
        if len(intervals) == 0:
            return 0.0
            
        # Calculate coefficient of variation (lower = more regular = higher confidence)
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        
        if mean_interval == 0:
            return 0.0
            
        cv = std_interval / mean_interval
        
        # Convert to confidence (0-1 scale, inverted)
        confidence = max(0.0, 1.0 - cv)
        
        # Apply some smoothing - very low confidence for highly irregular beats
        if confidence < 0.3:
            confidence *= 0.5
            
        return float(np.clip(confidence, 0.0, 1.0))
