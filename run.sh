#!/usr/bin/env bash
# Starts the FiveM Artifact Downloader TUI. Run ./install.sh first.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -x ".venv/bin/python3" ]; then
    echo "Virtual environment not found. Run ./install.sh first."
    exit 1
fi

.venv/bin/python3 fivem_tui.py
