from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow

from generated.ui_main_window import Ui_MainWindow
from camera_widget import CameraWidget
from dashboard_widget import DashboardWidget
from dds_worker import DDSSubscriber, CAMERA_CONFIGS


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.tabWidget.clear()

        self._cam_views = []
        for i, cfg in enumerate(CAMERA_CONFIGS):
            w = CameraWidget(cfg["name"], cfg["topic"])
            row, col = divmod(i, 2)
            self.cameraGrid.addWidget(w, row, col)
            self._cam_views.append(w)

        self._dashboard = DashboardWidget()
        self.tabWidget.addTab(self._dashboard, "仪表盘")

        self._data_count = 0
        self._no_data_timer = QTimer(self)
        self._no_data_timer.timeout.connect(self._check_data_timeout)
        self._no_data_timer.start(5000)

        config_path = str(
            Path(__file__).resolve().parent / "config" / "dds_config.yaml"
        )
        self._sub = DDSSubscriber(config_path)
        self._sub.frame_ready.connect(self._on_frame)
        self._sub.imu_ready.connect(self._on_any_data)
        self._sub.battery_ready.connect(self._on_any_data)
        self._sub.motor_ready.connect(self._on_any_data)
        self._sub.voice_ready.connect(self._on_any_data)
        self._sub.log_msg.connect(self.statusbar.showMessage)
        self._sub.start()

    def _on_any_data(self, *args):
        self._data_count += 1

    def _check_data_timeout(self):
        if self._data_count == 0:
            self.statusbar.showMessage(
                "WARNING: 未收到 DDS 数据。确认: 1) 网线连接 2) 机器人开机 3) cyclonedds ps 可发现"
            )

    def _on_frame(self, idx, img):
        if 0 <= idx < len(self._cam_views):
            self._cam_views[idx].update_frame(img)
        self._on_any_data()

    def closeEvent(self, event):
        self._sub.stop()
        self._sub.wait(2000)
        super().closeEvent(event)
