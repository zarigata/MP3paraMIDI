"""Tests for GUI worker classes."""
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PyQt6.QtCore import QCoreApplication, QThread, QTimer

from mp3paramidi.gui.workers import ConversionWorker, ConversionConfig
from mp3paramidi.audio import AudioData, PipelineProgress, PipelineResult


# Create QApplication instance once for all tests; ensure QThread works in tests
@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(list(sys.argv))
    return app

# Test parameters
SAMPLE_RATE = 44100

class TestConversionWorker:
    """Tests for the ConversionWorker class."""
    
    @pytest.fixture
    def worker(self):
        """Create a ConversionWorker instance with default config."""
        config = ConversionConfig(
            fmin='C2',
            fmax='C7',
            tempo=120.0,
            min_note_duration=0.05,
            output_dir=None
        )
        return ConversionWorker([], asdict(config))
    
    @pytest.fixture
    def mock_audio_data(self):
        """Create a mock AudioData instance."""
        audio_data = MagicMock(spec=AudioData)
        audio_data.samples = np.random.rand(SAMPLE_RATE).astype(np.float32)
        audio_data.sample_rate = SAMPLE_RATE
        audio_data.metadata = MagicMock(
            file_path=Path("test_audio.wav"),
            sample_rate=SAMPLE_RATE,
        )
        return audio_data
    
    def test_initialization(self, worker):
        """Test that the worker initializes with the correct properties."""
        assert worker.audio_data_list == []
        assert worker.config.fmin == 'C2'
        assert worker.config.fmax == 'C7'
        assert worker.config.tempo == 120.0
        assert worker.config.min_note_duration == 0.05
        assert worker.config.output_dir is None
        assert worker.is_cancelled is False
    
    def _run_worker(self, qtbot, worker, audio_items, *, timeout=3000, before_start=None):
        """Run worker in a QThread and wait for the finished signal."""
        worker.audio_data_list = audio_items

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        if before_start is not None:
            before_start(worker)

        with qtbot.waitSignal(worker.finished, timeout=timeout):
            thread.start()

        thread.quit()
        thread.wait()

    def test_run_single_file_success(self, qtbot, worker, mock_audio_data):
        """Test processing a single file successfully."""
        result = PipelineResult(
            success=True,
            output_path=Path("output.mid"),
            note_count=5,
            duration=2.5,
            error_message=None,
            processing_time=1.23,
        )

        progress_signals = []
        file_completed_signals = []
        all_completed_signals = []
        error_signals = []

        worker.progress.connect(lambda pct, msg: progress_signals.append((pct, msg)))
        worker.file_completed.connect(lambda f, r: file_completed_signals.append((f, r)))
        worker.all_completed.connect(lambda s, e: all_completed_signals.append((s, e)))
        worker.error.connect(lambda f, e: error_signals.append((f, e)))

        pipelines = []

        def pipeline_factory(*_, **kwargs):
            progress_callback = kwargs.get('progress_callback')
            pipeline = MagicMock()

            def process(audio_data, output_path):
                if progress_callback:
                    progress_callback(PipelineProgress(stage='start', progress=0.0, message='start'))
                    progress_callback(PipelineProgress(stage='done', progress=1.0, message='done'))
                return result

            pipeline.process.side_effect = process
            pipelines.append(pipeline)
            return pipeline

        with patch('mp3paramidi.gui.workers.AudioToMidiPipeline', side_effect=pipeline_factory):
            self._run_worker(qtbot, worker, [mock_audio_data])

        # Verify signals
        assert len(progress_signals) > 0
        assert progress_signals[0][0] == 0
        assert progress_signals[-1][0] == 100

        assert len(file_completed_signals) == 1
        assert file_completed_signals[0][0] == Path(mock_audio_data.metadata.file_path).name
        assert file_completed_signals[0][1].success is True

        assert len(all_completed_signals) == 1
        assert all_completed_signals[0] == (1, 0)
        assert not error_signals

        assert len(pipelines) == 1
        pipelines[0].process.assert_called_once()
        called_audio_data = pipelines[0].process.call_args[0][0]
        assert called_audio_data is mock_audio_data
    
    def test_run_multiple_files(self, qtbot, worker, mock_audio_data):
        """Test processing multiple files with one failure."""
        audio1 = mock_audio_data
        audio2 = MagicMock(spec=AudioData)
        audio2.samples = np.random.rand(SAMPLE_RATE).astype(np.float32)
        audio2.sample_rate = SAMPLE_RATE
        audio2.metadata = MagicMock(
            file_path=Path("test_audio2.wav"),
            sample_rate=SAMPLE_RATE,
        )

        results = [
            PipelineResult(success=True, output_path=Path("output1.mid"), note_count=3, duration=1.5, processing_time=1.0),
            PipelineResult(success=False, output_path=None, error_message="Conversion failed", processing_time=0.5),
        ]
        result_iter = iter(results)

        progress_signals = []
        file_completed_signals = []
        all_completed_signals = []
        error_signals = []

        worker.progress.connect(lambda pct, msg: progress_signals.append((pct, msg)))
        worker.file_completed.connect(lambda f, r: file_completed_signals.append((f, r)))
        worker.all_completed.connect(lambda s, e: all_completed_signals.append((s, e)))
        worker.error.connect(lambda f, e: error_signals.append((f, e)))

        def pipeline_factory(*_, **kwargs):
            progress_callback = kwargs.get('progress_callback')
            pipeline = MagicMock()

            def process(audio_data, output_path):
                if progress_callback:
                    progress_callback(PipelineProgress(stage='start', progress=0.0, message='start'))
                    progress_callback(PipelineProgress(stage='done', progress=1.0, message='done'))
                result = next(result_iter)
                return result

            pipeline.process.side_effect = process
            return pipeline

        with patch('mp3paramidi.gui.workers.AudioToMidiPipeline', side_effect=pipeline_factory):
            self._run_worker(qtbot, worker, [audio1, audio2])

        assert len(file_completed_signals) == 1
        assert len(error_signals) == 1
        assert len(all_completed_signals) == 1
        assert all_completed_signals[0] == (1, 1)

        progress_values = [pct for pct, _ in progress_signals]
        assert progress_values[0] == 0
        assert progress_values[-1] == 100
        assert all(p1 <= p2 for p1, p2 in zip(progress_values, progress_values[1:]))
    
    def test_cancel_processing(self, qtbot, worker, mock_audio_data):
        """Test that processing can be cancelled."""
        first_result = PipelineResult(
            success=True,
            output_path=Path("output.mid"),
            note_count=1,
            duration=1.0,
            processing_time=0.5,
        )

        finished_signals = []
        worker.finished.connect(lambda: finished_signals.append(True))

        def pipeline_factory(*_, **kwargs):
            progress_callback = kwargs.get('progress_callback')
            pipeline = MagicMock()

            def process(audio_data, output_path):
                if progress_callback:
                    progress_callback(PipelineProgress(stage='start', progress=0.0, message='start'))
                time.sleep(0.1)
                if progress_callback:
                    progress_callback(PipelineProgress(stage='done', progress=1.0, message='done'))
                return first_result

            pipeline.process.side_effect = process
            return pipeline

        def schedule_cancel(_worker):
            QTimer.singleShot(50, _worker.cancel)

        with patch('mp3paramidi.gui.workers.AudioToMidiPipeline', side_effect=pipeline_factory) as pipeline_cls:
            self._run_worker(
                qtbot,
                worker,
                [mock_audio_data] * 3,
                timeout=4000,
                before_start=schedule_cancel,
            )

        # The worker should stop after cancellation, invoking at most one pipeline
        assert pipeline_cls.call_count == 1
        assert len(finished_signals) == 1
    
    def test_output_directory_creation(self, qtbot, worker, mock_audio_data, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        output_dir = tmp_path / "nonexistent_subdir"
        worker.config.output_dir = output_dir
        worker.audio_data_list = [mock_audio_data]

        result = PipelineResult(
            success=True,
            output_path=output_dir / "output.mid",
            note_count=1,
            duration=1.0,
            processing_time=0.1,
        )

        def pipeline_factory(*_, **kwargs):
            progress_callback = kwargs.get('progress_callback')
            pipeline = MagicMock()

            def process(audio_data, output_path):
                if progress_callback:
                    progress_callback(PipelineProgress(stage='start', progress=0.0, message='start'))
                    progress_callback(PipelineProgress(stage='done', progress=1.0, message='done'))
                return result

            pipeline.process.side_effect = process
            return pipeline

        with patch('mp3paramidi.gui.workers.AudioToMidiPipeline', side_effect=pipeline_factory):
            self._run_worker(qtbot, worker, [mock_audio_data])

        assert output_dir.exists()
        assert output_dir.is_dir()
    
    def test_error_handling(self, qtbot, worker, mock_audio_data):
        """Test that exceptions during processing are properly handled."""
        error_signals = []
        worker.error.connect(lambda f, e: error_signals.append((f, e)))

        def pipeline_factory(*_, **kwargs):
            progress_callback = kwargs.get('progress_callback')
            pipeline = MagicMock()

            def process(audio_data, output_path):
                if progress_callback:
                    progress_callback(PipelineProgress(stage='start', progress=0.0, message='start'))
                raise Exception("Test error")

            pipeline.process.side_effect = process
            return pipeline

        with patch('mp3paramidi.gui.workers.AudioToMidiPipeline', side_effect=pipeline_factory):
            self._run_worker(qtbot, worker, [mock_audio_data])

        assert len(error_signals) == 1
        assert "Test error" in error_signals[0][1]
