"""相机标定主程序——支持 DDS 和 OpenCV 两种信号源"""

import sys
from pathlib import Path

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow, QComboBox, QHBoxLayout, QLabel

from generated.ui_main_window import Ui_MainWindow
from calib_worker import CalibWorker


class MainWindow(QMainWindow, Ui_MainWindow):
    """相机标定主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # 在控制栏添加信号源选择
        source_box = QComboBox()
        source_box.addItems(CalibWorker.SOURCES)
        source_box.setCurrentText("DDS 前置 RGB")
        source_box.setStyleSheet("""
            QComboBox { background:#26292d; color:#fff; padding:4px 8px;
                        border:1px solid #55585e; border-radius:4px; font:13px; }
            QComboBox::drop-down { border:none; }
            QComboBox QAbstractItemView { background-color:#2b2d31; color:#f5f5f5; border:1px solid #55585e; outline:none; }
            QComboBox QAbstractItemView::item { color:#f5f5f5; background-color:#2b2d31; padding:6px 8px; }
            QComboBox QAbstractItemView::item:hover { color:#fff; background-color:#3a3d42; }
            QComboBox QAbstractItemView::item:selected { color:#fff; background-color:#29b6f6; }
        """)
        self.controlLayout.insertWidget(0, QLabel("信号源:"))
        self.controlLayout.insertWidget(1, source_box)

        # 标定工作线程
        cfg_path = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        self._worker = CalibWorker(config_path=cfg_path)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.corners_detected.connect(self._on_corners)
        self._worker.calib_done.connect(self._on_calib_done)
        self._worker.log_msg.connect(self.statusbar.showMessage)
        self._worker.start()

        # 信号连接
        self.btnCapture.clicked.connect(self._on_capture)
        self.btnCalibrate.clicked.connect(self._on_calibrate)
        self.btnReset.clicked.connect(self._on_reset)
        source_box.currentTextChanged.connect(self._on_source_change)

        self.btnCalibrate.setEnabled(False)
        self._prev_source = "DDS 前置 RGB"

    def _on_frame(self, cv_img):
        """显示帧"""
        h, w, ch = cv_img.shape
        qt = QImage(cv_img.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(qt).scaled(
            self.labelCameraView.width(), self.labelCameraView.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.labelCameraView.setPixmap(pix)

    def _on_corners(self, corners, w, h):
        self.labelDetectResult.setText(f"✅ 检测到棋盘格: {w}×{h}")
        self.btnCalibrate.setEnabled(len(self._worker._img_points) >= 3)

    def _on_capture(self):
        self._worker.capture_frame()
        self.btnCapture.setEnabled(False)
        self.btnCapture.setText("捕获中...")
        QTimer.singleShot(500, self._restore_capture_btn)

    def _restore_capture_btn(self):
        self.btnCapture.setEnabled(True)
        self.btnCapture.setText("捕获帧")
        self.listFrames.addItem(f"帧 {self._worker._frame_count}  ✓")
        self.listFrames.scrollToBottom()

    def _on_calibrate(self):
        self._worker.calibrate()

    def _on_reset(self):
        self._worker.reset()
        self.listFrames.clear()
        self.labelResult.setText("等待标定...")
        self.btnCalibrate.setEnabled(False)
        self.labelDetectResult.setText("检测结果")

    def _on_source_change(self, name):
        """切换信号源"""
        if name == self._prev_source:
            return
        self._prev_source = name
        self._on_reset()
        self._worker.stop()
        self._worker.wait(1000)
        cfg_path = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        self._worker = CalibWorker(config_path=cfg_path)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.corners_detected.connect(self._on_corners)
        self._worker.calib_done.connect(self._on_calib_done)
        self._worker.log_msg.connect(self.statusbar.showMessage)
        self._worker.set_source(name)
        self._worker.start()

    def _on_calib_done(self, error, camera_matrix, dist_coeffs):
        fx = camera_matrix[0, 0]
        fy = camera_matrix[1, 1]
        cx = camera_matrix[0, 2]
        cy = camera_matrix[1, 2]
        k1, k2, p1, p2, k3 = dist_coeffs.ravel()

        self.labelResult.setText(
            f"重投影误差: {error:.4f} px\n"
            f"相机矩阵:\n"
            f"  fx = {fx:.4f}    fy = {fy:.4f}\n"
            f"  cx = {cx:.4f}    cy = {cy:.4f}\n"
            f"畸变系数:\n"
            f"  k1 = {k1:.6f}  k2 = {k2:.6f}  p1 = {p1:.6f}\n"
            f"  p2 = {p2:.6f}  k3 = {k3:.6f}\n"
        )
        self.statusbar.showMessage("标定完成 ✓")

    def closeEvent(self, event):
        self._worker.stop()
        self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad 相机标定")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
