#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SDK_DIR="$(cd -- "$APP_DIR/../dobot_quad_sdk/high_level/python" && pwd)"
OUTPUT_DIR="$APP_DIR/release/windows-x64"
DOWNLOAD_DIR="$APP_DIR/.packaging-build/windows/downloads"
WHEELS_DIR="$APP_DIR/.packaging-build/windows/wheels"
PYTHON_VERSION="3.10.11"
PYTHON_ZIP="python-${PYTHON_VERSION}-embed-amd64.zip"

mkdir -p "$DOWNLOAD_DIR" "$WHEELS_DIR"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$DOWNLOAD_DIR/$PYTHON_ZIP" ]]; then
    curl --fail --location --output "$DOWNLOAD_DIR/$PYTHON_ZIP" \
        "https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_ZIP}"
fi
python3 -m zipfile -e "$DOWNLOAD_DIR/$PYTHON_ZIP" "$OUTPUT_DIR"

python3 -m pip download \
    --only-binary=:all: \
    --platform win_amd64 \
    --implementation cp \
    --python-version 310 \
    --abi cp310 \
    --dest "$WHEELS_DIR" \
    -r "$SCRIPT_DIR/requirements-runtime.txt"

for wheel in "$WHEELS_DIR"/*.whl; do
    python3 -m zipfile -e "$wheel" "$OUTPUT_DIR"
done

cp "$APP_DIR"/*.py "$OUTPUT_DIR/"
cp -R "$SDK_DIR/dobot_quad" "$OUTPUT_DIR/"
cp "$SCRIPT_DIR/launchers/启动_MH4_HTTP_Auto_Move.cmd" "$OUTPUT_DIR/"
cp "$SCRIPT_DIR/launchers/诊断启动.cmd" "$OUTPUT_DIR/"
cp "$SCRIPT_DIR/launchers/sitecustomize.py" "$OUTPUT_DIR/"
cp "$SCRIPT_DIR/README.txt" "$OUTPUT_DIR/使用说明.txt"
sed -i 's/^#import site/import site/' "$OUTPUT_DIR/python310._pth"
cp "$OUTPUT_DIR/pythonw.exe" "$OUTPUT_DIR/MH4_HTTP_Auto_Move.exe"
