"""
Tests for the tempo detection module.
"""
import pytest
import numpy as np
from pathlib import Path

from mp3paramidi.audio.tempo_detector import TempoDetector, TempoInfo
from mp3paramidi.audio.loader import AudioData, AudioMetadata


class TestTempoDetector:
    """Test the TempoDetector class."""
    
    @pytest.fixture
    def tempo_detector(self) -> TempoDetector:
        """Create a TempoDetector instance for testing."""
        return TempoDetector()
    
    @pytest.fixture
    def sample_audio_data(self) -> AudioData:
        """Create sample audio data for testing."""
        # Generate a simple sine wave at 440 Hz
        sample_rate = 22050
        duration = 4.0  # 4 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Create a signal with clear beat pattern (amplitude modulation)
        # Modulate at 2 Hz (120 BPM)
        signal = np.sin(2 * np.pi * 440 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
        
        # Convert to float32
        signal = signal.astype(np.float32)
        
        metadata = AudioMetadata(
            file_path="test.wav",
            sample_rate=sample_rate,
            duration=duration,
            channels=1,
            format="WAV"
        )
        
        return AudioData(
            samples=signal,
            metadata=metadata
        )
    
    def test_detector_initialization(self, tempo_detector: TempoDetector) -> None:
        """Test tempo detector initialization."""
        assert tempo_detector is not None
        assert hasattr(tempo_detector, 'detect_tempo')
        assert hasattr(tempo_detector, 'detect_time_varying_tempo')
    
    def test_detect_tempo_basic(self, tempo_detector: TempoDetector, sample_audio_data: AudioData) -> None:
        """Test basic tempo detection."""
        tempo_info = tempo_detector.detect_tempo(sample_audio_data)
        
        assert isinstance(tempo_info, TempoInfo)
        assert isinstance(tempo_info.tempo, float)
        assert tempo_info.tempo > 0
        assert isinstance(tempo_info.beat_times, np.ndarray)
        assert len(tempo_info.beat_times) > 0
        assert tempo_info.confidence >= 0.0
        assert tempo_info.confidence <= 1.0
    
    def test_detect_tempo_expected_range(self, tempo_detector: TempoDetector, sample_audio_data: AudioData) -> None:
        """Test that detected tempo is in expected range."""
        tempo_info = tempo_detector.detect_tempo(sample_audio_data)
        
        # For our test signal at 2 Hz modulation, we expect around 120 BPM
        # Allow some tolerance for real-world detection
        assert 100 <= tempo_info.tempo <= 140
    
    def test_detect_tempo_beat_timing(self, tempo_detector: TempoDetector, sample_audio_data: AudioData) -> None:
        """Test that beat times are reasonable."""
        tempo_info = tempo_detector.detect_tempo(sample_audio_data)
        
        # Beat times should be within the audio duration
        assert all(0 <= beat_time <= sample_audio_data.metadata.duration for beat_time in tempo_info.beat_times)
        
        # Beat times should be monotonically increasing
        beat_times = tempo_info.beat_times
        assert all(beat_times[i] < beat_times[i+1] for i in range(len(beat_times)-1))
        
        # Beat intervals should be roughly consistent
        if len(beat_times) > 1:
            intervals = np.diff(beat_times)
            expected_interval = 60.0 / tempo_info.tempo
            # Allow 20% tolerance
            assert all(abs(interval - expected_interval) / expected_interval < 0.2 for interval in intervals)
    
    def test_detect_time_varying_tempo(self, tempo_detector: TempoDetector, sample_audio_data: AudioData) -> None:
        """Test time-varying tempo detection."""
        tempo_info = tempo_detector.detect_time_varying_tempo(sample_audio_data)
        
        assert isinstance(tempo_info, TempoInfo)
        assert tempo_info.tempo > 0
        assert isinstance(tempo_info.beat_times, np.ndarray)
        assert len(tempo_info.beat_times) > 0
        assert 0.0 <= tempo_info.confidence <= 1.0
        assert not tempo_info.is_constant_tempo
    
    def test_get_tempo_curve(self, tempo_detector: TempoDetector, sample_audio_data: AudioData) -> None:
        """Test getting tempo curve."""
        tempo_curve = tempo_detector.get_tempo_curve(sample_audio_data)
        
        assert isinstance(tempo_curve, np.ndarray)
        assert tempo_curve.ndim == 1
        assert len(tempo_curve) > 0
        assert np.all(tempo_curve > 0)
    
    def test_confidence_estimation(self, tempo_detector: TempoDetector, sample_audio_data: AudioData) -> None:
        """Test confidence estimation."""
        tempo_info = tempo_detector.detect_tempo(sample_audio_data)
        
        assert 0.0 <= tempo_info.confidence <= 1.0
        
        # For our clear beat signal, confidence should be reasonably high
        assert tempo_info.confidence > 0.3
    
    def test_tempo_info_dataclass(self) -> None:
        """Test TempoInfo dataclass."""
        beat_times = np.array([0.0, 0.5, 1.0, 1.5])
        tempo_info = TempoInfo(
            tempo=120.0,
            beat_times=beat_times,
            confidence=0.85
        )
        
        assert tempo_info.tempo == 120.0
        assert np.array_equal(tempo_info.beat_times, beat_times)
        assert tempo_info.confidence == 0.85
    
    def test_empty_audio(self, tempo_detector: TempoDetector) -> None:
        """Test handling of empty audio data."""
        empty_signal = np.array([], dtype=np.float32)
        metadata = AudioMetadata(
            file_path="empty.wav",
            sample_rate=22050,
            duration=0.0,
            channels=1,
            format="WAV"
        )
        empty_audio = AudioData(samples=empty_signal, metadata=metadata)
        
        # Should handle gracefully (librosa may raise ValueError)
        with pytest.raises(ValueError):
            tempo_detector.detect_tempo(empty_audio)
    
    def test_very_short_audio(self, tempo_detector: TempoDetector) -> None:
        """Test handling of very short audio."""
        # Very short signal (0.1 seconds)
        sample_rate = 22050
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        signal = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        metadata = AudioMetadata(
            file_path="short.wav",
            sample_rate=sample_rate,
            duration=duration,
            channels=1,
            format="WAV"
        )
        short_audio = AudioData(samples=signal, metadata=metadata)
        
        # Should handle gracefully or return reasonable result
        tempo_info = tempo_detector.detect_tempo(short_audio)
        assert isinstance(tempo_info, TempoInfo)
        assert tempo_info.tempo > 0
        assert tempo_info.confidence >= 0.0
    
    def test_noise_audio(self, tempo_detector: TempoDetector) -> None:
        """Test tempo detection on noise (should have low confidence)."""
        sample_rate = 22050
        duration = 4.0
        noise = np.random.normal(0, 0.1, int(sample_rate * duration)).astype(np.float32)
        
        metadata = AudioMetadata(
            file_path="noise.wav",
            sample_rate=sample_rate,
            duration=duration,
            channels=1,
            format="WAV"
        )
        noise_audio = AudioData(samples=noise, metadata=metadata)
        
        tempo_info = tempo_detector.detect_tempo(noise_audio)
        
        # Should still return a result but with relatively low confidence
        assert isinstance(tempo_info, TempoInfo)
        assert tempo_info.confidence < 0.8
    
    def test_stereo_audio(self, tempo_detector: TempoDetector) -> None:
        """Test tempo detection on stereo audio."""
        sample_rate = 22050
        duration = 4.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Create stereo signal
        left = np.sin(2 * np.pi * 440 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
        right = np.sin(2 * np.pi * 330 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
        stereo_signal = np.column_stack([left, right]).astype(np.float32)
        
        metadata = AudioMetadata(
            file_path="stereo.wav",
            sample_rate=sample_rate,
            duration=duration,
            channels=2,
            format="WAV"
        )
        stereo_audio = AudioData(samples=stereo_signal, metadata=metadata)
        
        tempo_info = tempo_detector.detect_tempo(stereo_audio)
        
        assert isinstance(tempo_info, TempoInfo)
        assert tempo_info.tempo > 0
        assert len(tempo_info.beat_times) > 0
