#!/usr/bin/env bash
# Builds a standalone, single-file executable of the app for the CURRENT
# machine's OS and CPU architecture, using PyInstaller.
#
# IMPORTANT: PyInstaller cannot cross-compile. It only produces a binary for
# the OS + architecture it is actually running on. So from this machine you
# can only ever get ONE of the possible combinations (e.g. macOS/arm64 on an
# Apple Silicon Mac). To get the others (Windows x86_64/arm64, Linux
# x86_64/arm64, macOS x86_64, ...) you need to run this same script on a
# real or virtual machine of that OS/arch - or use a CI matrix build (e.g.
# GitHub Actions runners: windows-latest, windows-11-arm, ubuntu-latest,
# ubuntu-24.04-arm, macos-13 (Intel), macos-14 (Apple Silicon)).
#
# The output is placed in build/<os>-<arch>/ so multiple builds made on
# different machines (then copied together) don't collide, and each build
# is clearly labeled with what it actually is.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -x ".venv/bin/python3" ]; then
    echo "Virtual environment not found. Run ./install.sh first."
    exit 1
fi

case "$(uname -s)" in
    Darwin) OS_NAME="macos" ;;
    Linux) OS_NAME="linux" ;;
    *) OS_NAME="$(uname -s | tr '[:upper:]' '[:lower:]')" ;;
esac

case "$(uname -m)" in
    arm64|aarch64) ARCH_NAME="arm64" ;;
    x86_64|amd64) ARCH_NAME="x86_64" ;;
    *) ARCH_NAME="$(uname -m)" ;;
esac

APP_VERSION="$(.venv/bin/python3 -c "from version import __version__; print(__version__)")"
TAG="${OS_NAME}-${ARCH_NAME}"
BIN_NAME="fivem-artifact-downloader-${APP_VERSION}"
OUT_DIR="build/${TAG}-v${APP_VERSION}"
WORK_DIR="build/.pyinstaller-work"

echo "Building for: ${TAG} (v${APP_VERSION})"
echo "(This machine can only build for its own OS/architecture - see the"
echo " comment at the top of build.sh for how to get the other targets.)"
echo ""

echo "Installing PyInstaller into .venv (if missing)..."
.venv/bin/python3 -m pip install --quiet --upgrade pyinstaller

rm -rf "$OUT_DIR" "$WORK_DIR"
mkdir -p "$OUT_DIR"

.venv/bin/python3 -m PyInstaller \
    --onefile \
    --name "$BIN_NAME" \
    --distpath "$OUT_DIR" \
    --workpath "$WORK_DIR" \
    --specpath "$WORK_DIR" \
    fivem_tui.py

rm -rf "$WORK_DIR"

cat > "${OUT_DIR}/BUILD_INFO.txt" <<EOF
OS:           ${OS_NAME}
Architecture: ${ARCH_NAME}
App version:  ${APP_VERSION}
Built on:     $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Built with:   $(.venv/bin/python3 --version)

Built natively on this machine. PyInstaller does not cross-compile - a
binary built here only runs on ${OS_NAME}/${ARCH_NAME}.
EOF

echo ""
echo "Done. Output: ${OUT_DIR}/"
