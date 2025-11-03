"""PyInstaller hook collecting pygame assets and binaries for MIDI playback."""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

hiddenimports = collect_submodules("pygame") + [
    "pygame.mixer",
    "pygame.midi",
    "pygame.time",
    "pygame.font",
]

datas = collect_data_files("pygame")

binaries = collect_dynamic_libs("pygame")
