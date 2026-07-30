"""AprilTag 双相机标定——使用 tagStandard41h12 检测与标定"""

import sys
from pathlib import Path

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow

from generated.ui_main_window import Ui_MainWindow
from board_generator import get_calib_config
from pupil_apriltags import Detector as ApriltagDetector


# ─── 标定引擎 ───────────────────────────────────────

class CalibEngine:
    """使用 AprilTag 检测的标定引擎"""

    def __init__(self, name, tag_grid, tag_size_mm, spacing_mm):
        self.name = name
        self.tag_grid = tag_grid          # (rows, cols)
        self.tag_size = tag_size_mm
        self.spacing = spacing_mm
        self._detector = ApriltagDetector(families="tagStandard41h12", nthreads=2)

        # 预计算世界坐标：tag 中心 + 四角
        self._object_pts = self._build_object_points()

        self._all_obj = []
        self._all_img = []
        self._image_size = None
        self._frame_count = 0

    def _build_object_points(self):
        """
        构建所有 tag 及其四个角在 世界坐标系 (mm) 中的坐标。
        每个 tag 的坐标系原点在其中心，四角对称。
        """
        rows, cols = self.tag_grid
        half = self.tag_size / 2.0
        # tag 的四个角相对于 tag 中心的偏移
        corners_local = np.array([
            [-half, -half, 0],
            [ half, -half, 0],
            [ half,  half, 0],
            [-half,  half, 0],
        ], dtype=np.float32)

        pts = []
        for r in range(rows):
            for c in range(cols):
                cx = c * (self.tag_size + self.spacing) + self.tag_size / 2.0
                cy = r * (self.tag_size + self.spacing) + self.tag_size / 2.0
                for corner in corners_local:
                    pts.append(corner + [cx, cy, 0])
        return np.array(pts, dtype=np.float32)

    def detect(self, gray):
        """检测 AprilTag，返回画了结果的彩色图 + 是否检测到完整板"""
        img_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        tags = self._detector.detect(gray)
        result_img = img_rgb.copy()

        # 过滤：只保留 grid 内 tag ID
        max_id = self.tag_grid[0] * self.tag_grid[1] - 1
        tags = [t for t in tags if t.tag_id <= max_id]

        # 绘制检测结果
        for tag in tags:
            corners = tag.corners.astype(int)
            for i in range(4):
                cv2.line(result_img, tuple(corners[i]), tuple(corners[(i + 1) % 4]), (0, 255, 0), 2)
            cx, cy = int(tag.center[0]), int(tag.center[1])
            cv2.putText(result_img, str(tag.tag_id), (cx - 10, cy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        return result_img, tags

    def capture(self, gray, tags):
        """保存检测到的 tag 角点用于标定"""
        if self._image_size is None:
            self._image_size = (gray.shape[1], gray.shape[0])

        max_id = self.tag_grid[0] * self.tag_grid[1] - 1
        tags = [t for t in tags if t.tag_id <= max_id]

        # 需要检测到至少一半的 tag
        required = max(1, (self.tag_grid[0] * self.tag_grid[1]) // 2)
        if len(tags) < required:
            return False

        # 按 tag_id 排序，确保与 object_pts 顺序一致
        tags.sort(key=lambda t: t.tag_id)

        obj_pts = []
        img_pts = []
        for tag in tags:
            idx = tag.tag_id
            half = self.tag_size / 2.0
            # 四个角相对于 tag 中心的偏移
            offsets = np.array([
                [-half, -half, 0],
                [ half, -half, 0],
                [ half,  half, 0],
                [-half,  half, 0],
            ], dtype=np.float32)
            r = idx // self.tag_grid[1]
            c = idx % self.tag_grid[1]
            cx = c * (self.tag_size + self.spacing) + self.tag_size / 2.0
            cy = r * (self.tag_size + self.spacing) + self.tag_size / 2.0
            for off in offsets:
                obj_pts.append(off + [cx, cy, 0])
            for corner in tag.corners:
                img_pts.append(corner)

        self._all_obj.append(np.array(obj_pts, dtype=np.float32))
        self._all_img.append(np.array(img_pts, dtype=np.float32))
        self._frame_count += 1
        return True

    def calibrate(self):
        if self._frame_count < 3:
            return None
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self._all_obj, self._all_img, self._image_size, None, None
        )
        return ret, mtx, dist

    def save_result(self, error, mtx, dist):
        import json
        result = {
            "camera": self.name,
            "tag_family": "tagStandard41h12",
            "tag_grid": list(self.tag_grid),
            "tag_size_mm": self.tag_size,
            "spacing_mm": self.spacing,
            "image_size": list(self._image_size),
            "num_frames": self._frame_count,
            "reprojection_error": float(error),
            "camera_matrix": mtx.tolist(),
            "distortion_coefficients": dist.tolist(),
        }
        out = Path(__file__).resolve().parent / f"calib_{self.name}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return out

    def reset(self):
        self._all_obj.clear()
        self._all_img.clear()
        self._image_size = None
        self._frame_count = 0

    @property
    def frame_count(self):
        return self._frame_count


# ─── DDS 双相机订阅 ──────────────────────────────────

import time
import dds_middleware_python as dds
from PySide6.QtCore import QThread, Signal


FRAME_INTERVAL = 0.1  # 100ms


class DualCamWorker(QThread):
    front_ready = Signal(np.ndarray)
    rear_ready = Signal(np.ndarray)
    log_msg = Signal(str)

    def __init__(self, config_path="config/dds_config.yaml", parent=None):
        super().__init__(parent)
        self._config = config_path
        self._running = True
        self._last = {"front": 0.0, "rear": 0.0}

    def run(self):
        try:
            mw = dds.PyDDSMiddleware(self._config)
        except Exception as e:
            self.log_msg.emit(f"DDS 初始化失败: {e}")
            return

        def throttle(side):
            now = time.monotonic()
            if now - self._last[side] < FRAME_INTERVAL:
                return True
            self._last[side] = now
            return False

        def mkcb(side):
            def cb(data):
                if throttle(side):
                    return
                try:
                    arr = np.frombuffer(bytes(data.data()), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        (self.front_ready if side == "front" else self.rear_ready).emit(img)
                except Exception:
                    pass
            return cb

        for side, topic in [("front", "rt/camera/camera2/image_compressed"),
                            ("rear", "rt/camera/camera3/image_compressed")]:
            try:
                mw.subscribeCompressedImage(topic, mkcb(side))
                self.log_msg.emit(f"已订阅 {topic}")
            except Exception as e:
                self.log_msg.emit(f"订阅失败 {topic}: {e}")

        while self._running:
            time.sleep(1)

    def stop(self):
        self._running = False


# ─── 主窗口 ─────────────────────────────────────────

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        cfg = get_calib_config()
        self._eng_front = CalibEngine("camera2", cfg["tag_grid"], cfg["tag_size_mm"], cfg["spacing_mm"])
        self._eng_rear = CalibEngine("camera3", cfg["tag_grid"], cfg["tag_size_mm"], cfg["spacing_mm"])

        self._cap_front = False
        self._cap_rear = False
        self._busy_front = False
        self._busy_rear = False

        # DDS
        dds_cfg = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        self._cam = DualCamWorker(config_path=dds_cfg)
        self._cam.front_ready.connect(self._on_front)
        self._cam.rear_ready.connect(self._on_rear)
        self._cam.log_msg.connect(self.statusbar.showMessage)
        self._cam.start()

        # 按钮
        self.btnCapFront.clicked.connect(lambda: setattr(self, "_cap_front", True))
        self.btnCapRear.clicked.connect(lambda: setattr(self, "_cap_rear", True))
        self.btnCalFront.clicked.connect(lambda: self._calib(self._eng_front, self.textResultFront, "前置"))
        self.btnCalRear.clicked.connect(lambda: self._calib(self._eng_rear, self.textResultRear, "后置"))
        self.btnResetFront.clicked.connect(lambda: self._reset(self._eng_front, self.textResultFront, "前置"))
        self.btnResetRear.clicked.connect(lambda: self._reset(self._eng_rear, self.textResultRear, "后置"))

    # ─── 帧处理 ──────────────────────────────────────

    def _proc(self, img_bgr, engine, label_view, label_info, label_count, btn_cal, need_cap):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        result_img, tags = engine.detect(gray)

        h, w, ch = result_img.shape
        qt = QImage(result_img.data, w, h, ch * w, QImage.Format.Format_BGR888)
        label_view.setPixmap(QPixmap.fromImage(qt))
        label_view.setFixedSize(w, h)

        # 检查是否检测到足够的 tag
        MAX_ID = engine.tag_grid[0] * engine.tag_grid[1] - 1
        valid = [t for t in tags if t.tag_id <= MAX_ID]
        detected = len(valid)

        self._update_status(label_info, label_count, btn_cal, engine, detected, MAX_ID + 1)

        if need_cap and detected > 0:
            engine.capture(gray, tags)
            self._update_status(label_info, label_count, btn_cal, engine, detected, MAX_ID + 1)

    def _update_status(self, label_info, label_count, btn_cal, engine, detected, total):
        if detected >= total:
            label_info.setText(f"✅ 检测到全部 {detected}/{total} 个 tag")
            label_info.setStyleSheet("color: #0f0; font: 12px;")
        elif detected > 0:
            label_info.setText(f"⚠️ 检测到 {detected}/{total} 个 tag")
            label_info.setStyleSheet("color: #fa0; font: 12px;")
        else:
            label_info.setText("❌ 未检测到 AprilTag")
            label_info.setStyleSheet("color: #f44; font: 12px;")
        label_count.setText(f"已捕获: {engine.frame_count} 帧")
        btn_cal.setEnabled(engine.frame_count >= 3)

    def _on_front(self, img):
        if self._busy_front:
            return
        self._busy_front = True
        try:
            self._proc(img, self._eng_front, self.viewFront, self.infoFront,
                       self.countFront, self.btnCalFront, self._cap_front)
        finally:
            self._cap_front = False
            self._busy_front = False

    def _on_rear(self, img):
        if self._busy_rear:
            return
        self._busy_rear = True
        try:
            self._proc(img, self._eng_rear, self.viewRear, self.infoRear,
                       self.countRear, self.btnCalRear, self._cap_rear)
        finally:
            self._cap_rear = False
            self._busy_rear = False

    # ─── 标定 ────────────────────────────────────────

    def _calib(self, engine, label_result, name):
        r = engine.calibrate()
        if r is None:
            self.statusbar.showMessage(f"{name}: 至少需要 3 帧")
            return
        error, mtx, dist = r
        fx, fy = mtx[0, 0], mtx[1, 1]
        cx, cy = mtx[0, 2], mtx[1, 2]
        k1, k2, p1, p2, k3 = dist.ravel()
        label_result.setText(
            f"重投影误差: {error:.4f} px\n"
            f"fx = {fx:.2f}    fy = {fy:.2f}\n"
            f"cx = {cx:.2f}    cy = {cy:.2f}\n"
            f"k1 = {k1:.6f}  k2 = {k2:.6f}\n"
            f"p1 = {p1:.6f}  p2 = {p2:.6f}\n"
            f"k3 = {k3:.6f}"
        )
        out = engine.save_result(error, mtx, dist)
        self.statusbar.showMessage(f"{name} 标定完成 → {out.name}")

    def _reset(self, engine, label_result, name):
        engine.reset()
        self.countFront.setText("已捕获: 0 帧")
        self.countRear.setText("已捕获: 0 帧")
        label_result.setText("等待标定...")
        self.statusbar.showMessage(f"{name}: 已重置")

    def closeEvent(self, event):
        self._cam.stop()
        self._cam.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad AprilTag 标定")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
