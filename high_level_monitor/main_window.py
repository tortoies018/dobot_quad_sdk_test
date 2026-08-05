"""主窗口——组装 UI 并连接 gRPC 数据信号和 DDS 四相机"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout

from generated.ui_main_window import Ui_MainWindow
from data_panel import DataPanel
from viz_3d import Viz3D
from camera_view import CameraView
from robot_poller import RobotPoller
from dds_camera import FourCamWorker


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # ---- 左侧：数据面板 ----
        self._panel = DataPanel()
        self.scrollArea.setWidget(self._panel)
        self.scrollArea.setWidgetResizable(True)

        # ---- 右侧：上方 3D 轨迹 + 下方四相机 ----
        self._viz3d = Viz3D()
        self._cam_view = CameraView()

        self._cam_view.setMaximumHeight(400)

        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(self._viz3d)
        right_split.addWidget(self._cam_view)
        right_split.setStretchFactor(0, 7)
        right_split.setStretchFactor(1, 1)
        right_split.setStyleSheet("QSplitter::handle { background:#42464c; height:2px; }")

        self.mainLayout.addWidget(right_split)
        self.mainLayout.setStretch(0, 3)
        self.mainLayout.setStretch(1, 7)

        # ---- gRPC 轮询 ----
        self._poller = RobotPoller(addr="10.30.12.196:50051", interval=0.2)
        self._poller.info_ready.connect(self._panel.update_info)
        self._poller.pose_ready.connect(self._panel.update_pose)
        self._poller.pose_ready.connect(self._viz3d.update_pose)
        self._poller.joints_ready.connect(self._panel.update_joints)
        self._poller.grf_ready.connect(self._panel.update_grf)
        self._poller.status_msg.connect(self.statusbar.showMessage)
        self._poller.connected.connect(self._on_connected)
        self._poller.start()

        # ---- DDS 四相机 ----
        cam_cfg = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        self._four_cam = FourCamWorker(config_path=cam_cfg)
        self._four_cam.frame_ready.connect(self._cam_view.update_frame)
        self._four_cam.log_msg.connect(self.statusbar.showMessage)
        self._four_cam.start()

        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_status_time)
        self._time_timer.start(1000)
        self._connected = False

    def _on_connected(self, ok):
        self._connected = ok
        if ok:
            self.statusbar.setStyleSheet("color: #69f0ae; background: #26292d; font: 12px;")
        else:
            self.statusbar.setStyleSheet("color: #ef5350; background: #26292d; font: 12px;")

    def _update_status_time(self):
        now = datetime.now().strftime("%H:%M:%S")
        if not self._connected:
            self.statusbar.showMessage(f"[未连接]  等待 {self._poller._addr} ...  {now}")

    def closeEvent(self, event):
        self._poller.stop(); self._poller.wait(2000)
        self._four_cam.stop(); self._four_cam.wait(2000)
        super().closeEvent(event)
