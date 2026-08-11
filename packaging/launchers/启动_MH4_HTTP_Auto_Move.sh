#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/MH4_HTTP_Auto_Move/MH4_HTTP_Auto_Move" "$@"
