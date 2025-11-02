"""Tests for the audio loader module."""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from mp3paramidi.audio import (
    AudioLoader,
    AudioData,
    AudioMetadata,
    AudioLoadError,
    UnsupportedFormatError,
    FFmpegNotFoundError,
    CorruptedFileError,
    InvalidAudioDataError,
)
from tests.fixtures import (
    create_test_wav,
    create_test_mp3,
    create_corrupted_file,
)

# Skip MP3 tests if FFmpeg is not available
FFMPEG_AVAILABLE = AudioLoader()._ffmpeg_available


class TestFFmpegDetector:
    """Tests for the FFmpegDetector class."""
    
    @patch('shutil.which')
    @patch('os.path.isfile', return_value=True)
    @patch.dict('os.environ', {'FFMPEG_BINARY': '/custom/ffmpeg'})
    def test_find_ffmpeg_from_env(self, mock_isfile, mock_which):
        """Test finding FFmpeg from environment variable."""
        from mp3paramidi.audio.loader import FFmpegDetector
        
        # Test with FFMPEG_BINARY set and file exists
        assert FFmpegDetector.find_ffmpeg() == '/custom/ffmpeg'
        mock_which.assert_not_called()
        mock_isfile.assert_called_once_with('/custom/ffmpeg')
    
    @patch('subprocess.run')
    def test_is_available(self, mock_run):
        """Test FFmpeg availability check."""
        from mp3paramidi.audio.loader import FFmpegDetector
        
        # Mock successful FFmpeg version check
        mock_result = MagicMock()
        mock_result.stdout = "ffmpeg version 4.3.1"
        mock_run.return_value = mock_result
        
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            assert FFmpegDetector.is_available() is True
    
    @patch('subprocess.run', side_effect=FileNotFoundError)
    def test_is_available_not_found(self, mock_run):
        """Test FFmpeg availability check when not found."""
        from mp3paramidi.audio.loader import FFmpegDetector
        
        with patch('shutil.which', return_value=None):
            assert FFmpegDetector.is_available() is False


class TestAudioValidator:
    """Tests for the AudioValidator class."""
    
    def test_is_supported_extension(self):
        """Test supported file extensions."""
        from mp3paramidi.audio.loader import AudioValidator
        
        assert AudioValidator.is_supported_extension('test.wav') is True
        assert AudioValidator.is_supported_extension('test.WAV') is True
        assert AudioValidator.is_supported_extension('test.mp3') is True
        assert AudioValidator.is_supported_extension('test.MP3') is True
        assert AudioValidator.is_supported_extension('test.txt') is False
        assert AudioValidator.is_supported_extension('test') is False
    
    def test_validate_file_exists(self, tmp_path):
        """Test file existence validation."""
        from mp3paramidi.audio.loader import AudioValidator
        
        # Test with existing file
        test_file = tmp_path / 'test.txt'
        test_file.touch()
        AudioValidator.validate_file_exists(test_file)
        
        # Test with non-existent file
        non_existent = tmp_path / 'nonexistent.txt'
        with pytest.raises(FileNotFoundError):
            AudioValidator.validate_file_exists(non_existent)
    
    def test_validate_metadata(self):
        """Test metadata validation."""
        from mp3paramidi.audio.loader import AudioValidator, AudioMetadata
        
        # Valid metadata
        valid_meta = AudioMetadata(
            duration=1.0,
            sample_rate=44100,
            channels=2,
            bit_depth=16,
            format='WAV'
        )
        AudioValidator.validate_metadata(valid_meta)
        
        # Invalid duration
        invalid_duration = AudioMetadata(
            duration=0.0,  # Invalid
            sample_rate=44100,
            channels=2,
            bit_depth=16,
            format='WAV'
        )
        with pytest.raises(InvalidAudioDataError):
            AudioValidator.validate_metadata(invalid_duration)
        
        # Invalid sample rate
        invalid_rate = AudioMetadata(
            duration=1.0,
            sample_rate=100,  # Too low
            channels=2,
            bit_depth=16,
            format='WAV'
        )
        with pytest.raises(InvalidAudioDataError):
            AudioValidator.validate_metadata(invalid_rate)
        
        # Invalid channels
        invalid_channels = AudioMetadata(
            duration=1.0,
            sample_rate=44100,
            channels=3,  # Not 1 or 2
            bit_depth=16,
            format='WAV'
        )
        with pytest.raises(InvalidAudioDataError):
            AudioValidator.validate_metadata(invalid_channels)


class TestAudioLoader:
    """Tests for the AudioLoader class."""
    
    def test_load_wav_file(self, tmp_path):
        """Test loading a WAV file."""
        # Create a test WAV file
        wav_path = create_test_wav(
            output_path=tmp_path / 'test.wav',
            frequency=440.0,
            duration=0.1,
            sample_rate=44100,
            channels=1
        )
        
        # Load the file
        loader = AudioLoader()
        audio_data = loader.load(wav_path)
        
        # Verify the result
        assert isinstance(audio_data, AudioData)
        assert audio_data.file_path == wav_path
        assert isinstance(audio_data.samples, np.ndarray)
        assert audio_data.samples.dtype == np.float32
        assert len(audio_data.samples) > 0
        
        # Check metadata
        assert isinstance(audio_data.metadata, AudioMetadata)
        assert audio_data.metadata.duration == pytest.approx(0.1, abs=0.01)
        assert audio_data.metadata.sample_rate == 44100
        assert audio_data.metadata.channels == 1
        assert audio_data.metadata.format == 'WAV'
    
    @pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg not available")
    def test_load_mp3_file(self, tmp_path):
        """Test loading an MP3 file."""
        # Skip if FFmpeg is not available
        if not FFMPEG_AVAILABLE:
            pytest.skip("FFmpeg not available")
        
        # Create a test MP3 file
        mp3_path = create_test_mp3(
            output_path=tmp_path / 'test.mp3',
            frequency=440.0,
            duration=0.1,
            sample_rate=44100,
            channels=1
        )
        
        if not mp3_path:  # Skip if MP3 creation failed
            pytest.skip("Could not create test MP3 file")
        
        # Load the file
        loader = AudioLoader()
        audio_data = loader.load(mp3_path)
        
        # Verify the result
        assert isinstance(audio_data, AudioData)
        assert audio_data.file_path == mp3_path
        assert isinstance(audio_data.samples, np.ndarray)
        assert audio_data.samples.dtype == np.float32
        assert len(audio_data.samples) > 0
        
        # Check metadata
        assert isinstance(audio_data.metadata, AudioMetadata)
        assert audio_data.metadata.duration == pytest.approx(0.1, abs=0.02)  # Allow some tolerance
        assert audio_data.metadata.sample_rate == 44100
        assert audio_data.metadata.channels == 1
        assert audio_data.metadata.format == 'MP3'
    
    def test_load_stereo_file(self, tmp_path):
        """Test loading a stereo WAV file."""
        # Create a test stereo WAV file
        wav_path = create_test_wav(
            output_path=tmp_path / 'stereo.wav',
            frequency=440.0,
            duration=0.1,
            sample_rate=44100,
            channels=2
        )
        
        # Load with preserve_stereo=True
        loader = AudioLoader(preserve_stereo=True)
        audio_data = loader.load(wav_path)
        
        # Should be stereo (2 channels)
        assert audio_data.samples.ndim == 2
        assert audio_data.samples.shape[1] == 2
        assert audio_data.metadata.channels == 2
        
        # Load with preserve_stereo=False
        loader = AudioLoader(preserve_stereo=False)
        audio_data = loader.load(wav_path)
        
        # Should be mono (1 channel)
        assert audio_data.samples.ndim == 1 or audio_data.samples.shape[1] == 1
        assert audio_data.metadata.channels == 1
    
    def test_load_with_resampling(self, tmp_path):
        """Test loading with sample rate conversion."""
        # Create a test WAV file at 44.1kHz
        wav_path = create_test_wav(
            output_path=tmp_path / 'test_44k.wav',
            frequency=440.0,
            duration=0.1,
            sample_rate=44100,
            channels=1
        )
        
        # Load with target sample rate of 22.05kHz
        loader = AudioLoader(target_sample_rate=22050)
        audio_data = loader.load(wav_path)
        
        # Should be resampled to 22.05kHz
        assert audio_data.metadata.sample_rate == 22050
        # Number of samples should be approximately half
        assert len(audio_data.samples) == pytest.approx(2205, abs=10)
    
    def test_unsupported_format(self, tmp_path):
        """Test loading an unsupported file format."""
        # Create a text file with unsupported extension
        txt_path = tmp_path / 'test.txt'
        txt_path.write_text('This is not an audio file')
        
        # Try to load it
        loader = AudioLoader()
        with pytest.raises(UnsupportedFormatError):
            loader.load(txt_path)
    
    def test_file_not_found(self):
        """Test loading a non-existent file."""
        loader = AudioLoader()
        with pytest.raises(FileNotFoundError):
            loader.load('/path/that/does/not/exist.wav')
    
    def test_corrupted_file(self, tmp_path):
        """Test loading a corrupted audio file."""
        # Create a corrupted WAV file
        corrupted_path = create_corrupted_file(tmp_path / 'corrupted.wav')
        
        # Try to load it
        loader = AudioLoader()
        with pytest.raises(CorruptedFileError):
            loader.load(corrupted_path)
    
    @patch('mp3paramidi.audio.loader.FFmpegDetector.is_available', return_value=False)
    def test_mp3_without_ffmpeg(self, mock_ffmpeg_available, tmp_path):
        """Test MP3 loading when FFmpeg is not available."""
        # Create a test MP3 file path (don't actually create it)
        mp3_path = tmp_path / 'test.mp3'
        mp3_path.touch()  # Create empty file
        
        # Try to load it
        loader = AudioLoader()
        with pytest.raises(FFmpegNotFoundError):
            loader.load(mp3_path)
    
    def test_metadata_extraction(self, tmp_path):
        """Test that metadata is correctly extracted from audio files."""
        # Create a test WAV file with known properties
        wav_path = create_test_wav(
            output_path=tmp_path / 'meta_test.wav',
            frequency=1000.0,
            duration=0.5,  # 500ms
            sample_rate=48000,
            channels=2
        )
        
        # Load the file
        loader = AudioLoader(preserve_stereo=True)
        audio_data = loader.load(wav_path)
        
        # Check metadata
        assert audio_data.metadata.duration == pytest.approx(0.5, abs=0.01)
        assert audio_data.metadata.sample_rate == 48000
        assert audio_data.metadata.channels == 2
        assert audio_data.metadata.bit_depth == 32  # We used FLOAT format in create_test_wav
        assert audio_data.metadata.format == 'WAV'
        
        # Check that the samples array matches the metadata
        assert audio_data.samples.shape == (24000, 2)  # 48000 * 0.5 = 24000 samples, 2 channels
        assert np.all(audio_data.samples >= -1.0) and np.all(audio_data.samples <= 1.0)
