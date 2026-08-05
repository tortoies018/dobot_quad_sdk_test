"""
IMU 轨迹绘图控件——使用 PyOpenGL / pyqtgraph 绘制机器人在世界坐标系中的 3D 运动轨迹。

交互方式：
- 左键拖拽：平移视角（Pan）
- 右键拖拽：环绕视角（Orbit）
- 滚轮：缩放
- R 键：重置视角
"""

import math

import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy


# 颜色常量（浮点 0-1）
COLOR_BG = "#d9dce1"
COLOR_GRID_MAJOR = np.array([0.24, 0.27, 0.31, 1.0], dtype=np.float32)
COLOR_GRID_MINOR = np.array([0.59, 0.63, 0.67, 1.0], dtype=np.float32)
COLOR_LINE = np.array([0.0, 0.55, 0.28, 1.0], dtype=np.float32)
COLOR_START = (0.93, 0.46, 0.0, 1.0)
COLOR_CURRENT = (0.83, 0.18, 0.18, 1.0)
COLOR_DROP = np.array([0.39, 0.43, 0.47, 1.0], dtype=np.float32)
COLOR_ORIGIN_X = np.array([0.86, 0.2, 0.2, 1.0], dtype=np.float32)
COLOR_ORIGIN_Y = np.array([0.2, 0.7, 0.2, 1.0], dtype=np.float32)
COLOR_ORIGIN_Z = np.array([0.2, 0.4, 0.86, 1.0], dtype=np.float32)
COLOR_IMU_X = np.array([0.9, 0.2, 0.2, 1.0], dtype=np.float32)
COLOR_IMU_Y = np.array([0.2, 0.75, 0.2, 1.0], dtype=np.float32)
COLOR_IMU_Z = np.array([0.2, 0.5, 0.9, 1.0], dtype=np.float32)


def _repeat_color(color, n):
    """把单个颜色重复 n 次，生成 (N,4) 的 per-vertex 颜色数组"""
    return np.tile(color, (n, 1))


class TrajectoryPlot3D(gl.GLViewWidget):
    """3D 轨迹绘图：世界坐标 XYZ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        self.setBackgroundColor(COLOR_BG)
        self.setStyleSheet(f"background-color: {COLOR_BG};")
        self.setCameraPosition(distance=6.0, elevation=40, azimuth=45)

        self._points = []
        self._clear_pts = []
        self._max_points = 5000

        # 网格（mode='lines' + translucent：每对顶点一条独立线段，颜色正常）
        self._grid_major = gl.GLLinePlotItem(mode="lines", width=2, glOptions='translucent')
        self._grid_minor = gl.GLLinePlotItem(mode="lines", width=1, glOptions='translucent')
        self.addItem(self._grid_major)
        self.addItem(self._grid_minor)
        self._build_grid(20.0, 1.0, 0.2, 0.0, 0.0)

        # 世界坐标轴（原点）
        self._origin_axes = gl.GLLinePlotItem(mode="lines", width=3, glOptions='translucent')
        self.addItem(self._origin_axes)
        self._build_origin_axes(1.5)

        # 轨迹线
        self._line = gl.GLLinePlotItem(mode="lines", width=3, antialias=True, glOptions='translucent')
        self.addItem(self._line)

        # 起点标记
        self._starts = gl.GLScatterPlotItem(color=COLOR_START, size=8)
        self.addItem(self._starts)

        # 当前位置
        self._current = gl.GLScatterPlotItem(color=COLOR_CURRENT, size=10)
        self.addItem(self._current)

        # 垂线
        self._drop_line = gl.GLLinePlotItem(mode="lines", width=2, glOptions='translucent')
        self.addItem(self._drop_line)

        # IMU 本体坐标轴
        self._imu_axes = gl.GLLinePlotItem(mode="lines", width=3, glOptions='translucent')
        self.addItem(self._imu_axes)

        self._last_mouse_pos = None
        self._drag_button = None

    # ─── 网格：mode='lines'，每两点一条独立线段 ────────────────────

    @staticmethod
    def _grid_segments(size, step, cx, cy):
        """生成 XY 平面网格线段（mode='lines'：每两点一条独立线段）"""
        half = size / 2.0
        start = -half
        n = int(round(size / step))
        pts = []
        for i in range(n + 1):
            v = start + i * step
            # 水平线
            pts.append([start + cx, v + cy, 0.0])
            pts.append([half + cx, v + cy, 0.0])
            # 垂直线
            pts.append([v + cx, start + cy, 0.0])
            pts.append([v + cx, half + cy, 0.0])
        return np.array(pts, dtype=np.float32)

    def _build_grid(self, size, major_step, minor_step, cx, cy):
        pos_major = self._grid_segments(size, major_step, cx, cy)
        self._grid_major.setData(
            pos=pos_major,
            color=_repeat_color(COLOR_GRID_MAJOR, len(pos_major)),
        )

        half = size / 2.0
        start = -half
        n_minor = int(round(size / minor_step))
        n_major = int(round(size / major_step))
        major_set = {start + i * major_step for i in range(n_major + 1)}
        pts = []
        for i in range(n_minor + 1):
            v = start + i * minor_step
            if any(abs(v - mv) < 0.001 for mv in major_set):
                continue
            pts.append([start + cx, v + cy, 0.0])
            pts.append([half + cx, v + cy, 0.0])
            pts.append([v + cx, start + cy, 0.0])
            pts.append([v + cx, half + cy, 0.0])
        pos_minor = np.array(pts, dtype=np.float32) if pts else np.zeros((0, 3), dtype=np.float32)
        self._grid_minor.setData(
            pos=pos_minor,
            color=_repeat_color(COLOR_GRID_MINOR, len(pos_minor)),
        )

    # ─── 坐标轴：mode='lines' + per-vertex 颜色 ────────────────────

    def _build_origin_axes(self, size=1.5):
        pos = np.array([
            [0.0, 0.0, 0.0], [size, 0.0, 0.0],
            [0.0, 0.0, 0.0], [0.0, size, 0.0],
            [0.0, 0.0, 0.0], [0.0, 0.0, size],
        ], dtype=np.float32)
        color = np.array([
            COLOR_ORIGIN_X, COLOR_ORIGIN_X,
            COLOR_ORIGIN_Y, COLOR_ORIGIN_Y,
            COLOR_ORIGIN_Z, COLOR_ORIGIN_Z,
        ], dtype=np.float32)
        self._origin_axes.setData(pos=pos, color=color)

    def _build_imu_axes(self, x, y, z, roll, pitch, yaw, scale=0.4):
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy_, sy = math.cos(yaw), math.sin(yaw)

        ex = np.array([cy_ * cp, sy * cp, -sp])
        ey = np.array([cy_ * sp * sr - sy * cr, sy * sp * sr + cy_ * cr, cp * sr])
        ez = np.array([cy_ * sp * cr + sy * sr, sy * sp * cr - cy_ * cr, cp * cr])

        p = np.array([x, y, z])
        px, py, pz = p + ex * scale
        qx, qy, qz = p + ey * scale
        rx, ry, rz = p + ez * scale

        pos = np.array([
            [x, y, z], [px, py, pz],
            [x, y, z], [qx, qy, qz],
            [x, y, z], [rx, ry, rz],
        ], dtype=np.float32)
        color = np.array([
            COLOR_IMU_X, COLOR_IMU_X,
            COLOR_IMU_Y, COLOR_IMU_Y,
            COLOR_IMU_Z, COLOR_IMU_Z,
        ], dtype=np.float32)
        self._imu_axes.setData(pos=pos, color=color)

    # ─── 数据接口 ──────────────────────────────────────────────────

    def add_point(self, x, y, z):
        x, y, z = float(x), float(y), float(z)
        if not all(math.isfinite(v) for v in (x, y, z)):
            return
        self._points.append((x, y, z))
        if len(self._points) > self._max_points:
            self._points.pop(0)
        self._update()

    def mark_start(self):
        if self._points:
            self._clear_pts.append(self._points[-1])
            self._update()

    def clear(self):
        self._points.clear()
        self._clear_pts.clear()
        self._update()
        self.setCameraPosition(distance=6.0, elevation=40, azimuth=45)

    def _update(self):
        if not self._points:
            empty = np.zeros((0, 3), dtype=np.float32)
            self._line.setData(pos=empty, color=_repeat_color(COLOR_LINE, 0))
            self._current.setData(pos=empty)
            self._starts.setData(pos=empty)
            self._drop_line.setData(pos=empty, color=_repeat_color(COLOR_DROP, 0))
            self._build_grid(20.0, 1.0, 0.2, 0.0, 0.0)
            self._build_imu_axes(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            return

        pts = np.array(self._points, dtype=np.float32)
        floor_pts = pts.copy()
        floor_pts[:, 2] = 0.0
        self._line.setData(
            pos=floor_pts,
            color=_repeat_color(COLOR_LINE, len(floor_pts)),
        )
        self._current.setData(pos=pts[-1:])

        last = pts[-1]
        drop = np.array([[last[0], last[1], 0.0], last], dtype=np.float32)
        self._drop_line.setData(
            pos=drop,
            color=_repeat_color(COLOR_DROP, len(drop)),
        )

        if self._clear_pts:
            self._starts.setData(pos=np.array(self._clear_pts, dtype=np.float32))
        else:
            self._starts.setData(pos=np.zeros((0, 3), dtype=np.float32))

        xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]
        cx, cy = float(xs.mean()), float(ys.mean())
        max_range = max(
            xs.max() - xs.min(),
            ys.max() - ys.min(),
            zs.max() - zs.min(),
            1.0,
        )
        total_size = max(math.ceil(max_range * 2.4), 20)
        major_step = max(1.0, round(total_size / 10))
        minor_step = max(0.2, round(major_step / 5, 1))
        self._build_grid(float(total_size), major_step, minor_step, cx, cy)

    def update_imu_axes(self, x, y, z, roll, pitch, yaw, scale=0.4):
        self._build_imu_axes(x, y, z, roll, pitch, yaw, scale)

    # ─── 交互 ──────────────────────────────────────────────────────

    def mousePressEvent(self, ev):
        self._last_mouse_pos = ev.position()
        self._drag_button = ev.button()
        if ev.button() in (Qt.LeftButton, Qt.MiddleButton, Qt.RightButton):
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._last_mouse_pos is None:
            super().mouseMoveEvent(ev)
            return
        delta = ev.position() - self._last_mouse_pos
        self._last_mouse_pos = ev.position()
        if self._drag_button == Qt.LeftButton:
            dist = max(0.1, self.opts.get("distance", 6.0))
            self.pan(delta.x() * 0.02 * dist, delta.y() * 0.02 * dist, 0, relative="view")
        elif self._drag_button == Qt.RightButton:
            self.orbit(-delta.x() * 0.4, delta.y() * 0.4)
        elif self._drag_button == Qt.MiddleButton:
            self.orbit(-delta.x() * 0.4, delta.y() * 0.4)
        else:
            super().mouseMoveEvent(ev)
            return
        ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_button = None
        self._last_mouse_pos = None
        super().mouseReleaseEvent(ev)

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        if delta != 0:
            factor = 0.9 if delta > 0 else 1.1
            self.setCameraPosition(distance=max(0.1, self.opts.get("distance", 6.0) * factor))
        ev.accept()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_R:
            self.setCameraPosition(distance=6.0, elevation=40, azimuth=45)
        else:
            super().keyPressEvent(ev)
