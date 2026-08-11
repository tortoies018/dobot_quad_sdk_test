#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

"$SCRIPT_DIR/build_ubuntu.sh"
"$SCRIPT_DIR/build_windows_portable.sh"

cp "$SCRIPT_DIR/README.txt" "$APP_DIR/release/README.txt"
(
    cd "$APP_DIR/release"
    rm -f ubuntu-x86_64.zip windows-x64.zip
    rm -f ubuntu-x86_64.zip.part-* windows-x64.zip.part-*
    rm -f SHA256SUMS.txt SHA256SUMS.parts.txt
    zip -1qr ubuntu-x86_64.zip ubuntu-x86_64
    zip -1qr windows-x64.zip windows-x64
    sha256sum ubuntu-x86_64.zip windows-x64.zip > SHA256SUMS.txt
    split --bytes=90M --numeric-suffixes=1 --suffix-length=3 \
        ubuntu-x86_64.zip ubuntu-x86_64.zip.part-
    split --bytes=90M --numeric-suffixes=1 --suffix-length=3 \
        windows-x64.zip windows-x64.zip.part-
    sha256sum ./*.zip.part-* > SHA256SUMS.parts.txt
    rm -f ubuntu-x86_64.zip windows-x64.zip
)
