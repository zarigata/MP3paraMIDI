#!/usr/bin/env bash
# Build a Linux AppImage from the PyInstaller onedir output.

set -euo pipefail

PYINSTALLER_DIST=${1:-dist/mp3paramidi-standard}
OUTPUT_DIR=${2:-dist}
VERSION=${3:-0.1.0}
VARIANT=${4:-standard}

case "${VARIANT}" in
  ai|AI)
    VARIANT="ai"
    VARIANT_LABEL="AI"
    ;;
  *)
    VARIANT="standard"
    VARIANT_LABEL="Standard"
    ;;
esac

export APPIMAGE_EXTRACT_AND_RUN=${APPIMAGE_EXTRACT_AND_RUN:-1}

APPDIR="${OUTPUT_DIR}/AppDir"

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/lib"

cp -r "${PYINSTALLER_DIST}"/* "${APPDIR}/usr/bin/"

cp build_configs/linux/mp3paramidi.desktop "${APPDIR}/"
cp assets/icons/png/icon_256.png "${APPDIR}/mp3paramidi.png"
ln -sf mp3paramidi.png "${APPDIR}/.DirIcon"

cp build_configs/linux/AppRun "${APPDIR}/"
chmod +x "${APPDIR}/AppRun"

LINUXDEPLOY="linuxdeploy-x86_64.AppImage"
if [[ ! -x "${LINUXDEPLOY}" ]]; then
  wget -q https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/${LINUXDEPLOY}
  chmod +x "${LINUXDEPLOY}"
fi

./${LINUXDEPLOY} --appdir "${APPDIR}" --output appimage

mkdir -p "${OUTPUT_DIR}"
OUTPUT_IMAGE="MP3paraMIDI-v${VERSION}-Linux-${VARIANT_LABEL}-x86_64.AppImage"
find . -maxdepth 1 -name '*.AppImage' -print -quit | while read -r image; do
  mv "$image" "${OUTPUT_DIR}/${OUTPUT_IMAGE}"
  break
done

echo "AppImage created at ${OUTPUT_DIR}/${OUTPUT_IMAGE}"
