"""AprilTag 追踪与 PnP 定位程序——实时检测 tag 并计算机器人位置轨迹"""

import sys, time, json
from pathlib import Path

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QGroupBox, QSplitter, QTextEdit, QStatusBar,
)

import dds_middleware_python as dds
from pupil_apriltags import Detector as ApriltagDetector

from tag_generator import generate_a4_page, TAG_SIZE_MM, DICT_NAME


# ─── 参数 ───────────────────────────────────────────
CAMERA_TOPICS = {
    "前置 RGB": "rt/camera/camera2/image_compressed",
    "后置 RGB": "rt/camera/camera3/image_compressed",
}

# 相机内参（未标定时使用估算值，标定后可替换）
# 分辨率 640×480，水平视角约 60°
CAMERA_MATRIX = np.array([
    [500, 0, 320],
    [0, 500, 240],
    [0, 0, 1]
], dtype=np.float64)
DIST_COEFFS = np.zeros((5, 1), dtype=np.float64)

FRAME_INTERVAL = 0.1  # 100ms


# ─── DDS 相机订阅 ──────────────────────────────────

class DDSCamThread(QThread):
    frame_ready = Signal(np.ndarray)
    log = Signal(str)

    def __init__(self, topic, config_path, parent=None):
        super().__init__(parent)
        self._topic = topic
        self._config = config_path
        self._running = True
        self._last = 0.0

    def switch_topic(self, topic):
        self._topic = topic

    def run(self):
        try:
            mw = dds.PyDDSMiddleware(self._config)
        except Exception as e:
            self.log.emit(f"DDS 初始化失败: {e}")
            return

        def cb(data):
            now = time.monotonic()
            if now - self._last < FRAME_INTERVAL:
                return
            self._last = now
            try:
                arr = np.frombuffer(bytes(data.data()), dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    self.frame_ready.emit(img)
            except Exception:
                pass

        try:
            mw.subscribeCompressedImage(self._topic, cb)
            self.log.emit(f"已订阅 {self._topic}")
        except Exception as e:
            self.log.emit(f"订阅失败: {e}")
            return

        while self._running:
            time.sleep(1)

    def stop(self):
        self._running = False


# ─── 轨迹记录器（保存路径点） ──────────────────────

class Trajectory:
    def __init__(self, max_points=500):
        self.poses = []          # [(x, y, z), ...] 单位 mm
        self.timestamps = []
        self.max_points = max_points

    def add(self, tvec):
        self.poses.append((float(tvec[0]), float(tvec[1]), float(tvec[2])))
        self.timestamps.append(time.time())
        if len(self.poses) > self.max_points:
            self.poses.pop(0)
            self.timestamps.pop(0)

    def clear(self):
        self.poses.clear()
        self.timestamps.clear()

    def to_dict(self):
        return {"poses": self.poses, "timestamps": self.timestamps}

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# ─── 轨迹绘制面板 ──────────────────────────────────

class TrajectoryWidget(QWidget):
    """用 QPainter 绘制俯视图轨迹"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #111;")
        self._trajectory = Trajectory()
        self._current_pos = None  # (x, z) 俯视图
        self._tag_id = -1

    def set_trajectory(self, traj):
        self._trajectory = traj

    def update_pose(self, tvec, tag_id):
        self._current_pos = (float(tvec[0]), float(tvec[2]))  # 俯视图: x, z
        self._tag_id = tag_id

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # 背景
        painter.fillRect(0, 0, w, h, QColor("#1a1a1a"))

        # 网格
        painter.setPen(QPen(QColor("#333"), 1))
        grid_size = 50
        for x in range(0, w, grid_size):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, grid_size):
            painter.drawLine(0, y, w, y)

        # 中心十字（tag 位置）
        painter.setPen(QPen(QColor("#0af"), 2))
        painter.drawLine(cx - 20, cy, cx + 20, cy)
        painter.drawLine(cx, cy - 20, cx, cy + 20)
        painter.drawText(cx + 4, cy - 4, "Tag")

        # 绘制轨迹
        if len(self._trajectory.poses) >= 2:
            painter.setPen(QPen(QColor("#0f0"), 3))
            pts = self._trajectory.poses
            for i in range(len(pts) - 1):
                x1 = cx + int(pts[i][0] * 2)  # 2x 缩放
                y1 = cy - int(pts[i][2] * 2)
                x2 = cx + int(pts[i + 1][0] * 2)
                y2 = cy - int(pts[i + 1][2] * 2)
                # 钳位到窗口范围
                if all(0 <= v < w * 2 for v in [x1, x2, y1, y2]):
                    painter.drawLine(x1, y1, x2, y2)

        # 当前位置
        if self._current_pos is not None:
            px = cx + int(self._current_pos[0] * 2)
            py = cy - int(self._current_pos[1] * 2)
            if 0 <= px < w and 0 <= py < h:
                painter.setPen(QPen(QColor("#f00"), 0))
                painter.setBrush(QColor("#f00"))
                painter.drawEllipse(px - 6, py - 6, 12, 12)
                painter.setPen(QPen(QColor("#fff"), 1))
                painter.drawText(px + 8, py + 4,
                                 f"TAG#{self._tag_id}  ({self._current_pos[0]:.0f},{self._current_pos[1]:.0f})mm")

        painter.end()


# ─── 主窗口 ─────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dobot Quad AprilTag 追踪定位")
        self.setMinimumSize(1400, 850)

        # 状态
        self._running = True
        self._busy = False
        self._tag_size_mm = TAG_SIZE_MM
        self._cam_matrix = CAMERA_MATRIX.copy()
        self._dist_coeffs = DIST_COEFFS.copy()
        self._detector = ApriltagDetector(families=DICT_NAME, nthreads=2)
        self._trajectory = Trajectory()
        self._current_tvec = None
        self._current_tag_id = -1

        # ─── UI ────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # 左侧：相机画面 + 控制
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # 相机选择
        bar = QHBoxLayout()
        bar.addWidget(QLabel("相机:"))
        self.cam_combo = QComboBox()
        self.cam_combo.addItems(list(CAMERA_TOPICS.keys()))
        bar.addWidget(self.cam_combo)
        bar.addStretch()
        self.btn_gen_tag = QPushButton("生成 tag PNG")
        self.btn_gen_tag.clicked.connect(self._gen_tag)
        bar.addWidget(self.btn_gen_tag)
        self.btn_save = QPushButton("保存轨迹")
        self.btn_save.clicked.connect(self._save_traj)
        bar.addWidget(self.btn_save)
        self.btn_clear = QPushButton("清除轨迹")
        self.btn_clear.clicked.connect(self._trajectory.clear)
        bar.addWidget(self.btn_clear)
        left_layout.addLayout(bar)

        # 画面
        self.label_cam = QLabel("等待相机...")
        self.label_cam.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_cam.setMinimumSize(480, 360)
        self.label_cam.setStyleSheet("background:#111; color:#555; font:18px; border:1px solid #333;")
        left_layout.addWidget(self.label_cam, 1)

        # PnP 信息
        self.text_info = QTextEdit()
        self.text_info.setReadOnly(True)
        self.text_info.setMaximumHeight(120)
        self.text_info.setStyleSheet("background:#1a1a1a; color:#0f0; font:12px monospace; border:1px solid #333;")
        left_layout.addWidget(self.text_info)

        # 右侧：轨迹
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("俯视图轨迹 (Tag 为中心)", styleSheet="color:#0af; font:bold 14px;"))
        self.traj_widget = TrajectoryWidget()
        self.traj_widget.set_trajectory(self._trajectory)
        right_layout.addWidget(self.traj_widget, 1)

        # 分割
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 6)
        split.setStretchFactor(1, 4)
        main_layout.addWidget(split)

        # 状态栏
        self.status = QStatusBar()
        self.status.setStyleSheet("color:#aaa; background:#222; font:12px;")
        self.setStatusBar(self.status)

        # ─── DDS ───────────────────────────────────
        config_path = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        topic = CAMERA_TOPICS[list(CAMERA_TOPICS.keys())[0]]
        self._cam_thread = DDSCamThread(topic, config_path)
        self._cam_thread.frame_ready.connect(self._on_frame)
        self._cam_thread.log.connect(self.status.showMessage)
        self._cam_thread.start()

        self.cam_combo.currentTextChanged.connect(self._on_cam_switch)

        # 定时更新轨迹
        self._traj_timer = QTimer(self)
        self._traj_timer.timeout.connect(self._update_traj_display)
        self._traj_timer.start(200)

    def _on_cam_switch(self, name):
        topic = CAMERA_TOPICS.get(name)
        if topic:
            self._cam_thread._topic = topic
            self.status.showMessage(f"已切换: {name}")

    def _gen_tag(self):
        generate_a4_page(self._current_tag_id if self._current_tag_id >= 0 else 0, "tags")
        self.status.showMessage(f"tag_{self._current_tag_id:02d}.png 已生成")

    def _save_traj(self):
        path = Path(__file__).resolve().parent / "trajectory.json"
        self._trajectory.save(str(path))
        self.status.showMessage(f"轨迹已保存: {path.name}")

    # ─── 帧处理 ─────────────────────────────────────

    def _on_frame(self, img_bgr):
        if self._busy:
            return
        self._busy = True
        try:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            tags = self._detector.detect(gray)

            # 绘制检测结果
            display = img_bgr.copy()
            info_lines = []

            for tag in tags:
                corners = tag.corners.astype(int)
                cv2.polylines(display, [corners], True, (0, 255, 0), 3)
                cx, cy = int(tag.center[0]), int(tag.center[1])
                cv2.circle(display, (cx, cy), 6, (0, 255, 255), -1)
                cv2.putText(display, f"#{tag.tag_id}", (cx - 20, cy - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

                # PnP
                half = self._tag_size_mm / 2.0
                obj_pts = np.array([
                    [-half, -half, 0],
                    [ half, -half, 0],
                    [ half,  half, 0],
                    [-half,  half, 0],
                ], dtype=np.float64)
                img_pts = tag.corners.astype(np.float64)

                success, rvec, tvec = cv2.solvePnP(
                    obj_pts, img_pts, self._cam_matrix, self._dist_coeffs
                )

                if success:
                    # 绘制坐标轴
                    cv2.drawFrameAxes(display, self._cam_matrix, self._dist_coeffs,
                                      rvec, tvec, self._tag_size_mm * 0.5)

                    # 记录轨迹
                    self._trajectory.add(tvec)
                    self._current_tvec = tvec
                    self._current_tag_id = tag.tag_id

                    dist_mm = np.linalg.norm(tvec)
                    info_lines.append(
                        f"Tag#{tag.tag_id:2d}  "
                        f"X={tvec[0][0]:6.0f} Y={tvec[1][0]:6.0f} Z={tvec[2][0]:6.0f} mm  "
                        f"距离={dist_mm:.0f} mm"
                    )

            # 显示画面
            h, w, ch = display.shape
            qt = QImage(display.data, w, h, ch * w, QImage.Format.Format_BGR888)
            self.label_cam.setPixmap(QPixmap.fromImage(qt))
            self.label_cam.setFixedSize(w, h)

            # 显示信息
            self.text_info.setText("\n".join(info_lines) if info_lines else "未检测到 AprilTag")

        finally:
            self._busy = False

    def _update_traj_display(self):
        self.traj_widget.update_pose(
            self._current_tvec if self._current_tvec is not None else np.array([[0], [0], [0]]),
            self._current_tag_id,
        )
        self.traj_widget.update()

    def closeEvent(self, event):
        self._cam_thread.stop()
        self._cam_thread.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad AprilTag 追踪")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
