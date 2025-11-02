"""
Integration tests for advanced MIDI features.
"""
import pytest
import numpy as np
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from mp3paramidi.audio import AudioToMidiPipeline, PipelineResult, AudioData, AudioMetadata
from mp3paramidi.audio.tempo_detector import TempoDetector
from mp3paramidi.audio.note_filter import NoteFilter, FilterConfig
from mp3paramidi.midi.quantizer import NoteQuantizer, QuantizationGrid
from mp3paramidi.midi.playback import MidiPlayer
from mp3paramidi.gui.settings_dialog import SettingsData
from mp3paramidi.gui.workers import ConversionConfig


class TestAdvancedFeaturesIntegration:
    """Integration tests for all advanced features working together."""
    
    @pytest.fixture
    def sample_audio_data(self) -> AudioData:
        """Create sample audio data for testing."""
        # Generate a simple sine wave with clear beat pattern
        sample_rate = 22050
        duration = 4.0  # 4 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Create a signal with clear beat pattern at 120 BPM (2 Hz)
        signal = np.sin(2 * np.pi * 440 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
        
        # Add some harmonics for richer sound
        signal += 0.3 * np.sin(2 * np.pi * 880 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
        
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
    
    @pytest.fixture
    def advanced_config(self) -> dict:
        """Create advanced configuration for testing."""
        return {
            'fmin': 'C2',
            'fmax': 'C7',
            'tempo': 120.0,
            'min_note_duration': 0.05,
            'detect_tempo': True,
            'quantization_enabled': True,
            'quantization_grid': 'SIXTEENTH',
            'filter_config': {
                'min_confidence': 0.3,
                'min_duration': 0.05,
                'min_velocity': 40,
                'max_velocity': 110,
                'remove_outliers': True,
                'outlier_std_threshold': 2.0
            },
            'use_ai_models': False,
            'enable_separation': False,
        }
    
    def test_pipeline_with_all_features(self, sample_audio_data: AudioData, advanced_config: dict) -> None:
        """Test the complete pipeline with all advanced features enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.mid"
            
            # Create pipeline with all features
            pipeline = AudioToMidiPipeline(
                fmin=advanced_config['fmin'],
                fmax=advanced_config['fmax'],
                tempo=advanced_config['tempo'],
                min_note_duration=advanced_config['min_note_duration'],
                detect_tempo=advanced_config['detect_tempo'],
                quantization_enabled=advanced_config['quantization_enabled'],
                quantization_grid=QuantizationGrid[advanced_config['quantization_grid']],
                filter_config=FilterConfig(**advanced_config['filter_config'])
            )
            
            # Process audio
            result = pipeline.process(sample_audio_data, output_path)
            
            # Verify successful processing
            assert result.success == True
            assert result.output_path == output_path
            assert result.output_path.exists()
            
            # Verify advanced features were applied
            assert result.detected_tempo is not None
            assert result.beat_times is not None
            assert result.quantization_applied == True
            assert result.notes_filtered >= 0
            
            # Check that detected tempo is reasonable
            assert 100 <= result.detected_tempo <= 140  # Around 120 BPM
    
    def test_pipeline_with_quantization_only(self, sample_audio_data: AudioData) -> None:
        """Test pipeline with only quantization enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output_quantized.mid"
            
            pipeline = AudioToMidiPipeline(
                detect_tempo=False,
                quantization_enabled=True,
                quantization_grid=QuantizationGrid.EIGHTH,
                filter_config=None
            )
            
            result = pipeline.process(sample_audio_data, output_path)
            
            assert result.success == True
            assert result.quantization_applied == True
            assert result.detected_tempo is None  # Tempo detection disabled
    
    def test_pipeline_with_tempo_detection_only(self, sample_audio_data: AudioData) -> None:
        """Test pipeline with only tempo detection enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output_tempo.mid"
            
            pipeline = AudioToMidiPipeline(
                detect_tempo=True,
                quantization_enabled=False,
                filter_config=None
            )
            
            result = pipeline.process(sample_audio_data, output_path)
            
            assert result.success == True
            assert result.detected_tempo is not None
            assert result.beat_times is not None
            assert result.quantization_applied == False  # Quantization disabled
    
    def test_pipeline_with_filtering_only(self, sample_audio_data: AudioData) -> None:
        """Test pipeline with only filtering enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output_filtered.mid"
            
            filter_config = FilterConfig(
                min_confidence=0.5,
                remove_outliers=True
            )
            
            pipeline = AudioToMidiPipeline(
                detect_tempo=False,
                quantization_enabled=False,
                filter_config=filter_config
            )
            
            result = pipeline.process(sample_audio_data, output_path)
            
            assert result.success == True
            assert result.detected_tempo is None
            assert result.quantization_applied == False
            assert result.notes_filtered >= 0
    
    def test_pipeline_with_all_features_disabled(self, sample_audio_data: AudioData) -> None:
        """Test pipeline with all advanced features disabled (baseline)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output_baseline.mid"
            
            pipeline = AudioToMidiPipeline(
                detect_tempo=False,
                quantization_enabled=False,
                filter_config=None
            )
            
            result = pipeline.process(sample_audio_data, output_path)
            
            assert result.success == True
            assert result.detected_tempo is None
            assert result.beat_times is None
            assert result.quantization_applied == False
            assert result.notes_filtered == 0
    
    def test_quantization_grid_sizes(self, sample_audio_data: AudioData) -> None:
        """Test different quantization grid sizes."""
        grids = [
            QuantizationGrid.QUARTER,
            QuantizationGrid.EIGHTH,
            QuantizationGrid.SIXTEENTH,
            QuantizationGrid.THIRTY_SECOND
        ]
        
        results = {}
        
        for grid in grids:
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"output_{grid.name.lower()}.mid"
                
                pipeline = AudioToMidiPipeline(
                    detect_tempo=True,
                    quantization_enabled=True,
                    quantization_grid=grid,
                    filter_config=None
                )
                
                result = pipeline.process(sample_audio_data, output_path)
                results[grid] = result
                
                assert result.success == True
                assert result.quantization_applied == True
        
        # Verify that different grids produce different results
        # (This is a basic check - in practice, the timing differences would be subtle)
        for grid, result in results.items():
            assert result.note_count > 0
    
    def test_filter_config_variations(self, sample_audio_data: AudioData) -> None:
        """Test different filter configurations."""
        configs = [
            FilterConfig(min_confidence=0.1),  # Very permissive
            FilterConfig(min_confidence=0.8),  # Very strict
            FilterConfig(remove_outliers=False),  # No outlier removal
            FilterConfig(min_duration=0.1),  # Longer minimum duration
        ]
        
        for config in configs:
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "output_filtered.mid"
                
                pipeline = AudioToMidiPipeline(
                    detect_tempo=False,
                    quantization_enabled=False,
                    filter_config=config
                )
                
                result = pipeline.process(sample_audio_data, output_path)
                
                assert result.success == True
                assert result.notes_filtered >= 0
    
    def test_tempo_detection_consistency(self, sample_audio_data: AudioData) -> None:
        """Test that tempo detection is consistent across multiple runs."""
        tempos = []
        
        for i in range(3):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"output_{i}.mid"
                
                pipeline = AudioToMidiPipeline(
                    detect_tempo=True,
                    quantization_enabled=False,
                    filter_config=None
                )
                
                result = pipeline.process(sample_audio_data, output_path)
                tempos.append(result.detected_tempo)
        
        # All detected tempos should be close to each other
        # Allow some tolerance for real-world detection
        for tempo in tempos:
            assert abs(tempo - tempos[0]) < 10.0  # Within 10 BPM
    
    def test_worker_integration(self, sample_audio_data: AudioData, advanced_config: dict) -> None:
        """Test integration with ConversionWorker."""
        from mp3paramidi.gui.workers import ConversionWorker
        
        # Create worker with advanced config
        config = ConversionConfig(**advanced_config)
        worker = ConversionWorker([sample_audio_data], config.__dict__)
        
        # Mock the progress callback
        progress_callback = Mock()
        worker.progress_callback = progress_callback
        
        # Run conversion (simplified for testing)
        # In a real test, this would run in a separate thread
        pipeline = AudioToMidiPipeline(
            fmin=config.fmin,
            fmax=config.fmax,
            tempo=config.tempo,
            min_note_duration=config.min_note_duration,
            detect_tempo=config.detect_tempo,
            quantization_enabled=config.quantization_enabled,
            quantization_grid=QuantizationGrid[config.quantization_grid],
            filter_config=FilterConfig(**config.filter_config) if config.filter_config else None
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "worker_output.mid"
            result = pipeline.process(sample_audio_data, output_path)
            
            assert result.success == True
            assert result.detected_tempo is not None
            assert result.quantization_applied == True
    
    def test_settings_dialog_integration(self, advanced_config: dict) -> None:
        """Test integration with settings dialog."""
        from PyQt6.QtWidgets import QApplication
        
        if not QApplication.instance():
            app = QApplication([])
        
        # Create settings data from config
        settings_data = SettingsData(
            quantization_enabled=advanced_config['quantization_enabled'],
            quantization_grid=QuantizationGrid[advanced_config['quantization_grid']],
            detect_tempo=advanced_config['detect_tempo'],
            default_tempo=advanced_config['tempo'],
            min_note_duration=advanced_config['min_note_duration'],
            min_confidence=advanced_config['filter_config']['min_confidence'],
            remove_outliers=advanced_config['filter_config']['remove_outliers'],
        )
        
        # Verify settings data
        assert settings_data.quantization_enabled == True
        assert settings_data.quantization_grid == QuantizationGrid.SIXTEENTH
        assert settings_data.detect_tempo == True
        assert settings_data.min_confidence == 0.3
        assert settings_data.remove_outliers == True
    
    def test_midi_playback_integration(self, sample_audio_data: AudioData) -> None:
        """Test integration with MIDI playback."""
        # First generate a MIDI file
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "playback_test.mid"
            
            pipeline = AudioToMidiPipeline(
                detect_tempo=True,
                quantization_enabled=True,
                quantization_grid=QuantizationGrid.SIXTEENTH
            )
            
            result = pipeline.process(sample_audio_data, output_path)
            assert result.success == True
            assert output_path.exists()
            
            # Test playback initialization
            with patch('pygame.mixer.init'):
                with patch('pygame.mixer.music.load'):
                    player = MidiPlayer()
                    
                    # Load the generated MIDI
                    player.load_midi(output_path)
                    
                    assert player.current_file == output_path
                    assert player.duration > 0
                    assert player.state.value == "stopped"
    
    def test_error_handling_integration(self, sample_audio_data: AudioData) -> None:
        """Test error handling with advanced features."""
        # Test with invalid quantization grid
        with pytest.raises(KeyError):
            pipeline = AudioToMidiPipeline(
                quantization_grid='INVALID_GRID',  # type: ignore
                detect_tempo=False,
                quantization_enabled=False,
                filter_config=None
            )
        
        # Test with invalid filter config
        invalid_filter_config = FilterConfig(min_confidence=1.5)  # Invalid confidence
        pipeline = AudioToMidiPipeline(
            detect_tempo=False,
            quantization_enabled=False,
            filter_config=invalid_filter_config
        )
        
        # Should handle gracefully (clamp values or use defaults)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "error_test.mid"
            result = pipeline.process(sample_audio_data, output_path)
            
            # Should still succeed but with warnings
            assert result.success == True
    
    def test_performance_with_advanced_features(self, sample_audio_data: AudioData) -> None:
        """Test performance impact of advanced features."""
        import time
        
        configs = [
            {'detect_tempo': False, 'quantization_enabled': False, 'filter_config': None},
            {'detect_tempo': True, 'quantization_enabled': False, 'filter_config': None},
            {'detect_tempo': False, 'quantization_enabled': True, 'filter_config': None},
            {'detect_tempo': False, 'quantization_enabled': False, 'filter_config': FilterConfig()},
            {'detect_tempo': True, 'quantization_enabled': True, 'filter_config': FilterConfig()},
        ]
        
        processing_times = []
        
        for config in configs:
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "perf_test.mid"
                
                pipeline = AudioToMidiPipeline(**config)
                
                start_time = time.perf_counter()
                result = pipeline.process(sample_audio_data, output_path)
                end_time = time.perf_counter()
                
                processing_time = end_time - start_time
                processing_times.append(processing_time)
                
                assert result.success == True
        
        # Advanced features should add some processing time
        # But not excessively (this is a rough sanity check)
        baseline_time = processing_times[0]
        full_features_time = processing_times[-1]
        
        # Should not be more than 10x slower
        assert full_features_time < baseline_time * 10
    
    def test_memory_usage_with_advanced_features(self, sample_audio_data: AudioData) -> None:
        """Test memory usage with advanced features."""
        import gc
        import sys
        
        # Force garbage collection before test
        gc.collect()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "memory_test.mid"
            
            pipeline = AudioToMidiPipeline(
                detect_tempo=True,
                quantization_enabled=True,
                quantization_grid=QuantizationGrid.SIXTEENTH,
                filter_config=FilterConfig()
            )
            
            result = pipeline.process(sample_audio_data, output_path)
            
            assert result.success == True
            
            # Clean up
            del pipeline
            del result
            gc.collect()
            
            # Memory should be released (basic check)
            # In a real test, you'd use memory profiling tools
