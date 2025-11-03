# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for the standard (non-AI) MP3paraMIDI build."""

import sys
from pathlib import Path

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Standard build excludes heavy AI dependencies for a smaller download.
BUNDLE_AI = False

ROOT = Path(__file__).resolve().parent.parent
SRC_ENTRY = ROOT / "src" / "mp3paramidi" / "__main__.py"
ICON_ROOT = ROOT / "assets" / "icons"
VERSION_FILE = ROOT / "build_configs" / "version_info.txt"
HOOKS_PATH = [str(ROOT / "build_configs" / "hooks")]

# Bundle data files required by the audio stack (waveform samples, etc.).
datas = []
datas += collect_data_files("librosa")
datas += collect_data_files("soundfile")
datas += collect_data_files("pygame")
datas.append((str(ICON_ROOT), "icons"))

# Hidden imports ensure PyQt6 and scientific dependencies are shipped.
hiddenimports = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "numba",
    "scipy",
    "joblib",
    "llvmlite",
]

for package in ("librosa", "soundfile", "pygame", "mido", "pretty_midi"):
    hiddenimports += collect_submodules(package)

hiddenimports += [
    "numba.core",
    "numba.typed",
    "scipy.signal",
    "scipy.ndimage",
    "scipy.interpolate",
]

if BUNDLE_AI:
    for package in ("torch", "torchaudio", "demucs", "basic_pitch"):
        datas += collect_data_files(package)
        hiddenimports += collect_submodules(package)
    hiddenimports += [
        "torch.nn",
        "torch.optim",
        "torchaudio.transforms",
        "torchaudio.functional",
        "scipy",
    ]

analysis = Analysis(
    [str(SRC_ENTRY)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=HOOKS_PATH,
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "PyQt5", "PySide2"],
    cipher=block_cipher,
    noarchive=False,
)

python_zip = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher, optimize=0)

if sys.platform == "win32":
    executable_icon = ICON_ROOT / "ico" / "mp3paramidi.ico"
elif sys.platform == "darwin":
    executable_icon = ICON_ROOT / "icns" / "mp3paramidi.icns"
else:
    executable_icon = ICON_ROOT / "png" / "icon_256.png"

executable = EXE(
    python_zip,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="mp3paramidi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(executable_icon),
    version=str(VERSION_FILE),
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Collect into onedir layout for faster startup and easier debugging.
coll = COLLECT(
    executable,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="mp3paramidi-standard",
)

if sys.platform == "darwin":
    app_bundle = BUNDLE(
        executable,
        name="mp3paramidi.app",
        icon=str(ICON_ROOT / "icns" / "mp3paramidi.icns"),
        bundle_identifier="com.zarigata.mp3paramidi",
        info_plist={
            "CFBundleName": "MP3paraMIDI",
            "CFBundleDisplayName": "MP3paraMIDI",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
