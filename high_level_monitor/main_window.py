"""主窗口——组装 UI 并连接 gRPC 数据信号"""

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel

from generated.ui_main_window import Ui_MainWindow
from data_panel import DataPanel
from robot_poller import RobotPoller


class MainWindow(QMainWindow, Ui_MainWindow):
    """应用程序主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # 创建数据显示面板
        self._panel = DataPanel()
        self.panelLayout.addWidget(self._panel)

        # 创建 gRPC 轮询线程（默认连接 192.168.5.2:50051）
        self._poller = RobotPoller(addr="192.168.5.2:50051", interval=0.2)

        # 连接信号
        self._poller.info_ready.connect(self._panel.update_info)
        self._poller.pose_ready.connect(self._panel.update_pose)
        self._poller.joints_ready.connect(self._panel.update_joints)
        self._poller.grf_ready.connect(self._panel.update_grf)
        self._poller.status_msg.connect(self.statusbar.showMessage)
        self._poller.connected.connect(self._on_connected)

        # 启动轮询
        self._poller.start()

        # 连接后定时更新状态栏时间
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_status_time)
        self._time_timer.start(1000)

        self._connected = False

    def _on_connected(self, ok):
        """连接状态变化回调"""
        self._connected = ok
        if ok:
            self.statusbar.setStyleSheet("color: #0f0; background: #222; font: 12px;")
        else:
            self.statusbar.setStyleSheet("color: #f44; background: #222; font: 12px;")

    def _update_status_time(self):
        """每秒更新状态栏右侧的时间"""
        now = datetime.now().strftime("%H:%M:%S")
        if not self._connected:
            self.statusbar.showMessage(f"[未连接]  等待连接 {self._poller._addr} ...  {now}")
        # 连接后状态栏由 poller 的 status_msg 更新，此处不再覆盖

    def closeEvent(self, event):
        """窗口关闭时停止后台线程"""
        self._poller.stop()
        self._poller.wait(2000)
        super().closeEvent(event)
