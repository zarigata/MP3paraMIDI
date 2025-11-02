"""Unit tests for the DemucsWrapper abstraction."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mp3paramidi.models import DemucsWrapper, ModelLoadError


@pytest.fixture
def demucs_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> DemucsWrapper:
    import mp3paramidi.models.demucs_wrapper as demucs_module

    class _DummyContext:
        def __enter__(self) -> None:  # pragma: no cover - trivial
            return None

        def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
            return None

    class DummyTorch:
        class device:
            def __init__(self, value: str) -> None:
                self.type = value

        @staticmethod
        def no_grad() -> _DummyContext:
            return _DummyContext()

    class DummyTorchaudio:
        class functional:
            @staticmethod
            def resample(tensor: object, _orig: int, _target: int) -> object:
                return tensor

    def fake_get_model(name: str) -> SimpleNamespace:
        assert name == "htdemucs"
        return SimpleNamespace(
            sources=["vocals", "drums"],
            to=lambda device: SimpleNamespace(sources=["vocals", "drums"], to=lambda *_: None, eval=lambda: None),
            eval=lambda: None,
        )

    monkeypatch.setattr(demucs_module, "torch", DummyTorch())
    monkeypatch.setattr(demucs_module, "torchaudio", DummyTorchaudio())
    monkeypatch.setattr(demucs_module, "get_model", fake_get_model)

    # Device manager may be invoked when device is not supplied
    monkeypatch.setattr(
        demucs_module.DeviceManager,
        "detect_device",
        staticmethod(lambda: DummyTorch.device("cpu")),
    )

    wrapper = DemucsWrapper(
        model_name="htdemucs",
        cache_dir=tmp_path,
        segment_duration=4.2,
        device="cpu",
    )

    # Prevent heavy loading and provide a lightweight model representation
    monkeypatch.setattr(wrapper, "_ensure_model_loaded", lambda: None)
    wrapper._model = SimpleNamespace(sources=["vocals", "drums"])

    class FakeTensor:
        def to(self, _device: object) -> "FakeTensor":
            return self

        def unsqueeze(self, _dim: int) -> "FakeTensor":
            return self

    monkeypatch.setattr(wrapper, "_preprocess_audio", lambda _audio: FakeTensor())
    return wrapper


def test_demucs_wrapper_passes_segment_argument(demucs_test_env: DemucsWrapper, monkeypatch: pytest.MonkeyPatch) -> None:
    import mp3paramidi.models.demucs_wrapper as demucs_module

    called = {}

    class DummyApplyOutput:
        def __init__(self) -> None:
            self.data = np.zeros((1, 2, 2, 4410), dtype=np.float32)

        def squeeze(self, axis: int) -> "DummyApplyOutput":
            self.data = np.squeeze(self.data, axis=axis)
            return self

        def cpu(self) -> "DummyApplyOutput":
            return self

        def numpy(self) -> np.ndarray:
            return self.data

    def fake_apply_model(model: object, mix_batch: object, **kwargs: object) -> DummyApplyOutput:
        called["segment"] = kwargs.get("segment")
        return DummyApplyOutput()

    monkeypatch.setattr(demucs_module, "apply_model", fake_apply_model)

    demucs_test_env.separate(
        SimpleNamespace(
            samples=np.zeros((2, 4410), dtype=np.float32),
            metadata=SimpleNamespace(sample_rate=44100),
        )
    )

    assert called["segment"] == pytest.approx(demucs_test_env.segment_duration)


def test_demucs_wrapper_requires_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    import mp3paramidi.models.demucs_wrapper as demucs_module

    monkeypatch.setattr(demucs_module, "torch", None)
    monkeypatch.setattr(demucs_module, "torchaudio", None)
    monkeypatch.setattr(demucs_module, "get_model", None)

    with pytest.raises(ModelLoadError):
        DemucsWrapper(model_name="htdemucs")
