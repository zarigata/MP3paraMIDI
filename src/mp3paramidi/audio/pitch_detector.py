"""
Pitch detection and note segmentation for monophonic audio signals.

This module provides functionality to detect pitch and segment audio into musical notes
using the pYIN algorithm from librosa. It handles both pitch detection and note segmentation
with configurable parameters for different use cases.
"""
from __future__ import annotations

import numpy as np
import librosa
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy.typing as npt


@dataclass
class PitchFrame:
    """Represents pitch information for a single audio frame.
    
    Attributes:
        time: Time in seconds from the start of the audio.
        frequency: Detected frequency in Hz, or None if unvoiced.
        voiced: Boolean indicating if the frame contains a voiced signal.
        confidence: Confidence score between 0 and 1, where 1 is most confident.
    """
    time: float
    frequency: Optional[float]
    voiced: bool
    confidence: float


@dataclass
class NoteEvent:
    """Represents a detected musical note event.
    
    Attributes:
        start_time: Start time of the note in seconds.
        end_time: End time of the note in seconds.
        pitch_hz: Fundamental frequency of the note in Hz.
        midi_note: MIDI note number (0-127).
        velocity: Note velocity (1-127).
        confidence: Average confidence of pitch detection (0-1).
    """
    start_time: float
    end_time: float
    pitch_hz: float
    midi_note: int
    velocity: int
    confidence: float


class PitchDetector:
    """Detects pitch and segments audio into musical notes.
    
    Uses the pYIN algorithm for robust monophonic pitch detection and provides
    methods for segmenting the pitch contour into discrete notes.
    
    Args:
        fmin: Minimum detectable frequency in Hz or note name (e.g., 'C2').
        fmax: Maximum detectable frequency in Hz or note name (e.g., 'C7').
        hop_length: Number of samples between successive frames.
        frame_length: Number of samples in each analysis frame.
    """
    
    def __init__(
        self,
        fmin: float | str = 'C2',
        fmax: float | str = 'C7',
        hop_length: int = 512,
        frame_length: int = 2048
    ) -> None:
        self.hop_length = hop_length
        self.frame_length = frame_length
        
        # Convert note names to frequencies if needed
        if isinstance(fmin, str):
            self.fmin = librosa.note_to_hz(fmin)
        else:
            self.fmin = fmin
            
        if isinstance(fmax, str):
            self.fmax = librosa.note_to_hz(fmax)
        else:
            self.fmax = fmax
    
    def detect_pitch(self, audio_data: 'AudioData') -> List[PitchFrame]:
        """Detect pitch in the given audio data.
        
        Args:
            audio_data: Audio data to analyze.
            
        Returns:
            List of PitchFrame objects containing pitch information for each frame.
            
        Raises:
            ValueError: If audio data is empty or invalid.
        """
        if not audio_data.samples.size:
            raise ValueError("Audio data is empty")
        
        # Convert to mono if needed
        if len(audio_data.samples.shape) > 1:
            y = librosa.to_mono(audio_data.samples)
        else:
            y = audio_data.samples
        
        # Detect pitch using pYIN algorithm
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y=y,
            fmin=self.fmin,
            fmax=self.fmax,
            sr=audio_data.sample_rate,
            hop_length=self.hop_length,
            frame_length=self.frame_length
        )
        
        # Convert frame indices to times
        times = librosa.frames_to_time(
            frames=range(len(f0)),
            sr=audio_data.sample_rate,
            hop_length=self.hop_length
        )
        
        # Create PitchFrame objects
        frames = []
        for i, (t, freq, voiced, prob) in enumerate(zip(times, f0, voiced_flag, voiced_probs)):
            frames.append(PitchFrame(
                time=t,
                frequency=float(freq) if not np.isnan(freq) and voiced else None,
                voiced=bool(voiced),
                confidence=float(prob) if not np.isnan(prob) else 0.0
            ))
        
        return frames
    
    def segment_notes(
        self,
        pitch_frames: List[PitchFrame],
        audio_data: 'AudioData',
        min_note_duration: float = 0.05
    ) -> List[NoteEvent]:
        """Segment pitch frames into discrete note events.
        
        Args:
            pitch_frames: List of PitchFrame objects from detect_pitch().
            audio_data: Original audio data for computing note velocities.
            min_note_duration: Minimum duration in seconds for a note to be included.
            
        Returns:
            List of NoteEvent objects representing the detected notes.
        """
        if not pitch_frames:
            return []
        
        # Convert audio to mono for RMS calculation
        if len(audio_data.samples.shape) > 1:
            y = librosa.to_mono(audio_data.samples)
        else:
            y = audio_data.samples
        
        # Extract times and frequencies
        times = np.array([f.time for f in pitch_frames])
        freqs = np.array([f.frequency if f.voiced and f.frequency is not None else np.nan 
                         for f in pitch_frames])
        confidences = np.array([f.confidence for f in pitch_frames])
        
        # Detect note onsets
        onset_frames = librosa.onset.onset_detect(
            y=y,
            sr=audio_data.sample_rate,
            hop_length=self.hop_length,
            backtrack=True
        )
        
        # Convert onset frames to times
        onset_times = librosa.frames_to_time(
            onset_frames,
            sr=audio_data.sample_rate,
            hop_length=self.hop_length
        )
        
        # Ensure we have at least the start time
        if not onset_times.size or onset_times[0] > times[0]:
            onset_times = np.insert(onset_times, 0, times[0])
            
        # Calculate the actual audio duration
        audio_duration = len(audio_data.samples) / audio_data.sample_rate
        
        # Ensure the last note extends to the end of the audio
        if onset_times[-1] < audio_duration - 0.01:  # Small threshold to avoid floating point issues
            onset_times = np.append(onset_times, audio_duration)
        
        note_events = []
        
        # Process each note segment
        for i in range(len(onset_times) - 1):
            start_time = onset_times[i]
            end_time = onset_times[i + 1]
            
            # For the last segment, ensure it extends to the end of the audio
            if i == len(onset_times) - 2:  # Last segment
                end_time = max(end_time, audio_duration)
                
            # Skip if too short (except for the last note which we want to keep)
            if end_time - start_time < min_note_duration and i < len(onset_times) - 2:
                continue
            
            # Find frames within this segment
            mask = (times >= start_time) & (times < end_time)
            segment_freqs = freqs[mask]
            segment_confidences = confidences[mask]
            
            # Skip if no voiced frames
            voiced_mask = ~np.isnan(segment_freqs)
            if not np.any(voiced_mask):
                continue
            
            # Compute median frequency (more robust than mean for pitch)
            median_freq = np.nanmedian(segment_freqs)
            
            # Convert to MIDI note
            midi_note = int(round(librosa.hz_to_midi(median_freq)))
            midi_note = max(0, min(127, midi_note))  # Clamp to valid range
            
            # Compute average confidence
            avg_confidence = float(np.nanmean(segment_confidences[voiced_mask]))
            
            # Compute velocity using the helper method
            velocity = self._compute_velocity(audio_data, start_time, end_time)
            
            # Create note event
            note_events.append(NoteEvent(
                start_time=start_time,
                end_time=end_time,
                pitch_hz=median_freq,
                midi_note=midi_note,
                velocity=velocity,
                confidence=avg_confidence
            ))
        
        return note_events
    
    def _compute_velocity(
        self,
        audio_data: 'AudioData',
        start_time: float,
        end_time: float,
        onset_weight: float = 0.7
    ) -> int:
        """Compute velocity for a note based on enhanced RMS energy analysis.
        
        This method calculates the velocity (loudness) of a note segment using an
        improved approach that focuses on the attack portion for better perceived
        loudness correlation. Uses librosa.feature.rms() with proper frame length
        and applies perceptual weighting for better dynamic range distribution.
        
        Args:
            audio_data: Audio data containing the samples.
            start_time: Start time of the note in seconds.
            end_time: End time of the note in seconds.
            onset_weight: Weight for onset vs sustain portions (0.0-1.0).
            
        Returns:
            Velocity value between 40 and 110 (inclusive).
            Returns 64 (mezzo-forte) if the segment is invalid or empty.
        """
        # Convert to mono if needed
        if len(audio_data.samples.shape) > 1:
            y = librosa.to_mono(audio_data.samples)
        else:
            y = audio_data.samples
        
        # Convert times to sample indices
        start_sample = int(start_time * audio_data.sample_rate)
        end_sample = int(end_time * audio_data.sample_rate)
        
        # Ensure indices are within bounds
        start_sample = max(0, min(start_sample, len(y) - 1))
        end_sample = max(start_sample + 1, min(end_sample, len(y)))
        
        # Extract segment
        segment = y[start_sample:end_sample]
        
        # Default to mezzo-forte if segment is invalid
        if len(segment) == 0:
            return 64
        
        # Get onset segment (first 30ms for attack analysis)
        onset_segment = self._get_onset_segment(segment, audio_data.sample_rate)
        
        # Use librosa.feature.rms for proper RMS calculation
        frame_length = min(2048, len(segment))
        hop_length = frame_length // 4
        
        try:
            # Compute RMS for the entire segment
            rms_full = librosa.feature.rms(
                y=segment, 
                frame_length=frame_length, 
                hop_length=hop_length
            )[0]
            
            # Compute RMS for onset segment if available
            if len(onset_segment) > 0:
                rms_onset = librosa.feature.rms(
                    y=onset_segment,
                    frame_length=min(512, len(onset_segment)),
                    hop_length=min(128, len(onset_segment) // 4)
                )[0]
                onset_rms = np.mean(rms_onset) if len(rms_onset) > 0 else 0
            else:
                onset_rms = 0
            
            # Weighted combination of onset and sustain
            sustain_rms = np.mean(rms_full) if len(rms_full) > 0 else 0
            weighted_rms = onset_weight * onset_rms + (1 - onset_weight) * sustain_rms
            
        except Exception:
            # Fallback to simple RMS calculation
            weighted_rms = np.sqrt(np.mean(np.square(segment.astype(np.float64))))
        
        # Apply perceptual weighting (A-weighting approximation)
        # This better matches human loudness perception
        try:
            # Simple high-frequency emphasis for perceptual weighting
            if weighted_rms > 0:
                # Apply gentle compression to avoid extreme values
                compressed_rms = np.tanh(weighted_rms * 2.0) * 0.5
                
                # Map to velocity with improved musical curve
                velocity = int(np.clip(40 + 70 * (compressed_rms ** 0.4), 40, 110))
            else:
                velocity = 40  # Minimum velocity
        except Exception:
            # Fallback velocity calculation
            velocity = int(np.clip(40 + 70 * (weighted_rms ** 0.5), 40, 110))
        
        return velocity
    
    def _get_onset_segment(self, segment: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Extract the onset (attack) portion of a note segment.
        
        Args:
            segment: Audio segment to extract onset from
            sample_rate: Sample rate of the audio
            
        Returns:
            Onset segment (first 30ms or entire segment if shorter)
        """
        # Extract first 30ms for onset analysis
        onset_samples = int(0.03 * sample_rate)  # 30ms in samples
        
        if len(segment) <= onset_samples:
            return segment
        else:
            return segment[:onset_samples]
