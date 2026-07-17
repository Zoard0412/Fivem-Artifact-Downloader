#!/usr/bin/env bash
# Sets up a local virtual environment and installs dependencies.
# Works on macOS and Linux (incl. Debian/Ubuntu). If Python (or, on macOS,
# Homebrew) is missing, this script offers to install it for you.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

confirm() {
    # confirm "question" -> exit 0 (yes) / 1 (no); Enter defaults to yes
    read -r -p "$1 [Y/n] " reply
    case "$reply" in
        [nN]*) return 1 ;;
        *) return 0 ;;
    esac
}

install_python_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew (the macOS package manager) was not found."
        if confirm "Install Homebrew now?"; then
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            # Homebrew installs to /opt/homebrew (Apple Silicon) or /usr/local (Intel);
            # make it available in this shell session right away.
            if [ -x /opt/homebrew/bin/brew ]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [ -x /usr/local/bin/brew ]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi
        else
            echo "Cannot continue without Python. Install it manually from https://www.python.org/downloads/macos/"
            exit 1
        fi
    fi
    echo "Installing Python via Homebrew..."
    brew install python
}

install_python_debian() {
    echo "Python 3 was not found."
    if confirm "Install python3, python3-venv and python3-pip via apt now? (requires sudo)"; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip
    else
        echo "Cannot continue without Python. Install it manually:"
        echo "  sudo apt install python3 python3-venv python3-pip"
        exit 1
    fi
}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    case "$(uname -s)" in
        Darwin)
            install_python_macos
            ;;
        Linux)
            if command -v apt-get >/dev/null 2>&1; then
                install_python_debian
            else
                echo "Error: '$PYTHON_BIN' was not found, and this script only automates"
                echo "installation on Debian/Ubuntu (apt) and macOS (Homebrew)."
                echo "Please install Python 3.10+ manually for your distribution."
                exit 1
            fi
            ;;
        *)
            echo "Error: '$PYTHON_BIN' was not found. Install Python 3.10+ manually."
            exit 1
            ;;
    esac
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Error: Python installation did not succeed (or '$PYTHON_BIN' is still not on PATH)."
    echo "Open a new terminal and re-run this script, or install Python manually."
    exit 1
fi

echo "Creating virtual environment in .venv ..."
"$PYTHON_BIN" -m venv .venv

if [ ! -x ".venv/bin/python3" ]; then
    echo ""
    echo "The virtual environment looks broken (.venv/bin/python3 is missing)."
    if command -v apt-get >/dev/null 2>&1; then
        echo "On Debian/Ubuntu this usually means the venv module isn't installed."
        PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || true)"
        PKG="python3-venv"
        [ -n "$PY_VER" ] && PKG="python${PY_VER}-venv"
        if confirm "Install $PKG via apt now? (requires sudo)"; then
            sudo apt-get install -y "$PKG"
            rm -rf .venv
            "$PYTHON_BIN" -m venv .venv
        fi
    fi
    if [ ! -x ".venv/bin/python3" ]; then
        echo "Still could not create a working virtual environment. Install the venv"
        echo "module for your Python version manually, delete .venv, and try again."
        exit 1
    fi
fi

echo "Installing dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo ""
echo "Installation complete. Start the app with ./run.sh"
