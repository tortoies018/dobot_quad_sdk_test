"""SDK 指令精度测试程序入口。

复用 auto_move 窗口，默认在“直线行走”页签中开启精度测量。
"""

import sys

from PySide6.QtWidgets import QApplication

from main import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad SDK 指令精度测试")
    window = MainWindow()
    window.setWindowTitle("Dobot Quad SDK 指令精度测试")
    window.command_tabs.setCurrentIndex(0)
    window.precision_checks[0].setChecked(True)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
