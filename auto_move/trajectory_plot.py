"""
IMU 轨迹绘图控件——使用 PyOpenGL / pyqtgraph 绘制机器人在世界坐标系中的 3D 运动轨迹。

交互方式（类 Blender）：
- 中键拖拽：环绕视角（Orbit）
- Shift + 中键拖拽：平移视角（Pan）
- 滚轮：缩放
- R 键：重置视角

数据来源：gRPC get_state().robot_state.pos_body（IMU 融合定位）。

注意：轨迹线绘制在地面（z=0）上，当前位置标记显示真实高度，便于和网格对齐。
"""

import math

import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy


# 颜色常量（0-255 整数元组，兼容 pyqtgraph 0.14）
COLOR_BG = (217, 222, 225, 255)
COLOR_GRID_MAJOR = (60, 70, 80, 255)
COLOR_GRID_MINOR = (150, 160, 170, 255)
COLOR_LINE = (0, 140, 70, 255)
COLOR_START = (238, 110, 0, 255)
COLOR_CURRENT = (210, 50, 50, 255)
COLOR_DROP = (100, 110, 120, 255)


class TrajectoryPlot3D(gl.GLViewWidget):
    """3D 轨迹绘图：世界坐标 XYZ，支持 Blender 式交互"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        # 浅灰背景
        self.setBackgroundColor("#d9dce1")
        self.setStyleSheet("background-color: #d9dce1;")

        # 初始相机位置：略俯视，能看清地面网格
        self.setCameraPosition(distance=6.0, elevation=40, azimuth=45)

        self._points = []        # [(x, y, z), ...] 单位 m
        self._clear_pts = []     # 每次移动的起点标记
        self._max_points = 5000

        # 地面网格：使用线段绘制，避免 GLGridItem 线太细看不清
        self._grid_major = gl.GLLinePlotItem(mode="lines", width=2, color=COLOR_GRID_MAJOR)
        self.addItem(self._grid_major)
        self._grid_minor = gl.GLLinePlotItem(mode="lines", width=1, color=COLOR_GRID_MINOR)
        self.addItem(self._grid_minor)
        self._draw_grid(20.0, 1.0, 0.2, 0.0, 0.0)

        # 坐标轴
        self._axes = gl.GLAxisItem()
        self._axes.setSize(0.5, 0.5, 0.5)
        self.addItem(self._axes)

        # 轨迹线（绘制在地面上 z=0，确保和网格对齐）
        self._line = gl.GLLinePlotItem(
            color=COLOR_LINE, width=3, antialias=True
        )
        self.addItem(self._line)

        # 起点标记（橙色）
        self._starts = gl.GLScatterPlotItem(color=COLOR_START, size=8)
        self.addItem(self._starts)

        # 当前位置（红色）
        self._current = gl.GLScatterPlotItem(color=COLOR_CURRENT, size=10)
        self.addItem(self._current)

        # 当前位置到地面的垂线
        self._drop_line = gl.GLLinePlotItem(mode="lines", width=2, color=COLOR_DROP)
        self.addItem(self._drop_line)

        # 鼠标交互状态
        self._last_mouse_pos = None
        self._drag_button = None

    # ─── 网格绘制 ──────────────────────────────────────────────────

    @staticmethod
    def _grid_segments(size, step, cx=0.0, cy=0.0):
        """生成 XY 平面网格线段（mode='lines' 格式，每两点一条独立线段）"""
        half = size / 2.0
        start = -half
        n = int(round(size / step))
        pts = []
        for i in range(n + 1):
            v = start + i * step
            # 平行于 X 轴的线
            pts.append((start + cx, v + cy, 0.0))
            pts.append((half + cx, v + cy, 0.0))
            # 平行于 Y 轴的线
            pts.append((v + cx, start + cy, 0.0))
            pts.append((v + cx, half + cy, 0.0))
        return np.array(pts, dtype=np.float32)

    def _draw_grid(self, size, major_step, minor_step, cx, cy):
        self._grid_major.setData(
            pos=self._grid_segments(size, major_step, cx, cy)
        )
        self._grid_minor.setData(
            pos=self._grid_segments(size, minor_step, cx, cy)
        )

    # ─── 数据接口 ──────────────────────────────────────────────────

    def add_point(self, x, y, z):
        """追加一个 3D 轨迹点"""
        x, y, z = float(x), float(y), float(z)
        if not all(math.isfinite(v) for v in (x, y, z)):
            return
        self._points.append((x, y, z))
        if len(self._points) > self._max_points:
            self._points.pop(0)
        self._update()

    def mark_start(self):
        """标记当前位置为一次移动的起点"""
        if self._points:
            self._clear_pts.append(self._points[-1])
            self._update()

    def clear(self):
        """清空轨迹"""
        self._points.clear()
        self._clear_pts.clear()
        self._update()
        self.setCameraPosition(distance=6.0, elevation=40, azimuth=45)

    def _update(self):
        """同步数据到 OpenGL 项"""
        if not self._points:
            empty = np.zeros((0, 3), dtype=np.float32)
            self._line.setData(pos=empty)
            self._current.setData(pos=empty)
            self._starts.setData(pos=empty)
            self._drop_line.setData(pos=empty)
            self._draw_grid(20.0, 1.0, 0.2, 0.0, 0.0)
            return

        pts = np.array(self._points, dtype=np.float32)

        # 轨迹线压到地面 z=0，便于和网格对齐
        floor_pts = pts.copy()
        floor_pts[:, 2] = 0.0
        self._line.setData(pos=floor_pts)

        # 当前位置标记使用真实高度
        self._current.setData(pos=pts[-1:])

        # 当前位置到地面的垂线
        last = pts[-1]
        drop = np.array([
            [last[0], last[1], 0.0],
            last,
        ], dtype=np.float32)
        self._drop_line.setData(pos=drop)

        if self._clear_pts:
            self._starts.setData(pos=np.array(self._clear_pts, dtype=np.float32))
        else:
            self._starts.setData(pos=np.zeros((0, 3), dtype=np.float32))

        # 动态调整网格大小与位置，使其始终包围轨迹
        xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]
        cx, cy = float(xs.mean()), float(ys.mean())
        max_range = max(
            xs.max() - xs.min(),
            ys.max() - ys.min(),
            zs.max() - zs.min(),
            1.0,
        )
        total_size = math.ceil(max_range * 2.4)
        # 默认网格至少 20m，避免一开始太小
        total_size = max(total_size, 20)
        major_step = max(1.0, round(total_size / 10))
        minor_step = max(0.2, round(major_step / 5, 1))
        self._draw_grid(float(total_size), major_step, minor_step, cx, cy)

    # ─── Blender 式交互 ───────────────────────────────────────────

    def mousePressEvent(self, ev):
        self._last_mouse_pos = ev.position()
        self._drag_button = ev.button()
        if ev.button() == Qt.MiddleButton:
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag_button != Qt.MiddleButton or self._last_mouse_pos is None:
            super().mouseMoveEvent(ev)
            return

        delta = ev.position() - self._last_mouse_pos
        self._last_mouse_pos = ev.position()

        if ev.modifiers() & Qt.ShiftModifier:
            # Shift + 中键 = 平移
            dist = max(0.1, self.opts.get("distance", 6.0))
            self.pan(
                -delta.x() * 0.005 * dist,
                delta.y() * 0.005 * dist,
                0,
                relative="view",
            )
        else:
            # 中键 = 环绕
            self.orbit(-delta.x() * 0.4, delta.y() * 0.4)
        ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_button = None
        self._last_mouse_pos = None
        super().mouseReleaseEvent(ev)

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        if delta != 0:
            factor = 0.9 if delta > 0 else 1.1
            self.setCameraPosition(
                distance=max(0.1, self.opts.get("distance", 6.0) * factor)
            )
        ev.accept()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_R:
            self.setCameraPosition(distance=6.0, elevation=40, azimuth=45)
        else:
            super().keyPressEvent(ev)
