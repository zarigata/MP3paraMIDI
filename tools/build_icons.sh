#!/usr/bin/env bash
# Generate platform icon assets from the master SVG source.
# Usage: ./tools/build_icons.sh [source_svg]

set -euo pipefail

SRC=${1:-assets/master.svg}
OUT_DIR="assets/icons"
PNG_DIR="${OUT_DIR}/png"
ICO_DIR="${OUT_DIR}/ico"
ICONSET_DIR="${OUT_DIR}/icns/MP3paraMIDI.iconset"

SIZES_ICO=(16 24 32 48 64 128 256)
SIZES_PNG=(16 32 48 64 128 256 512 1024)

if ! command -v inkscape >/dev/null 2>&1; then
  echo "Error: inkscape is required but not found in PATH." >&2
  exit 1
fi

if ! command -v convert >/dev/null 2>&1; then
  echo "Error: ImageMagick 'convert' is required but not found in PATH." >&2
  exit 1
fi

mkdir -p "${PNG_DIR}" "${ICO_DIR}" "${ICONSET_DIR}"
rm -f "${PNG_DIR}"/*.png "${ICO_DIR}"/*.ico
rm -f "${ICONSET_DIR}"/*

for size in "${SIZES_PNG[@]}"; do
  inkscape "${SRC}" -o "${PNG_DIR}/icon_${size}.png" -w "${size}" -h "${size}"
done

ICO_INPUTS=()
for size in "${SIZES_ICO[@]}"; do
  png_file="${PNG_DIR}/icon_${size}.png"
  if [[ -f "${png_file}" ]]; then
    ICO_INPUTS+=("${png_file}")
  fi
done

convert "${ICO_INPUTS[@]}" -define icon:auto-resize -colors 256 "${ICO_DIR}/mp3paramidi.ico"

# Populate macOS iconset assets
cp "${PNG_DIR}/icon_16.png"  "${ICONSET_DIR}/icon_16x16.png"
cp "${PNG_DIR}/icon_32.png"  "${ICONSET_DIR}/icon_16x16@2x.png"
cp "${PNG_DIR}/icon_32.png"  "${ICONSET_DIR}/icon_32x32.png"
cp "${PNG_DIR}/icon_64.png"  "${ICONSET_DIR}/icon_32x32@2x.png"
cp "${PNG_DIR}/icon_128.png" "${ICONSET_DIR}/icon_128x128.png"
cp "${PNG_DIR}/icon_256.png" "${ICONSET_DIR}/icon_128x128@2x.png"
cp "${PNG_DIR}/icon_256.png" "${ICONSET_DIR}/icon_256x256.png"
cp "${PNG_DIR}/icon_512.png" "${ICONSET_DIR}/icon_256x256@2x.png"
cp "${PNG_DIR}/icon_512.png" "${ICONSET_DIR}/icon_512x512.png"
cp "${PNG_DIR}/icon_1024.png" "${ICONSET_DIR}/icon_512x512@2x.png"

mkdir -p "${OUT_DIR}/icns"
if command -v iconutil >/dev/null 2>&1; then
  iconutil -c icns "${ICONSET_DIR}" -o "${OUT_DIR}/icns/mp3paramidi.icns"
elif command -v png2icns >/dev/null 2>&1; then
  png2icns "${OUT_DIR}/icns/mp3paramidi.icns" "${ICONSET_DIR}"/*.png
else
  echo "Warning: Neither iconutil nor png2icns found. ICNS generation skipped." >&2
fi

echo "Icon generation complete: ${OUT_DIR}"
