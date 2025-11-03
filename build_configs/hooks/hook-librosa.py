"""PyInstaller hook ensuring librosa ships with required dependencies."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Librosa dynamically loads a wide range of scientific submodules at runtime.
# Explicitly enumerate them so the frozen application remains functional.
hiddenimports = collect_submodules("librosa") + [
    "numba",
    "numba.core",
    "numba.typed",
    "llvmlite",
    "scipy",
    "scipy.signal",
    "scipy.ndimage",
    "scipy.interpolate",
    "joblib",
    "resampy",
    "audioread",
    "pooch",
]

datas = collect_data_files("librosa")
