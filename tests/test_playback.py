"""
Tests for the MIDI playback module.
"""
import pytest
import numpy as np
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from mp3paramidi.midi.playback import MidiPlayer, PlaybackState, PlaybackError
from mp3paramidi.audio.pitch_detector import NoteEvent


class TestPlaybackState:
    """Test the PlaybackState enum."""
    
    def test_state_values(self) -> None:
        """Test that state values are correct."""
        assert PlaybackState.STOPPED.value == "stopped"
        assert PlaybackState.PLAYING.value == "playing"
        assert PlaybackState.PAUSED.value == "paused"
    
    def test_state_comparison(self) -> None:
        """Test state comparison operations."""
        assert PlaybackState.STOPPED != PlaybackState.PLAYING
        assert PlaybackState.PLAYING == PlaybackState.PLAYING


class TestMidiPlayer:
    """Tests aligned with the current MidiPlayer implementation."""

    @pytest.fixture
    def midi_player(self):
        with patch('mp3paramidi.midi.playback.pygame.mixer') as mixer_mock:
            mixer_mock.music = MagicMock()
            mixer_mock.music.get_busy.return_value = False
            mixer_mock.music.get_pos.return_value = 0
            player = MidiPlayer()
            yield player, mixer_mock

    def test_initial_state(self, midi_player) -> None:
        player, _ = midi_player
        assert player.state == PlaybackState.STOPPED
        assert player.current_file is None

    def test_load_midi(self, midi_player, tmp_path: Path) -> None:
        player, mixer_mock = midi_player
        midi_path = tmp_path / "test.mid"
        midi_path.write_bytes(b"MThd")

        player.load_midi(midi_path)

        assert player.current_file == midi_path
        mixer_mock.music.load.assert_called_once_with(str(midi_path))

    def test_load_missing_file_raises(self, midi_player) -> None:
        player, _ = midi_player
        with pytest.raises(PlaybackError):
            player.load_midi(Path("missing.mid"))

    def test_load_invalid_extension_raises(self, midi_player, tmp_path: Path) -> None:
        player, _ = midi_player
        text_path = tmp_path / "bad.txt"
        text_path.write_text("not midi")

        with pytest.raises(PlaybackError):
            player.load_midi(text_path)

    def test_play_without_file_raises(self, midi_player) -> None:
        player, _ = midi_player
        with pytest.raises(PlaybackError):
            player.play()

    def test_play_sets_state(self, midi_player, tmp_path: Path) -> None:
        player, mixer_mock = midi_player
        midi_path = tmp_path / "test.mid"
        midi_path.write_bytes(b"MThd")
        player.load_midi(midi_path)

        with patch.object(player, '_start_position_tracking') as tracking_mock:
            player.play()

        assert player.state == PlaybackState.PLAYING
        mixer_mock.music.play.assert_called_once()
        tracking_mock.assert_called_once()

    def test_pause_sets_state(self, midi_player, tmp_path: Path) -> None:
        player, mixer_mock = midi_player
        midi_path = tmp_path / "test.mid"
        midi_path.write_bytes(b"MThd")
        player.load_midi(midi_path)

        with patch.object(player, '_start_position_tracking'):
            player.play()

        player.pause()
        assert player.state == PlaybackState.PAUSED
        mixer_mock.music.pause.assert_called_once()

    def test_stop_sets_state(self, midi_player, tmp_path: Path) -> None:
        player, mixer_mock = midi_player
        midi_path = tmp_path / "test.mid"
        midi_path.write_bytes(b"MThd")
        player.load_midi(midi_path)

        with patch.object(player, '_start_position_tracking'):
            player.play()

        player.stop()
        assert player.state == PlaybackState.STOPPED
        mixer_mock.music.stop.assert_called_once()

    def test_set_volume_clamps(self, midi_player) -> None:
        player, mixer_mock = midi_player

        player.set_volume(1.5)
        mixer_mock.music.set_volume.assert_called_with(1.0)

        player.set_volume(-0.2)
        mixer_mock.music.set_volume.assert_called_with(0.0)

    def test_is_playing_uses_busy_flag(self, midi_player) -> None:
        player, mixer_mock = midi_player
        player.state = PlaybackState.PLAYING
        mixer_mock.music.get_busy.return_value = True
        assert player.is_playing()

        mixer_mock.music.get_busy.return_value = False
        assert not player.is_playing()

    def test_get_position_ms_to_seconds(self, midi_player) -> None:
        player, mixer_mock = midi_player
        mixer_mock.music.get_pos.return_value = 250
        assert player.get_position() == pytest.approx(0.25)

    def test_get_position_negative_returns_zero(self, midi_player) -> None:
        player, mixer_mock = midi_player
        mixer_mock.music.get_pos.return_value = -1
        assert player.get_position() == 0.0

    def test_check_midi_support(self) -> None:
        import mp3paramidi.midi.playback as playback_module

        with patch.object(playback_module.pygame.mixer, 'init') as init_mock:
            with patch.object(playback_module.pygame.mixer, 'quit') as quit_mock:
                init_mock.return_value = None
                quit_mock.return_value = None
                assert MidiPlayer.check_midi_support() is True
                init_mock.assert_called_once()
                quit_mock.assert_called_once()
