#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SDK_DIR="$(cd -- "$APP_DIR/../dobot_quad_sdk/high_level/python" && pwd)"
OUTPUT_DIR="$APP_DIR/release/ubuntu-x86_64"
WORK_DIR="$APP_DIR/.packaging-build/ubuntu"
VENV_DIR="$APP_DIR/.packaging-venv"
SYSTEM_DEPS_DIR="$WORK_DIR/system-deps"

if [[ ! -x "$VENV_DIR/bin/pyinstaller" ]]; then
    echo "请先运行 ./packaging/setup_build_env.sh" >&2
    exit 1
fi

mkdir -p "$WORK_DIR"
rm -rf "$OUTPUT_DIR"

"$VENV_DIR/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --windowed \
    --onedir \
    --name MH4_HTTP_Auto_Move \
    --distpath "$OUTPUT_DIR" \
    --workpath "$WORK_DIR/work" \
    --specpath "$WORK_DIR" \
    --paths "$APP_DIR" \
    --paths "$SDK_DIR" \
    --hidden-import dobot_quad \
    --collect-all dobot_quad \
    --collect-all OpenGL \
    "$APP_DIR/main.py"

if ! ldconfig -p 2>/dev/null | grep -q 'libxcb-cursor.so.0'; then
    XCB_CURSOR_LIB="$(find "$SYSTEM_DEPS_DIR" -type f -name 'libxcb-cursor.so.0*' -print -quit 2>/dev/null || true)"
    if [[ -z "$XCB_CURSOR_LIB" ]]; then
        mkdir -p "$SYSTEM_DEPS_DIR"
        (cd "$SYSTEM_DEPS_DIR" && apt-get download libxcb-cursor0)
        XCB_CURSOR_DEB="$(find "$SYSTEM_DEPS_DIR" -maxdepth 1 -type f -name 'libxcb-cursor0_*.deb' -print -quit)"
        dpkg-deb -x "$XCB_CURSOR_DEB" "$SYSTEM_DEPS_DIR"
        XCB_CURSOR_LIB="$(find "$SYSTEM_DEPS_DIR" -type f -name 'libxcb-cursor.so.0*' -print -quit)"
    fi
    cp -L "$XCB_CURSOR_LIB" "$OUTPUT_DIR/MH4_HTTP_Auto_Move/_internal/libxcb-cursor.so.0"
fi

cp "$SCRIPT_DIR/launchers/启动_MH4_HTTP_Auto_Move.sh" "$OUTPUT_DIR/"
cp "$SCRIPT_DIR/launchers/诊断启动.sh" "$OUTPUT_DIR/"
cp "$SCRIPT_DIR/README.txt" "$OUTPUT_DIR/使用说明.txt"
chmod +x "$OUTPUT_DIR/启动_MH4_HTTP_Auto_Move.sh" "$OUTPUT_DIR/诊断启动.sh"
