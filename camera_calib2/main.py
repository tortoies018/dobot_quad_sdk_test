"""双相机标定主程序——前后相机同时显示、独立标定"""

import sys
from pathlib import Path

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow

from generated.ui_main_window import Ui_MainWindow
from dual_cam_worker import DualCamWorker
from calib_engine import CalibEngine
from checkerboard_utils import get_calib_config


class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        cfg = get_calib_config()
        self._engine_front = CalibEngine("camera2", cfg["pattern_size"], cfg["square_size_mm"])
        self._engine_rear = CalibEngine("camera3", cfg["pattern_size"], cfg["square_size_mm"])

        self._capture_front = False
        self._capture_rear = False
        self._busy_front = False
        self._busy_rear = False

        # DDS 双相机订阅
        dds_cfg = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        self._cam = DualCamWorker(config_path=dds_cfg)
        self._cam.front_ready.connect(self._on_front)
        self._cam.rear_ready.connect(self._on_rear)
        self._cam.log_msg.connect(self.statusbar.showMessage)
        self._cam.start()

        # 按钮信号
        self.btnCapFront.clicked.connect(lambda: setattr(self, "_capture_front", True))
        self.btnCapRear.clicked.connect(lambda: setattr(self, "_capture_rear", True))
        self.btnCalFront.clicked.connect(self._calibrate_front)
        self.btnCalRear.clicked.connect(self._calibrate_rear)
        self.btnResetFront.clicked.connect(self._reset_front)
        self.btnResetRear.clicked.connect(self._reset_rear)

    # ─── 帧处理 ──────────────────────────────────────

    def _process(self, img, engine, label_view, label_info, label_count,
                 btn_cal, capture_flag):
        """通用帧处理：检测 + 显示 + 捕获"""
        result, detected, _ = engine.detect_and_capture(img, capture_flag)

        # 显示画面
        h, w, ch = result.shape
        qt = QImage(result.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(qt).scaled(
            label_view.width(), label_view.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label_view.setPixmap(pix)

        # 更新信息
        if detected:
            label_info.setText("✅ 检测到棋盘格")
            label_info.setStyleSheet("color: #0f0; font: 12px; padding: 2px;")
        else:
            label_info.setText("❌ 未检测到棋盘格")
            label_info.setStyleSheet("color: #f44; font: 12px; padding: 2px;")

        label_count.setText(f"已捕获: {engine.frame_count} 帧")
        btn_cal.setEnabled(engine.ready_to_calibrate)

    def _on_front(self, img):
        if self._busy_front:
            return
        self._busy_front = True
        try:
            self._process(img, self._engine_front,
                          self.viewFront, self.infoFront, self.countFront,
                          self.btnCalFront, self._capture_front)
        finally:
            self._capture_front = False
            self._busy_front = False

    def _on_rear(self, img):
        if self._busy_rear:
            return
        self._busy_rear = True
        try:
            self._process(img, self._engine_rear,
                          self.viewRear, self.infoRear, self.countRear,
                          self.btnCalRear, self._capture_rear)
        finally:
            self._capture_rear = False
            self._busy_rear = False

    # ─── 标定 ────────────────────────────────────────

    def _calibrate_front(self):
        self._do_calibrate(self._engine_front, self.textResultFront, "前置 camera2")

    def _calibrate_rear(self):
        self._do_calibrate(self._engine_rear, self.textResultRear, "后置 camera3")

    def _do_calibrate(self, engine, label_result, name):
        result = engine.calibrate()
        if result is None:
            self.statusbar.showMessage(f"{name}: 至少需要 3 帧")
            return

        error, mtx, dist = result
        fx, fy = mtx[0, 0], mtx[1, 1]
        cx, cy = mtx[0, 2], mtx[1, 2]
        k1, k2, p1, p2, k3 = dist.ravel()

        text = (
            f"重投影误差: {error:.4f} px\n"
            f"fx = {fx:.2f}    fy = {fy:.2f}\n"
            f"cx = {cx:.2f}    cy = {cy:.2f}\n"
            f"k1 = {k1:.6f}  k2 = {k2:.6f}\n"
            f"p1 = {p1:.6f}  p2 = {p2:.6f}\n"
            f"k3 = {k3:.6f}"
        )
        label_result.setText(text)

        out = engine.save_result(error, mtx, dist)
        self.statusbar.showMessage(f"{name} 标定完成 → {out.name}")

    # ─── 重置 ────────────────────────────────────────

    def _reset_front(self):
        self._engine_front.reset()
        self.countFront.setText("已捕获: 0 帧")
        self.infoFront.setText("检测结果: —")
        self.textResultFront.setText("等待标定...")
        self.btnCalFront.setEnabled(False)
        self.statusbar.showMessage("前置: 已重置")

    def _reset_rear(self):
        self._engine_rear.reset()
        self.countRear.setText("已捕获: 0 帧")
        self.infoRear.setText("检测结果: —")
        self.textResultRear.setText("等待标定...")
        self.btnCalRear.setEnabled(False)
        self.statusbar.showMessage("后置: 已重置")

    def closeEvent(self, event):
        self._cam.stop()
        self._cam.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad 双相机标定")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
