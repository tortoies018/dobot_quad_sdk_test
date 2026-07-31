"""AprilTag 追踪与 PnP 定位程序——实时检测 tag 并计算机器人位置轨迹

功能：
- 实时 DDS 相机订阅 + 视频文件回放
- 轨迹平滑（EMA 滤波）
- 视频录制
- 逐帧分析（前进/后退/暂停/速度控制）
"""

import sys, time, json
from pathlib import Path

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSplitter, QTextEdit, QStatusBar,
    QFileDialog,
)

import pyqtgraph.opengl as gl
import dds_middleware_python as dds
from pupil_apriltags import Detector as ApriltagDetector

from tag_generator import generate_a4_page, TAG_SIZE_MM, DICT_NAME


# ─── 参数 ───────────────────────────────────────────
CAMERA_TOPICS = {
    "前置 RGB": "rt/camera/camera2/image_compressed",
    "后置 RGB": "rt/camera/camera3/image_compressed",
}

CALIB_FILES = {
    "前置 RGB": "/home/gg/Documents/dobot_quad_sdk_test/camera_calib2/calib_camera2.json",
    "后置 RGB": "/home/gg/Documents/dobot_quad_sdk_test/camera_calib2/calib_camera3.json",
}

CAMERA_MATRIX = np.array([
    [500, 0, 320],
    [0, 500, 240],
    [0, 0, 1]
], dtype=np.float64)
DIST_COEFFS = np.zeros((5, 1), dtype=np.float64)

FRAME_INTERVAL = 0.1  # 100ms
EMA_ALPHA = 0.3       # 轨迹平滑系数（越小越平滑）

HALF_TAG = TAG_SIZE_MM / 2.0
CORNER_POS = [
    (0,  HALF_TAG,  HALF_TAG),   # 角点 0
    (0, -HALF_TAG,  HALF_TAG),   # 角点 1
    (0, -HALF_TAG, -HALF_TAG),   # 角点 2
    (0,  HALF_TAG, -HALF_TAG),   # 角点 3
]


def load_calibration(camera_key: str):
    path = CALIB_FILES.get(camera_key)
    if not path or not Path(path).exists():
        print(f"[警告] 未找到标定文件 {path}，使用估算内参")
        return CAMERA_MATRIX.copy(), DIST_COEFFS.copy()
    with open(path, "r") as f:
        data = json.load(f)
    mtx = np.array(data["camera_matrix"], dtype=np.float64)
    dist = np.array(data["distortion_coefficients"], dtype=np.float64).reshape(-1, 1)
    print(f"[标定] {camera_key}: fx={mtx[0,0]:.2f} fy={mtx[1,1]:.2f} "
          f"cx={mtx[0,2]:.2f} cy={mtx[1,2]:.2f} ({data['num_frames']}帧)")
    return mtx, dist


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


# ─── 轨迹记录器 ──────────────────────────────────

class Trajectory:
    def __init__(self, max_points=500):
        self.poses = []
        self.headings = []
        self.timestamps = []
        self.max_points = max_points

    def add(self, pos_3d, heading=None):
        self.poses.append((float(pos_3d[0]), float(pos_3d[1]), float(pos_3d[2])))
        self.headings.append(heading)
        self.timestamps.append(time.time())
        if len(self.poses) > self.max_points:
            self.poses.pop(0)
            self.headings.pop(0)
            self.timestamps.pop(0)

    def clear(self):
        self.poses.clear()
        self.headings.clear()
        self.timestamps.clear()

    def to_dict(self):
        return {"poses": self.poses, "timestamps": self.timestamps}

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# ─── 轨迹 3D 视图 ──────────────────────────────────

COLOR_X = (255, 80, 80)
COLOR_Y = (80, 255, 80)
COLOR_Z = (80, 130, 255)


class TrajectoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #111;")

        self._trajectory = Trajectory()
        self._current_pos = None
        self._current_heading = None
        self._tag_id = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor("#1a1a1a")
        self.view.setCameraPosition(distance=4000, elevation=55, azimuth=45)
        layout.addWidget(self.view)

        # 地面网格
        self.grid = gl.GLGridItem()
        self.grid.setSize(8000, 8000)
        self.grid.setSpacing(500, 500)
        self.grid.translate(0, -0.1, 0)
        self.view.addItem(self.grid)

        # 坐标轴
        ax = 500
        ax_pts = np.array([[0,0,0],[ax,0,0], [0,0,0],[0,ax,0], [0,0,0],[0,0,ax]], dtype=float)
        ax_col = np.array([
            [1,0.3,0.3,1], [1,0.3,0.3,1],
            [0.3,1,0.3,1], [0.3,1,0.3,1],
            [0.3,0.5,1,1], [0.3,0.5,1,1],
        ], dtype=float)
        self.axes = gl.GLLinePlotItem(pos=ax_pts, color=ax_col, width=2, mode='lines')
        self.view.addItem(self.axes)

        for pos, clr in [((ax,0,0), COLOR_X), ((0,ax,0), COLOR_Y), ((0,0,ax), COLOR_Z)]:
            s = gl.GLScatterPlotItem(pos=[pos], color=[c/255 for c in clr] + [1], size=14)
            self.view.addItem(s)

        # tag 方块
        self.tag_square = self._make_tag_square()
        self.view.addItem(self.tag_square)

        # PnP 角点标记
        corner_colors = [
            (1.0, 0.0, 1.0, 1.0),
            (1.0, 0.6, 0.0, 1.0),
            (1.0, 1.0, 0.0, 1.0),
            (0.0, 1.0, 1.0, 1.0),
        ]
        self.corner_markers = []
        for pos, clr in zip(CORNER_POS, corner_colors):
            m = gl.GLScatterPlotItem(pos=[list(pos)], color=clr, size=16)
            self.view.addItem(m)
            self.corner_markers.append(m)

        # 轨迹线
        self.trail = gl.GLLinePlotItem(pos=np.zeros((1, 3)), color=(0, 1, 0, 1),
                                       width=3, antialias=True)
        self.view.addItem(self.trail)

        # 当前位置
        self.current_dot = gl.GLScatterPlotItem(pos=[[0, 0, 0]], size=18,
                                                color=(1, 0, 0, 1))
        self.view.addItem(self.current_dot)

        # 当前朝向
        self.curr_heading = gl.GLLinePlotItem(pos=np.zeros((2, 3)), color=(1, 1, 0, 1),
                                              width=4, antialias=True)
        self.view.addItem(self.curr_heading)

        self.info_label = QLabel("位置: —")
        self.info_label.setStyleSheet("color:#aaa; font:12px monospace; padding:4px; background:rgba(0,0,0,0.6);")
        layout.addWidget(self.info_label)

    def _make_tag_square(self):
        verts = np.array(CORNER_POS, dtype=float)
        faces = np.array([[0, 1, 3], [0, 3, 2]])
        mesh = gl.GLMeshItem(vertexes=verts, faces=faces,
                             color=(0.1, 0.5, 1, 0.25), smooth=False,
                             drawEdges=True, edgeColor=(0.3, 0.7, 1, 1))
        return mesh

    def set_trajectory(self, traj):
        self._trajectory = traj

    def update_pose(self, pos_3d, heading, tag_id):
        self._current_pos = pos_3d
        self._current_heading = heading
        self._tag_id = tag_id

        pts = self._trajectory.poses
        if len(pts) >= 2:
            self.trail.setData(pos=np.array(pts, dtype=float))

        if pos_3d is not None:
            self.current_dot.setData(pos=[list(pos_3d)])
            x, y, z = pos_3d
            if heading is not None:
                dx, dz = heading
                seg = np.array([
                    [x, y, z],
                    [x + dx * 300, y + dz * 300, z],
                ], dtype=float)
                self.curr_heading.setData(pos=seg)
            else:
                self.curr_heading.setData(pos=np.zeros((2, 3)))

            self.info_label.setText(
                f"Tag#{self._tag_id}  X={x:.0f}  Y={y:.0f}  Z={z:.0f} mm  |  "
                f"四角点(品红/橙/黄/青)为PnP解算点  (左键旋转 滚轮缩放 右键平移)"
            )

    def reset_view(self):
        self.view.setCameraPosition(distance=4000, elevation=55, azimuth=45)


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
        self._current_camera_key = list(CAMERA_TOPICS.keys())[0]
        self._cam_matrix, self._dist_coeffs = load_calibration(self._current_camera_key)
        self._detector = ApriltagDetector(families=DICT_NAME, nthreads=2)
        self._trajectory = Trajectory()
        self._current_pos = None
        self._current_heading = None
        self._current_tag_id = -1
        self._target_tag_id = 5
        self._smooth_pos = None  # EMA 平滑位置

        # 录制状态
        self._recording = False
        self._video_writer = None

        # 视频回放状态（逐帧查看）
        self._video_cap = None
        self._video_frame = -1      # 当前帧索引（-1 = 未加载）
        self._video_total = 0
        self._video_fps = 30
        self._video_active = False  # 视频模式标志：为 True 时忽略相机帧
        self._frame_cache = {}      # 帧缓存 {idx: BGR图像}，实现快速前后翻页

        # ─── UI ────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        # 控制栏 1：相机 + tag + 录制 + 视频
        bar1 = QHBoxLayout()
        bar1.addWidget(QLabel("相机:"))
        self.cam_combo = QComboBox()
        self.cam_combo.addItems(list(CAMERA_TOPICS.keys()))
        bar1.addWidget(self.cam_combo)

        bar1.addWidget(QLabel("目标Tag:"))
        self.tag_combo = QComboBox()
        self.tag_combo.addItems([f"#{i}" for i in range(36)])
        self.tag_combo.setCurrentIndex(self._target_tag_id)
        bar1.addWidget(self.tag_combo)

        bar1.addStretch()

        # 清空轨迹按钮
        self.btn_clear_traj = QPushButton("清空轨迹")
        self.btn_clear_traj.setStyleSheet("QPushButton { background:#a60; color:#fff; padding:4px 12px; "
                                          "border:1px solid #555; border-radius:4px; }"
                                          "QPushButton:hover { background:#c80; }")
        self.btn_clear_traj.clicked.connect(self._clear_trajectory)
        bar1.addWidget(self.btn_clear_traj)

        # 录制按钮
        self.btn_record = QPushButton("⏺ 录制")
        self.btn_record.setStyleSheet("QPushButton { background:#a33; color:#fff; padding:4px 12px; "
                                      "border:1px solid #555; border-radius:4px; }"
                                      "QPushButton:hover { background:#c55; }")
        self.btn_record.clicked.connect(self._toggle_record)
        bar1.addWidget(self.btn_record)

        # 加载视频按钮
        self.btn_load_video = QPushButton(" 加载视频")
        self.btn_load_video.setStyleSheet("QPushButton { background:#333; color:#fff; padding:4px 12px; "
                                          "border:1px solid #555; border-radius:4px; }"
                                          "QPushButton:hover { background:#444; }")
        self.btn_load_video.clicked.connect(self._load_video)
        bar1.addWidget(self.btn_load_video)

        left_layout.addLayout(bar1)

        # 控制栏 2：逐帧查看控制
        bar2 = QHBoxLayout()
        self.btn_step_back = QPushButton("⏮ 上一帧")
        self.btn_step_back.setEnabled(False)
        self.btn_step_back.setToolTip("快捷键: ← 或 Shift+←(10帧)")
        self.btn_step_back.setStyleSheet("QPushButton { background:#333; color:#fff; padding:4px 14px; "
                                         "border:1px solid #555; border-radius:4px; }"
                                         "QPushButton:hover { background:#444; }"
                                         "QPushButton:disabled { background:#555; }")
        self.btn_step_back.clicked.connect(lambda: self._step_back(1))
        bar2.addWidget(self.btn_step_back)

        self.btn_step_back10 = QPushButton("⏪ 退10帧")
        self.btn_step_back10.setEnabled(False)
        self.btn_step_back10.clicked.connect(lambda: self._step_back(10))
        self.btn_step_back10.setStyleSheet("QPushButton { background:#333; color:#fff; padding:4px 14px; "
                                           "border:1px solid #555; border-radius:4px; }"
                                           "QPushButton:hover { background:#444; }"
                                           "QPushButton:disabled { background:#555; }")
        bar2.addWidget(self.btn_step_back10)

        self.btn_step_fwd = QPushButton("下一帧 ⏭")
        self.btn_step_fwd.setEnabled(False)
        self.btn_step_fwd.setToolTip("快捷键: → 或 Shift+→(10帧)")
        self.btn_step_fwd.setStyleSheet("QPushButton { background:#333; color:#fff; padding:4px 14px; "
                                        "border:1px solid #555; border-radius:4px; }"
                                        "QPushButton:hover { background:#444; }"
                                        "QPushButton:disabled { background:#555; }")
        self.btn_step_fwd.clicked.connect(lambda: self._step_fwd(1))
        bar2.addWidget(self.btn_step_fwd)

        self.btn_step_fwd10 = QPushButton("进10帧 ⏩")
        self.btn_step_fwd10.setEnabled(False)
        self.btn_step_fwd10.clicked.connect(lambda: self._step_fwd(10))
        self.btn_step_fwd10.setStyleSheet("QPushButton { background:#333; color:#fff; padding:4px 14px; "
                                          "border:1px solid #555; border-radius:4px; }"
                                          "QPushButton:hover { background:#444; }"
                                          "QPushButton:disabled { background:#555; }")
        bar2.addWidget(self.btn_step_fwd10)

        self.lbl_frame = QLabel("帧: -/0")
        self.lbl_frame.setStyleSheet("color:#aaa; font:13px monospace; padding:0 8px;")
        bar2.addWidget(self.lbl_frame)

        # 返回实时模式按钮
        self.btn_live = QPushButton("● 实时模式")
        self.btn_live.setEnabled(False)
        self.btn_live.setToolTip("停止视频查看，返回相机实时画面")
        self.btn_live.setStyleSheet("QPushButton { background:#0af; color:#fff; padding:4px 14px; "
                                    "border:1px solid #555; border-radius:4px; }"
                                    "QPushButton:hover { background:#0cf; }"
                                    "QPushButton:disabled { background:#555; }")
        self.btn_live.clicked.connect(self._back_to_live)
        bar2.addWidget(self.btn_live)

        bar2.addStretch()
        left_layout.addLayout(bar2)

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

        # 右侧：3D 轨迹
        right = QWidget()
        right_layout = QVBoxLayout(right)
        bar_r = QHBoxLayout()
        bar_r.addWidget(QLabel("3D 轨迹 (Tag 为原点)", styleSheet="color:#0af; font:bold 14px;"))
        bar_r.addStretch()
        btn_reset_view = QPushButton("重置视角")
        btn_reset_view.setStyleSheet("QPushButton { background:#333; color:#fff; padding:4px 12px; "
                                     "border:1px solid #555; border-radius:4px; }"
                                     "QPushButton:hover { background:#444; }")
        btn_reset_view.clicked.connect(self._reset_view)
        bar_r.addWidget(btn_reset_view)
        right_layout.addLayout(bar_r)
        self.traj_widget = TrajectoryWidget()
        self.traj_widget.set_trajectory(self._trajectory)
        right_layout.addWidget(self.traj_widget, 1)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 6)
        split.setStretchFactor(1, 4)
        main_layout.addWidget(split)

        self.status = QStatusBar()
        self.status.setStyleSheet("color:#aaa; background:#222; font:12px;")
        self.setStatusBar(self.status)

        # ── DDS ───────────────────────────────────
        config_path = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        topic = CAMERA_TOPICS[list(CAMERA_TOPICS.keys())[0]]
        self._cam_thread = DDSCamThread(topic, config_path)
        self._cam_thread.frame_ready.connect(self._on_frame)
        self._cam_thread.log.connect(self.status.showMessage)
        self._cam_thread.start()

        self.cam_combo.currentTextChanged.connect(self._on_cam_switch)
        self.tag_combo.currentIndexChanged.connect(self._on_tag_select)

        self._traj_timer = QTimer(self)
        self._traj_timer.timeout.connect(self._update_traj_display)
        self._traj_timer.start(200)

    # ─── 相机切换 ──────────────────────────────────

    def _on_cam_switch(self, name):
        topic = CAMERA_TOPICS.get(name)
        if topic:
            self._cam_thread._topic = topic
            self._current_camera_key = name
            self._cam_matrix, self._dist_coeffs = load_calibration(name)
            self.status.showMessage(f"已切换: {name}（使用标定内参）")

    def _on_tag_select(self, idx):
        self._target_tag_id = idx
        self._trajectory.clear()
        self._current_pos = None
        self._current_heading = None
        self._smooth_pos = None
        self.status.showMessage(f"目标 tag 切换为 #{idx}，轨迹已清空")

    def _reset_view(self):
        self.traj_widget.reset_view()
        self.status.showMessage("视角已重置")

    def _gen_tag(self):
        generate_a4_page(self._target_tag_id, "tags")
        self.status.showMessage(f"tag_{self._target_tag_id:02d}.png 已生成")

    def _save_traj(self):
        path = Path(__file__).resolve().parent / "trajectory.json"
        self._trajectory.save(str(path))
        self.status.showMessage(f"轨迹已保存: {path.name}")

    def _clear_trajectory(self):
        """清空已记录的轨迹"""
        self._trajectory.clear()
        self._current_pos = None
        self._current_heading = None
        self._smooth_pos = None
        self.traj_widget.update_pose((0, 0, 0), None, self._current_tag_id)
        self.status.showMessage("轨迹已清空")

    # ── 录制 ──────────────────────────────────────

    def _toggle_record(self):
        if not self._recording:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存录制视频", "recorded.mp4",
                "MP4 视频 (*.mp4);;AVI 视频 (*.avi)"
            )
            if not path:
                return
            # 延迟创建 writer：等收到第一帧确定实际分辨率
            self._record_path = path
            self._record_size = None
            self._video_writer = None
            self._recording = True
            self.btn_record.setText("⏹ 停止录制")
            self.btn_record.setStyleSheet("QPushButton { background:#a33; color:#fff; padding:4px 12px; "
                                          "border:1px solid #555; border-radius:4px; }")
            self.status.showMessage(f"开始录制: {path}")
        else:
            if self._video_writer:
                self._video_writer.release()
                self._video_writer = None
            self._recording = False
            self.btn_record.setText("⏺ 录制")
            self.btn_record.setStyleSheet("QPushButton { background:#a33; color:#fff; padding:4px 12px; "
                                          "border:1px solid #555; border-radius:4px; }"
                                          "QPushButton:hover { background:#c55; }")
            self.status.showMessage("录制已停止")

    # ─── 视频加载与逐帧查看 ─────────────────────────

    def _load_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载视频", "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.webm);;所有文件 (*)"
        )
        if not path:
            return

        if self._video_cap:
            self._video_cap.release()
        self._frame_cache.clear()

        self._video_cap = cv2.VideoCapture(path)
        if not self._video_cap.isOpened():
            self.status.showMessage("无法打开视频文件")
            return

        self._video_total = int(self._video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._video_fps = self._video_cap.get(cv2.CAP_PROP_FPS) or 30
        self._video_frame = -1
        self._video_active = True  # 进入视频模式，忽略相机帧

        self.btn_step_back.setEnabled(True)
        self.btn_step_back10.setEnabled(True)
        self.btn_step_fwd.setEnabled(True)
        self.btn_step_fwd10.setEnabled(True)
        self.btn_live.setEnabled(True)
        self.btn_live.setText("⏏ 返回实时")

        # 跳到第一帧
        self._goto_frame(0)
        self.status.showMessage(
            f"已加载视频: {Path(path).name} ({self._video_total}帧, {self._video_fps:.1f}fps, "
            f"逐帧查看：方向键←/→翻帧，Shift+方向键跳10帧)"
        )

    def _back_to_live(self):
        """返回实时相机模式"""
        self._video_active = False
        self.btn_live.setEnabled(False)
        self.btn_live.setText("● 实时模式")
        self.lbl_frame.setText("帧: -/0")
        self.status.showMessage("已返回实时相机模式")
        # 清除视频帧显示，等待相机帧刷新

    def _goto_frame(self, idx):
        """跳到指定帧并处理（优先使用缓存，其次顺序读取）"""
        if not self._video_cap:
            return

        # 帧缓存命中 → 直接使用
        if idx in self._frame_cache:
            self._video_frame = idx
            self.lbl_frame.setText(f"帧: {idx + 1}/{self._video_total}")
            self._on_frame(self._frame_cache[idx].copy(), source="video")
            return

        # 顺序读取到目标帧（避免 webm 随机跳帧不准确的问题）
        if idx < self._video_frame:
            # 后退：重新打开并顺序读
            path = self._video_cap.get(cv2.CAP_PROP_POS_MSEC)  # 保留进度
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._video_frame = -1

        frame = None
        while self._video_frame < idx:
            ret, frame = self._video_cap.read()
            if not ret:
                break
            self._video_frame += 1
            # 缓存帧（限制缓存数量）
            if len(self._frame_cache) < 3000:
                self._frame_cache[self._video_frame] = frame.copy()

        if frame is not None and self._video_frame == idx:
            self.lbl_frame.setText(f"帧: {idx + 1}/{self._video_total}")
            self._on_frame(frame, source="video")

    def _step_fwd(self, n=1):
        """前进 n 帧"""
        if self._video_cap and self._video_frame < self._video_total - 1:
            self._goto_frame(min(self._video_frame + n, self._video_total - 1))

    def _step_back(self, n=1):
        """后退 n 帧"""
        if self._video_cap and self._video_frame > 0:
            self._goto_frame(max(self._video_frame - n, 0))

    def keyPressEvent(self, event):
        """键盘快捷键：←/→ 翻帧，Shift+←/→ 跳10帧"""
        if self._video_cap is not None:
            key = event.key()
            if key == Qt.Key.Key_Right:
                self._step_fwd(10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
                event.accept()
                return
            elif key == Qt.Key.Key_Left:
                self._step_back(10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
                event.accept()
                return
        super().keyPressEvent(event)

    # ─── 帧处理 ─────────────────────────────────────

    def _on_frame(self, img_bgr, source="camera"):
        # 视频模式下忽略来自相机的帧，避免覆盖视频画面
        if source == "camera" and self._video_active:
            return

        if self._busy:
            return
        self._busy = True
        try:
            # 录制：首次写帧时按实际分辨率创建 writer
            if self._recording:
                if self._video_writer is None:
                    h, w = img_bgr.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    self._video_writer = cv2.VideoWriter(
                        self._record_path, fourcc, 30, (w, h)
                    )
                    if not self._video_writer.isOpened():
                        self.status.showMessage("录制失败：无法创建视频文件")
                        self._recording = False
                        self.btn_record.setText("⏺ 录制")
                    else:
                        self.status.showMessage(f"开始录制 {w}×{h}")
                if self._video_writer:
                    self._video_writer.write(img_bgr)

            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            tags = self._detector.detect(gray)

            display = img_bgr.copy()
            info_lines = []

            corner_colors = [(255, 0, 255), (255, 153, 0), (255, 255, 0), (0, 255, 255)]

            for tag in tags:
                corners = tag.corners.astype(int)
                is_target = (tag.tag_id == self._target_tag_id)

                box_color = (0, 128, 255) if is_target else (0, 255, 0)
                cv2.polylines(display, [corners], True, box_color, 3 if is_target else 2)
                cx, cy = int(tag.center[0]), int(tag.center[1])
                cv2.circle(display, (cx, cy), 6, (0, 255, 255), -1)
                cv2.putText(display, f"#{tag.tag_id}" + ("★" if is_target else ""),
                            (cx - 20, cy - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, box_color, 2)

                for ci, c in enumerate(corners):
                    cv2.circle(display, tuple(c), 7, corner_colors[ci], -1)
                    cv2.putText(display, f"{ci}",
                                (c[0] + 8, c[1] - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                corner_colors[ci], 2)

                if not is_target:
                    continue

                obj_pts = np.array(CORNER_POS, dtype=np.float64)
                img_pts = tag.corners.astype(np.float64)

                success, rvec, tvec = cv2.solvePnP(
                    obj_pts, img_pts, self._cam_matrix, self._dist_coeffs
                )

                if success:
                    R, _ = cv2.Rodrigues(rvec)
                    cam_in_tag = (-R.T @ tvec.reshape(3, 1)).flatten()

                    # EMA 平滑轨迹
                    if self._smooth_pos is None:
                        self._smooth_pos = cam_in_tag.copy()
                    else:
                        self._smooth_pos = EMA_ALPHA * cam_in_tag + (1 - EMA_ALPHA) * self._smooth_pos

                    fwd = (R.T @ np.array([0.0, 0.0, 1.0])).flatten()
                    heading = (fwd[0], fwd[2])

                    self._trajectory.add(self._smooth_pos, heading)
                    self._current_pos = self._smooth_pos
                    self._current_heading = heading
                    self._current_tag_id = tag.tag_id

                    dist_mm = np.linalg.norm(self._smooth_pos)
                    info_lines.append(
                        f"★ 目标Tag#{tag.tag_id}  "
                        f"X={self._smooth_pos[0]:6.0f} Y={self._smooth_pos[1]:6.0f} "
                        f"Z={self._smooth_pos[2]:6.0f} mm  "
                        f"距tag={dist_mm:.0f} mm"
                    )

            # 显示（视频帧可能很大，缩小到最大 760 宽，保持纵横比）
            h, w, ch = display.shape
            max_w = 760
            if w > max_w:
                ratio = max_w / w
                display = cv2.resize(display, (max_w, int(h * ratio)),
                                     interpolation=cv2.INTER_AREA)
                h, w, ch = display.shape
            qt = QImage(display.data, w, h, ch * w, QImage.Format.Format_BGR888)
            self.label_cam.setPixmap(QPixmap.fromImage(qt))
            self.label_cam.setFixedSize(w, h)

            if info_lines:
                self.text_info.setText("\n".join(info_lines))
            else:
                seen = ", ".join(f"#{t.tag_id}" for t in tags) if tags else "无"
                self.text_info.setText(
                    f"目标 Tag#{self._target_tag_id} 未检测到\n"
                    f"当前可见: {seen}"
                )

        finally:
            self._busy = False

    def _update_traj_display(self):
        pos = self._current_pos if self._current_pos is not None else (0, 0, 0)
        self.traj_widget.update_pose(pos, self._current_heading, self._current_tag_id)
        self.traj_widget.update()

    def closeEvent(self, event):
        self._cam_thread.stop()
        self._cam_thread.wait(2000)
        if self._video_writer:
            self._video_writer.release()
        if self._video_cap:
            self._video_cap.release()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad AprilTag 追踪")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
