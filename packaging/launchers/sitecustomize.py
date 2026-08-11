"""让重命名后的嵌入式 pythonw.exe 直接启动图形程序。"""

from __future__ import annotations

import os
import sys
import traceback


_APP_EXE = "mh4_http_auto_move.exe"


def _exit_code(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return max(0, min(255, value))
    return 1


def _show_startup_error(message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            message[-12000:],
            "MH4 HTTP Auto Move 启动失败",
            0x10,
        )
    except Exception:
        pass


if os.name == "nt" and os.path.basename(sys.executable).casefold() == _APP_EXE:
    try:
        from main import main

        main()
    except SystemExit as exc:
        os._exit(_exit_code(exc.code))
    except BaseException:
        _show_startup_error(traceback.format_exc())
        os._exit(1)
