#!/usr/bin/env bash
set -u
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$HERE/MH4_HTTP_Auto_Move/MH4_HTTP_Auto_Move" "$@"
STATUS=$?
echo
echo "程序退出，状态码：$STATUS"
read -r -p "按 Enter 键关闭..." _
exit "$STATUS"
