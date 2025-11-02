"""Tests for pitch detection and note segmentation."""
import numpy as np
import pytest

from mp3paramidi.audio import PitchDetector, PitchFrame
from tests.helpers import create_audio_data
from tests.fixtures.audio_generators import generate_sine_wave

# Test parameters
SAMPLE_RATE = 44100
DURATION = 0.5  # seconds
FREQ_A4 = 440.0
FREQ_C5 = 523.25
A4_MIDI = 69
C5_MIDI = 72


def test_detect_pitch_mono():
    """Test pitch detection on a mono sine wave."""
    # Create a mono sine wave
    audio_data = create_audio_data(
        samples=generate_sine_wave(FREQ_A4, DURATION, SAMPLE_RATE, channels=1),
        sample_rate=SAMPLE_RATE,
    )
    
    detector = PitchDetector()
    frames = detector.detect_pitch(audio_data)
    
    # Basic validation
    assert len(frames) > 0
    assert all(isinstance(f, PitchFrame) for f in frames)
    assert frames[0].time == 0
    assert frames[-1].time <= DURATION
    
    # Check that times are increasing
    times = [f.time for f in frames]
    assert all(t1 <= t2 for t1, t2 in zip(times, times[1:]))
    
    # Check that we have some voiced frames with reasonable frequencies
    voiced_frames = [f for f in frames if f.voiced and f.frequency is not None]
    assert len(voiced_frames) > 0
    
    # Check that frequencies are in a reasonable range for A4
    median_freq = np.median([f.frequency for f in voiced_frames])
    assert 430 <= median_freq <= 450  # Allow some tolerance


def test_detect_pitch_stereo():
    """Test pitch detection on a stereo signal."""
    # Create a stereo sine wave with slightly different amplitudes
    audio_data = create_audio_data(
        samples=generate_sine_wave(FREQ_A4, DURATION, SAMPLE_RATE, channels=2),
        sample_rate=SAMPLE_RATE,
    )
    
    detector = PitchDetector()
    frames = detector.detect_pitch(audio_data)
    
    # Basic validation
    assert len(frames) > 0
    voiced_frames = [f for f in frames if f.voiced and f.frequency is not None]
    assert len(voiced_frames) > 0
    
    # Check that frequencies are in a reasonable range for A4
    median_freq = np.median([f.frequency for f in voiced_frames])
    assert 430 <= median_freq <= 450  # Allow some tolerance


def test_segment_notes_basic():
    """Test basic note segmentation with a simple two-note sequence."""
    # Create a sequence with two notes: A4 then C5
    duration_per_note = 0.3
    t = np.linspace(0, duration_per_note * 2, int(SAMPLE_RATE * duration_per_note * 2), endpoint=False)
    
    # First note (A4)
    note1 = np.sin(2 * np.pi * FREQ_A4 * t[:int(SAMPLE_RATE * duration_per_note)])
    # Second note (C5)
    note2 = np.sin(2 * np.pi * FREQ_C5 * t[int(SAMPLE_RATE * duration_per_note):])
    
    # Combine and create audio data
    audio = np.concatenate([note1, note2])
    audio_data = create_audio_data(
        samples=audio.astype(np.float32),
        sample_rate=SAMPLE_RATE,
    )
    
    # Create mock pitch frames
    frames_per_note = 100
    times = np.linspace(0, duration_per_note * 2, frames_per_note * 2)
    
    # First note frames (A4)
    frames = []
    for i in range(frames_per_note):
        frames.append(PitchFrame(
            time=times[i],
            frequency=FREQ_A4,
            voiced=True,
            confidence=0.9
        ))
    
    # Second note frames (C5)
    for i in range(frames_per_note, frames_per_note * 2):
        frames.append(PitchFrame(
            time=times[i],
            frequency=FREQ_C5,
            voiced=True,
            confidence=0.9
        ))
    
    # Test segmentation
    detector = PitchDetector()
    notes = detector.segment_notes(frames, audio_data)
    
    # Should detect 2 notes
    assert len(notes) == 2
    
    # Check note properties
    note1, note2 = notes[0], notes[1]
    
    # First note (A4)
    assert abs(note1.pitch_hz - FREQ_A4) < 5  # Allow small tolerance
    assert note1.midi_note == A4_MIDI
    assert 0 <= note1.velocity <= 127
    assert 0 <= note1.start_time < note1.end_time <= duration_per_note * 2
    
    # Second note (C5)
    assert abs(note2.pitch_hz - FREQ_C5) < 5  # Allow small tolerance
    assert note2.midi_note == C5_MIDI
    assert 0 <= note2.velocity <= 127
    assert note2.start_time >= note1.end_time  # Should be after first note
    assert note2.end_time <= duration_per_note * 2


def test_segment_notes_min_duration():
    """Test that notes shorter than min_note_duration are filtered out."""
    # Create a very short note
    short_duration = 0.02  # 20ms (shorter than default min_note_duration of 50ms)
    t = np.linspace(0, short_duration, int(SAMPLE_RATE * short_duration), endpoint=False)
    audio = np.sin(2 * np.pi * FREQ_A4 * t)
    audio_data = create_audio_data(
        samples=audio.astype(np.float32),
        sample_rate=SAMPLE_RATE,
    )
    
    # Create pitch frames for the short note
    frames = [
        PitchFrame(time=0, frequency=FREQ_A4, voiced=True, confidence=0.9),
        PitchFrame(time=short_duration/2, frequency=FREQ_A4, voiced=True, confidence=0.9),
        PitchFrame(time=short_duration, frequency=0, voiced=False, confidence=0.1)
    ]
    
    # Test with default min_note_duration (50ms)
    detector = PitchDetector()
    notes = detector.segment_notes(frames, audio_data)
    assert len(notes) == 0  # Should be filtered out
    
    # Test with shorter min_note_duration
    notes = detector.segment_notes(frames, audio_data, min_note_duration=0.01)
    assert len(notes) == 1  # Should be included


def test_compute_velocity():
    """Test velocity computation based on audio amplitude."""
    # Create a loud and quiet segment
    duration = 0.1
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    
    # Loud segment (amplitude 0.8)
    loud_audio = 0.8 * np.sin(2 * np.pi * FREQ_A4 * t)
    # Quiet segment (amplitude 0.2)
    quiet_audio = 0.2 * np.sin(2 * np.pi * FREQ_A4 * t)
    
    # Combine into one audio signal
    audio = np.concatenate([loud_audio, quiet_audio])
    audio_data = create_audio_data(
        samples=audio.astype(np.float32),
        sample_rate=SAMPLE_RATE,
    )
    
    detector = PitchDetector()
    
    # Compute velocity for loud segment
    loud_vel = detector._compute_velocity(audio_data, 0, duration)
    # Compute velocity for quiet segment
    quiet_vel = detector._compute_velocity(audio_data, duration, 2*duration)
    
    # Loud segment should have higher velocity
    assert loud_vel > quiet_vel
    # Velocities should be in the expected range (40-110)
    assert 40 <= loud_vel <= 110
    assert 40 <= quiet_vel <= 110


def test_detect_pitch_silence():
    """Test pitch detection on silence returns unvoiced frames."""
    # Create silent audio
    silent_audio = np.zeros((1, int(SAMPLE_RATE * 0.1)))  # 100ms of silence
    audio_data = create_audio_data(
        samples=silent_audio.astype(np.float32),
        sample_rate=SAMPLE_RATE,
    )
    
    detector = PitchDetector()
    frames = detector.detect_pitch(audio_data)
    
    # Should have frames but they should be unvoiced
    assert len(frames) > 0
    assert all(not f.voiced for f in frames)
    assert all(f.frequency is None for f in frames)
