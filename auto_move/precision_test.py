"""SDK 指令精度自动测试程序入口。

复用 auto_move 的连接、轨迹、日志和窗口，只默认选择自动精度测试模式。
"""

import sys

from PySide6.QtWidgets import QApplication

from main import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad SDK 指令精度测试")
    window = MainWindow()
    window.setWindowTitle("Dobot Quad SDK 指令精度自动测试")
    index = window.mode_combo.findData("precision_test")
    if index >= 0:
        window.mode_combo.setCurrentIndex(index)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
