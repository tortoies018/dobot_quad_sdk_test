#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$APP_DIR/.packaging-venv"

python3 -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install "PyInstaller==6.15.0"
"$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements-runtime.txt"
