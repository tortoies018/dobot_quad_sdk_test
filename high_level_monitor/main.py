"""Dobot Quad 高级状态监控——通过 gRPC 实时显示机器人状态"""

import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def main():
    """程序入口：创建 Qt 应用并显示主窗口"""
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad 高级监控")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
