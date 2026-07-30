"""主窗口——组装 UI 并连接 gRPC 数据信号和 DDS 相机"""

from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout

from generated.ui_main_window import Ui_MainWindow
from data_panel import DataPanel
from viz_3d import Viz3D
from camera_view import CameraView
from robot_poller import RobotPoller
from dds_camera import DDSCamera


class MainWindow(QMainWindow, Ui_MainWindow):
    """应用程序主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # ---- 左侧：数据面板 ----
        self._panel = DataPanel()
        self.scrollArea.setWidget(self._panel)
        self.scrollArea.setWidgetResizable(True)

        # ---- 右侧上方：3D 可视化 ----
        self._viz3d = Viz3D()

        # ---- 右侧下方：相机画面 ----
        self._cam_view = CameraView()

        # 右侧垂直分割 (3D 上, 相机下)
        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(self._viz3d)
        right_split.addWidget(self._cam_view)
        right_split.setStretchFactor(0, 5)
        right_split.setStretchFactor(1, 4)
        right_split.setStyleSheet("QSplitter::handle { background: #444; height: 2px; }")

        # 主布局：左侧数据面板 + 右侧垂直分割
        self.mainLayout.addWidget(right_split)
        self.mainLayout.setStretch(0, 3)  # 面板 30%
        self.mainLayout.setStretch(1, 7)  # 右侧 70%

        # ---- gRPC 轮询 (高层状态) ----
        self._poller = RobotPoller(addr="192.168.1.6:50051", interval=0.2)
        self._poller.info_ready.connect(self._panel.update_info)
        self._poller.pose_ready.connect(self._panel.update_pose)
        self._poller.pose_ready.connect(self._viz3d.update_pose)
        self._poller.joints_ready.connect(self._panel.update_joints)
        self._poller.grf_ready.connect(self._panel.update_grf)
        self._poller.status_msg.connect(self.statusbar.showMessage)
        self._poller.connected.connect(self._on_connected)
        self._poller.start()

        # ---- DDS 相机 (底层画面) ----
        self._dds_cam = DDSCamera(camera_index=0)
        self._dds_cam.frame_ready.connect(self._cam_view.update_frame)
        self._dds_cam.log_msg.connect(self.statusbar.showMessage)
        self._dds_cam.start()

        # 相机切换信号
        self._cam_view.cam_switch.currentIndexChanged.connect(self._on_cam_switch)

        # 状态栏时间
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_status_time)
        self._time_timer.start(1000)
        self._connected = False

    def _on_cam_switch(self, idx):
        """切换前置/后置相机"""
        self._dds_cam.switch(idx)

    def _on_connected(self, ok):
        self._connected = ok
        if ok:
            self.statusbar.setStyleSheet("color: #0f0; background: #222; font: 12px;")
        else:
            self.statusbar.setStyleSheet("color: #f44; background: #222; font: 12px;")

    def _update_status_time(self):
        now = datetime.now().strftime("%H:%M:%S")
        if not self._connected:
            self.statusbar.showMessage(f"[未连接]  等待连接 {self._poller._addr} ...  {now}")

    def closeEvent(self, event):
        self._poller.stop()
        self._poller.wait(2000)
        self._dds_cam.stop()
        self._dds_cam.wait(2000)
        super().closeEvent(event)
