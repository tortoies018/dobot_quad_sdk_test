# 说明三维轨迹绘图控件的用途与交互方式。
"""
IMU 轨迹绘图控件——使用 PyOpenGL / pyqtgraph 绘制机器人在世界坐标系中的 3D 运动轨迹。

交互方式（Unity 风格）：
- 左键 / 中键拖拽：平移视角（Pan）
- 右键拖拽：环绕视角（Orbit）
- 滚轮：缩放
- WASDQE：飞行镜头（W/S 沿视线前后，A/D 左右，Q/E 上下，Shift 加速）
- R 键：重置视角
"""

# 导入本模块所需的库、类型和外部组件。
import math
import time

# 导入本模块所需的库、类型和外部组件。
import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph import Vector
from PySide6.QtCore import Qt, QTimer
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
COLOR_IDEAL = np.array([0.95, 0.55, 0.05, 1.0], dtype=np.float32)  # 理想轨迹（橙）
COLOR_TARGET = (1.0, 0.65, 0.05, 1.0)
COLOR_COMMAND = np.array([0.78, 0.05, 0.95, 1.0], dtype=np.float32)
COLOR_COMMAND_HEADING = np.array([0.0, 0.72, 1.0, 1.0], dtype=np.float32)
COLOR_COMMAND_ARC = np.array([1.0, 0.85, 0.05, 1.0], dtype=np.float32)
COLOR_BOUNDARY = np.array([0.0, 0.75, 0.95, 1.0], dtype=np.float32)
COLOR_PATROL_SAFE = np.array([1.0, 0.45, 0.05, 1.0], dtype=np.float32)
COLOR_BOUNDARY_CENTER = (1.0, 0.82, 0.1, 1.0)
COLOR_BOUNDARY_VERTEX = (0.75, 0.15, 0.95, 1.0)


# 为指定数量的顶点复制同一种颜色。
def _repeat_color(color, n):
    """把单个颜色重复 n 次，生成 (N,4) 的 per-vertex 颜色数组"""
    return np.tile(color, (n, 1))


# 封装三维轨迹、边界和指令图形的绘制与交互。
class TrajectoryPlot3D(gl.GLViewWidget):
    """3D 轨迹绘图：世界坐标 XYZ"""

    # 初始化对象状态以及运行所需的资源。
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        self.setBackgroundColor(COLOR_BG)
        self.setStyleSheet(f"background-color: {COLOR_BG};")
        self.setCameraPosition(distance=6.0, elevation=40, azimuth=45)

        # 初始化或更新本段运行所需的对象状态。
        self._points = []
        self._clear_pts = []
        self._max_points = 5000
        self._grid_spec = None

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
        self._line = gl.GLLinePlotItem(mode="line_strip", width=3, antialias=True, glOptions='translucent')
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

        # 理想轨迹（如正方形的期望路径）
        self._ideal = gl.GLLinePlotItem(mode="line_strip", width=2, antialias=True, glOptions='translucent')
        self.addItem(self._ideal)

        # 目标点和箭头把“转向目标点，再走到目标点”的指令效果画出来。
        self._ideal_targets = gl.GLScatterPlotItem(color=COLOR_TARGET, size=9)
        self.addItem(self._ideal_targets)
        self._ideal_arrows = gl.GLLinePlotItem(mode="lines", width=2, glOptions='translucent')
        self.addItem(self._ideal_arrows)

        # 自动来回动作的安全范围：青色轮廓、黄色中心点和紫色人工标点。
        self._boundary_outline = gl.GLLinePlotItem(
            mode="line_strip", width=4, antialias=True, glOptions='translucent')
        self.addItem(self._boundary_outline)
        self._boundary_center = gl.GLScatterPlotItem(
            color=COLOR_BOUNDARY_CENTER, size=13)
        self.addItem(self._boundary_center)
        self._boundary_cross = gl.GLLinePlotItem(
            mode="lines", width=3, glOptions='translucent')
        self.addItem(self._boundary_cross)
        self._boundary_vertices = gl.GLScatterPlotItem(
            color=COLOR_BOUNDARY_VERTEX, size=11)
        self.addItem(self._boundary_vertices)
        self._patrol_safe_outline = gl.GLLinePlotItem(
            mode="line_strip", width=4, antialias=True, glOptions='translucent')
        self.addItem(self._patrol_safe_outline)

        # 当前正在执行的指令：紫色剩余路径、蓝色当前朝向、黄色转向弧。
        self._command_line = gl.GLLinePlotItem(
            mode="line_strip", width=5, antialias=True, glOptions='translucent')
        self.addItem(self._command_line)
        self._command_arrow = gl.GLLinePlotItem(mode="lines", width=4, glOptions='translucent')
        self.addItem(self._command_arrow)
        self._command_headings = gl.GLLinePlotItem(mode="lines", width=3, glOptions='translucent')
        self.addItem(self._command_headings)
        self._command_arc = gl.GLLinePlotItem(
            mode="line_strip", width=3, antialias=True, glOptions='translucent')
        self.addItem(self._command_arc)
        self._command_target = gl.GLScatterPlotItem(color=tuple(COLOR_COMMAND), size=14)
        self.addItem(self._command_target)

        # 初始化或更新本段运行所需的对象状态。
        self._last_mouse_pos = None
        self._drag_button = None
        self._pressed_keys = set()
        self._camera_velocity = np.zeros(3, dtype=np.float64)
        self._pending_pan = np.zeros(2, dtype=np.float64)
        self._pending_orbit = np.zeros(2, dtype=np.float64)
        self._zoom_target = float(self.opts.get("distance", 6.0))
        self._last_frame_time = time.monotonic()

        # 所有镜头变化统一在 60 FPS 定时器中处理，避免按键重复和鼠标
        # 事件频率不同造成一顿一顿的观感。
        self._camera_timer = QTimer(self)
        self._camera_timer.setTimerType(Qt.PreciseTimer)
        self._camera_timer.setInterval(16)
        self._camera_timer.timeout.connect(self._animate_camera)
        self._camera_timer.start()

    # ─── 网格：mode='lines'，每两点一条独立线段 ────────────────────

    # 生成地面网格所需的独立线段顶点。
    @staticmethod
    def _grid_segments(size, step, cx, cy):
        """生成 XY 平面网格线段（mode='lines'：每两点一条独立线段）"""
        half = size / 2.0
        start = -half
        n = int(round(size / step))
        pts = []
        # 逐项处理当前集合中的数据。
        for i in range(n + 1):
            v = start + i * step
            # 水平线
            pts.append([start + cx, v + cy, 0.0])
            pts.append([half + cx, v + cy, 0.0])
            # 垂直线
            pts.append([v + cx, start + cy, 0.0])
            pts.append([v + cx, half + cy, 0.0])
        return np.array(pts, dtype=np.float32)

    # 创建主网格和次网格的绘制对象。
    def _build_grid(self, size, major_step, minor_step, cx, cy):
        spec = (float(size), float(major_step), float(minor_step), float(cx), float(cy))
        # 根据当前状态或输入选择对应的处理路径。
        if spec == self._grid_spec:
            return
        self._grid_spec = spec
        pos_major = self._grid_segments(size, major_step, cx, cy)
        self._grid_major.setData(
            pos=pos_major,
            color=_repeat_color(COLOR_GRID_MAJOR, len(pos_major)),
        )

        # 准备本逻辑段使用的局部数据和中间状态。
        half = size / 2.0
        start = -half
        n_minor = int(round(size / minor_step))
        n_major = int(round(size / major_step))
        major_set = {start + i * major_step for i in range(n_major + 1)}
        pts = []
        # 逐项处理当前集合中的数据。
        for i in range(n_minor + 1):
            v = start + i * minor_step
            # 根据当前状态或输入选择对应的处理路径。
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

    # 创建世界坐标原点的三色坐标轴。
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

    # 根据姿态角创建机器人局部坐标轴。
    def _build_imu_axes(self, x, y, z, roll, pitch, yaw, scale=0.4):
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy_, sy = math.cos(yaw), math.sin(yaw)

        # 准备本逻辑段使用的局部数据和中间状态。
        ex = np.array([cy_ * cp, sy * cp, -sp])
        ey = np.array([cy_ * sp * sr - sy * cr, sy * sp * sr + cy_ * cr, cp * sr])
        ez = np.array([cy_ * sp * cr + sy * sr, sy * sp * cr - cy_ * cr, cp * cr])

        # 准备本逻辑段使用的局部数据和中间状态。
        p = np.array([x, y, z])
        px, py, pz = p + ex * scale
        qx, qy, qz = p + ey * scale
        rx, ry, rz = p + ez * scale

        # 准备本逻辑段使用的局部数据和中间状态。
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

    # 向实际轨迹中加入一个新的位置点。
    def add_point(self, x, y, z):
        x, y, z = float(x), float(y), float(z)
        # 必要条件或数据不满足时执行安全处理。
        if not all(math.isfinite(v) for v in (x, y, z)):
            return
        self._points.append((x, y, z))
        # 根据当前状态或输入选择对应的处理路径。
        if len(self._points) > self._max_points:
            self._points.pop(0)
        self._update()

    # 在当前轨迹起点放置标记。
    def mark_start(self):
        # 根据当前状态或输入选择对应的处理路径。
        if self._points:
            self._clear_pts.append(self._points[-1])
            self._update()

    # 清空轨迹和动态指令图形并恢复静态边界。
    def clear(self):
        self._points.clear()
        self._clear_pts.clear()
        self.set_ideal_path(None)
        self.set_current_command(None)
        self.set_boundary_region(None)
        self.set_patrol_safe_region(None)
        self.set_boundary_points(None)
        self._update()
        self._reset_camera()

    # 更新蓝色实际边界的绘制数据。
    def set_boundary_region(self, region):
        """显示自动动作的矩形或多点限制范围。"""
        empty = np.zeros((0, 3), dtype=np.float32)
        # 必要条件或数据不满足时执行安全处理。
        if not region:
            self._boundary_outline.setData(
                pos=empty, color=_repeat_color(COLOR_BOUNDARY, 0)
            )
            self._boundary_center.setData(pos=empty)
            self._boundary_cross.setData(
                pos=empty, color=_repeat_color(COLOR_BOUNDARY, 0)
            )
            return
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            center = np.array(region["center"], dtype=np.float32)[:3]
            corners = np.array(region["corners"], dtype=np.float32)[:, :3]
        # 捕获异常并执行日志记录或安全降级。
        except (KeyError, TypeError, ValueError, IndexError):
            return
        # 根据当前状态或输入选择对应的处理路径。
        if len(center) != 3 or len(corners) < 3:
            return
        outline = np.vstack((corners, corners[0]))
        outline[:, 2] = 0.025
        center_floor = center.copy()
        center_floor[2] = 0.04
        self._boundary_outline.setData(
            pos=outline, color=_repeat_color(COLOR_BOUNDARY, len(outline))
        )
        self._boundary_center.setData(pos=center_floor.reshape(1, 3))

        # 准备本逻辑段使用的局部数据和中间状态。
        edge_lengths = [
            float(np.linalg.norm(start[:2] - end[:2]))
            for start, end in zip(corners, np.roll(corners, -1, axis=0))
        ]
        cross_size = max(0.08, min(edge_lengths) * 0.12)
        yaw = float(region.get("yaw", 0.0))
        forward = np.array([math.cos(yaw), math.sin(yaw), 0.0], dtype=np.float32)
        left = np.array([-math.sin(yaw), math.cos(yaw), 0.0], dtype=np.float32)
        cross = np.array([
            center_floor - forward * cross_size,
            center_floor + forward * cross_size,
            center_floor - left * cross_size,
            center_floor + left * cross_size,
        ], dtype=np.float32)
        self._boundary_cross.setData(
            pos=cross, color=_repeat_color(COLOR_BOUNDARY, len(cross))
        )

    # 更新用户采集的边界顶点及其连线。
    def set_boundary_points(self, points):
        """显示用户在机器狗当前位置记录的多点围栏标点。"""
        empty = np.zeros((0, 3), dtype=np.float32)
        # 必要条件或数据不满足时执行安全处理。
        if not points:
            self._boundary_vertices.setData(pos=empty)
            return
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            vertices = np.array(points, dtype=np.float32)[:, :3]
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError, IndexError):
            return
        # 根据当前状态或输入选择对应的处理路径。
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            return
        vertices = vertices.copy()
        vertices[:, 2] = 0.055
        self._boundary_vertices.setData(pos=vertices)

    # 更新巡逻目标安全线的绘制数据。
    def set_patrol_safe_region(self, region):
        """用橙色轮廓显示随机巡逻实际使用的内部安全线。"""
        empty = np.zeros((0, 3), dtype=np.float32)
        # 必要条件或数据不满足时执行安全处理。
        if not region:
            self._patrol_safe_outline.setData(
                pos=empty, color=_repeat_color(COLOR_PATROL_SAFE, 0)
            )
            return
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            corners = np.array(region["corners"], dtype=np.float32)[:, :3]
        # 捕获异常并执行日志记录或安全降级。
        except (KeyError, TypeError, ValueError, IndexError):
            return
        # 根据当前状态或输入选择对应的处理路径。
        if corners.ndim != 2 or len(corners) < 3 or corners.shape[1] != 3:
            return
        outline = np.vstack((corners, corners[0]))
        outline[:, 2] = 0.045
        self._patrol_safe_outline.setData(
            pos=outline,
            color=_repeat_color(COLOR_PATROL_SAFE, len(outline)),
        )

    # 更新计划路径及分步指令可视化。
    def set_ideal_path(self, points):
        """设置指令轨迹；折线、目标点和箭头共同显示每段移动效果。"""
        # 必要条件或数据不满足时执行安全处理。
        if not points:
            empty = np.zeros((0, 3), dtype=np.float32)
            self._ideal.setData(
                pos=empty,
                color=_repeat_color(COLOR_IDEAL, 0),
            )
            self._ideal_targets.setData(pos=empty)
            self._ideal_arrows.setData(pos=empty, color=_repeat_color(COLOR_IDEAL, 0))
            return
        pts = np.array(points, dtype=np.float32)
        self._ideal.setData(
            pos=pts,
            color=_repeat_color(COLOR_IDEAL, len(pts)),
        )
        self._ideal_targets.setData(pos=pts[1:])

        # 准备本逻辑段使用的局部数据和中间状态。
        arrow_segments = []
        # 逐项处理当前集合中的数据。
        for start, target in zip(pts[:-1], pts[1:]):
            direction = target[:2] - start[:2]
            length = float(np.linalg.norm(direction))
            # 根据当前状态或输入选择对应的处理路径。
            if length <= 1e-6:
                continue
            unit = direction / length
            side = np.array([-unit[1], unit[0]], dtype=np.float32)
            arrow_len = min(max(length * 0.16, 0.06), 0.24)
            tip = start + (target - start) * 0.68
            wing_center = tip.copy()
            wing_center[:2] -= unit * arrow_len
            wing_a = wing_center.copy()
            wing_b = wing_center.copy()
            wing_a[:2] += side * arrow_len * 0.55
            wing_b[:2] -= side * arrow_len * 0.55
            arrow_segments.extend((tip, wing_a, tip, wing_b))
        arrows = (np.array(arrow_segments, dtype=np.float32) if arrow_segments
                  else np.zeros((0, 3), dtype=np.float32))
        self._ideal_arrows.setData(
            pos=arrows,
            color=_repeat_color(COLOR_IDEAL, len(arrows)),
        )

    # 绘制当前正在执行的单步摇杆指令。
    def set_current_command(self, command):
        """动态绘制当前转向/移动指令及当前位置到目标点的剩余路径。"""
        empty = np.zeros((0, 3), dtype=np.float32)
        # 必要条件或数据不满足时执行安全处理。
        if not command:
            self._command_line.setData(pos=empty, color=_repeat_color(COLOR_COMMAND, 0))
            self._command_arrow.setData(pos=empty, color=_repeat_color(COLOR_COMMAND, 0))
            self._command_headings.setData(pos=empty, color=np.zeros((0, 4), dtype=np.float32))
            self._command_arc.setData(pos=empty, color=_repeat_color(COLOR_COMMAND_ARC, 0))
            self._command_target.setData(pos=empty)
            return

        # 准备本逻辑段使用的局部数据和中间状态。
        current = np.array(command.get("current", [0.0, 0.0, 0.0]), dtype=np.float32)
        target = np.array(command.get("target", current), dtype=np.float32)
        # 根据当前状态或输入选择对应的处理路径。
        if current.size < 3 or target.size < 3:
            return
        current, target = current[:3].copy(), target[:3].copy()
        # 略微抬高指令图层，避免与网格/计划轨迹发生深度闪烁。
        current[2] = target[2] = 0.035
        segment = np.array([current, target], dtype=np.float32)
        self._command_line.setData(
            pos=segment,
            color=_repeat_color(COLOR_COMMAND, len(segment)),
        )
        self._command_target.setData(pos=target.reshape(1, 3))

        # 准备本逻辑段使用的局部数据和中间状态。
        delta = target[:2] - current[:2]
        remaining = float(np.linalg.norm(delta))
        arrow_pts = empty
        # 根据当前状态或输入选择对应的处理路径。
        if remaining > 1e-6:
            unit = delta / remaining
            side = np.array([-unit[1], unit[0]], dtype=np.float32)
            arrow_len = min(max(remaining * 0.18, 0.08), 0.28)
            tip = current + (target - current) * 0.72
            base = tip.copy()
            base[:2] -= unit * arrow_len
            wing_a, wing_b = base.copy(), base.copy()
            wing_a[:2] += side * arrow_len * 0.6
            wing_b[:2] -= side * arrow_len * 0.6
            arrow_pts = np.array([tip, wing_a, tip, wing_b], dtype=np.float32)
        self._command_arrow.setData(
            pos=arrow_pts,
            color=_repeat_color(COLOR_COMMAND, len(arrow_pts)),
        )

        # 准备本逻辑段使用的局部数据和中间状态。
        current_yaw = float(command.get("current_yaw", 0.0))
        target_yaw = float(command.get("target_yaw", current_yaw))
        ray_len = min(max(remaining * 0.28, 0.22), 0.75)
        current_rad, target_rad = math.radians(current_yaw), math.radians(target_yaw)
        current_tip = current.copy()
        target_tip = current.copy()
        current_tip[:2] += ray_len * np.array([math.cos(current_rad), math.sin(current_rad)])
        target_tip[:2] += ray_len * np.array([math.cos(target_rad), math.sin(target_rad)])
        headings = np.array([current, current_tip, current, target_tip], dtype=np.float32)
        heading_colors = np.array([
            COLOR_COMMAND_HEADING, COLOR_COMMAND_HEADING,
            COLOR_COMMAND, COLOR_COMMAND,
        ], dtype=np.float32)
        self._command_headings.setData(pos=headings, color=heading_colors)

        # 准备本逻辑段使用的局部数据和中间状态。
        arc = empty
        turn = (target_yaw - current_yaw + 180.0) % 360.0 - 180.0
        # 根据当前状态或输入选择对应的处理路径。
        if command.get("phase") == "turn" and abs(turn) > 0.5:
            radius = ray_len * 0.62
            angles = np.radians(np.linspace(current_yaw, current_yaw + turn, 25))
            arc = np.column_stack((
                current[0] + radius * np.cos(angles),
                current[1] + radius * np.sin(angles),
                np.full_like(angles, current[2] + 0.01),
            )).astype(np.float32)
        self._command_arc.setData(
            pos=arc,
            color=_repeat_color(COLOR_COMMAND_ARC, len(arc)),
        )

    # 根据最新缓存数据刷新三维绘制对象。
    def _update(self):
        # 必要条件或数据不满足时执行安全处理。
        if not self._points:
            empty = np.zeros((0, 3), dtype=np.float32)
            self._line.setData(pos=empty, color=_repeat_color(COLOR_LINE, 0))
            self._current.setData(pos=empty)
            self._starts.setData(pos=empty)
            self._drop_line.setData(pos=empty, color=_repeat_color(COLOR_DROP, 0))
            self._build_grid(20.0, 1.0, 0.2, 0.0, 0.0)
            self._build_imu_axes(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            return

        # 准备本逻辑段使用的局部数据和中间状态。
        pts = np.array(self._points, dtype=np.float32)
        floor_pts = pts.copy()
        floor_pts[:, 2] = 0.0
        self._line.setData(
            pos=floor_pts,
            color=_repeat_color(COLOR_LINE, len(floor_pts)),
        )
        self._current.setData(pos=pts[-1:])

        # 准备本逻辑段使用的局部数据和中间状态。
        last = pts[-1]
        drop = np.array([[last[0], last[1], 0.0], last], dtype=np.float32)
        self._drop_line.setData(
            pos=drop,
            color=_repeat_color(COLOR_DROP, len(drop)),
        )

        # 根据当前状态或输入选择对应的处理路径。
        if self._clear_pts:
            self._starts.setData(pos=np.array(self._clear_pts, dtype=np.float32))
        # 其余情况进入默认的处理路径。
        else:
            self._starts.setData(pos=np.zeros((0, 3), dtype=np.float32))

        # 执行本逻辑段的数据处理、状态同步或界面更新。
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
        # 网格中心按主刻度吸附，避免每个采样点都重建整张网格。
        grid_cx = round(cx / major_step) * major_step
        grid_cy = round(cy / major_step) * major_step
        self._build_grid(float(total_size), major_step, minor_step, grid_cx, grid_cy)

    # 用最新姿态刷新机器人局部坐标轴。
    def update_imu_axes(self, x, y, z, roll, pitch, yaw, scale=0.4):
        self._build_imu_axes(x, y, z, roll, pitch, yaw, scale)

    # ─── 交互 ──────────────────────────────────────────────────────

    # 记录鼠标按键状态以开始相机交互。
    def mousePressEvent(self, ev):
        self.setFocus(Qt.MouseFocusReason)
        self._last_mouse_pos = ev.position()
        self._drag_button = ev.button()
        # 根据当前状态或输入选择对应的处理路径。
        if ev.button() in (Qt.LeftButton, Qt.MiddleButton, Qt.RightButton):
            ev.accept()
        # 其余情况进入默认的处理路径。
        else:
            super().mousePressEvent(ev)

    # 根据鼠标拖动旋转或平移三维相机。
    def mouseMoveEvent(self, ev):
        # 必要条件或数据不满足时执行安全处理。
        if self._last_mouse_pos is None:
            super().mouseMoveEvent(ev)
            return
        delta = ev.position() - self._last_mouse_pos
        self._last_mouse_pos = ev.position()
        # 根据当前状态或输入选择对应的处理路径。
        if self._drag_button in (Qt.LeftButton, Qt.MiddleButton):
            self._pending_pan += (delta.x(), delta.y())
        # 前一条件不成立时继续检查下一种情况。
        elif self._drag_button == Qt.RightButton:
            self._pending_orbit += (delta.x(), delta.y())
        # 其余情况进入默认的处理路径。
        else:
            super().mouseMoveEvent(ev)
            return
        ev.accept()

    # 结束对应鼠标按键的相机交互。
    def mouseReleaseEvent(self, ev):
        self._drag_button = None
        self._last_mouse_pos = None
        ev.accept()

    # 根据滚轮输入调整三维视图缩放。
    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        # 根据当前状态或输入选择对应的处理路径。
        if delta != 0:
            steps = delta / 120.0
            self._zoom_target = min(1000.0, max(0.08, self._zoom_target * math.exp(-steps * 0.16)))
        ev.accept()

    # 记录用于相机移动的按键状态。
    def keyPressEvent(self, ev):
        key = ev.key()
        # 根据当前状态或输入选择对应的处理路径。
        if key == Qt.Key_R:
            self._reset_camera()
            ev.accept()
            return
        # 根据当前状态或输入选择对应的处理路径。
        if key in (Qt.Key_W, Qt.Key_S, Qt.Key_A, Qt.Key_D, Qt.Key_Q, Qt.Key_E, Qt.Key_Shift):
            # 根据当前状态或输入选择对应的处理路径。
            if ev.isAutoRepeat():
                ev.accept()
                return
            self._pressed_keys.add(key)
            ev.accept()
            return
        super().keyPressEvent(ev)

    # 清除已经释放的相机移动按键。
    def keyReleaseEvent(self, ev):
        key = ev.key()
        # 根据当前状态或输入选择对应的处理路径。
        if ev.isAutoRepeat() and key in self._pressed_keys:
            ev.accept()
            return
        # 根据当前状态或输入选择对应的处理路径。
        if key in self._pressed_keys:
            self._pressed_keys.discard(key)
            ev.accept()
            return
        super().keyReleaseEvent(ev)

    # 窗口失焦时清除所有持续按键状态。
    def focusOutEvent(self, ev):
        self._pressed_keys.clear()
        super().focusOutEvent(ev)

    # 根据当前按键连续更新相机位置。
    def _animate_camera(self):
        """按真实帧间隔平滑更新平移、环绕、缩放和飞行镜头。"""
        now = time.monotonic()
        dt = min(max(now - self._last_frame_time, 0.0), 0.05)
        self._last_frame_time = now

        # 根据当前状态或输入选择对应的处理路径。
        if np.any(self._pending_orbit):
            dx, dy = self._pending_orbit
            self._pending_orbit[:] = 0.0
            self.orbit(-dx * 0.28, dy * 0.28)
        # 根据当前状态或输入选择对应的处理路径。
        if np.any(self._pending_pan):
            dx, dy = self._pending_pan
            self._pending_pan[:] = 0.0
            # GLViewWidget.pan(view) 的参数单位本来就是屏幕像素。
            self.pan(dx, dy, 0.0, relative="view")

        # 准备本逻辑段使用的局部数据和中间状态。
        current_distance = float(self.opts.get("distance", 6.0))
        zoom_alpha = 1.0 - math.exp(-14.0 * dt)
        next_distance = current_distance + (self._zoom_target - current_distance) * zoom_alpha
        # 根据当前状态或输入选择对应的处理路径。
        if abs(next_distance - current_distance) > 1e-5:
            self.setCameraPosition(distance=next_distance)

        # 准备本逻辑段使用的局部数据和中间状态。
        elev = math.radians(self.opts.get("elevation", 30))
        azim = math.radians(self.opts.get("azimuth", 45))
        outward = np.array([
            math.cos(elev) * math.cos(azim),
            math.cos(elev) * math.sin(azim),
            math.sin(elev),
        ])
        forward = -outward
        right = np.array([-math.sin(azim), math.cos(azim), 0.0])
        up = np.array([0.0, 0.0, 1.0])

        # 准备本逻辑段使用的局部数据和中间状态。
        move = np.zeros(3, dtype=np.float64)
        move += forward * ((Qt.Key_W in self._pressed_keys) - (Qt.Key_S in self._pressed_keys))
        move += right * ((Qt.Key_D in self._pressed_keys) - (Qt.Key_A in self._pressed_keys))
        move += up * ((Qt.Key_E in self._pressed_keys) - (Qt.Key_Q in self._pressed_keys))
        length = float(np.linalg.norm(move))
        # 根据当前状态或输入选择对应的处理路径。
        if length > 1e-8:
            move /= length

        # 距离越远飞行越快；指数插值提供类似 Unity 编辑器的加减速。
        speed = max(0.15, current_distance * 0.8)
        # 根据当前状态或输入选择对应的处理路径。
        if Qt.Key_Shift in self._pressed_keys:
            speed *= 3.0
        target_velocity = move * speed
        velocity_alpha = 1.0 - math.exp(-12.0 * dt)
        self._camera_velocity += (target_velocity - self._camera_velocity) * velocity_alpha
        # 根据当前状态或输入选择对应的处理路径。
        if float(np.linalg.norm(self._camera_velocity)) > 1e-5 and dt > 0.0:
            offset = self._camera_velocity * dt
            center = self.opts.get("center")
            self.setCameraPosition(pos=Vector(
                center.x() + offset[0],
                center.y() + offset[1],
                center.z() + offset[2],
            ))

    # 将三维相机恢复到默认观察位置。
    def _reset_camera(self):
        self._pressed_keys.clear()
        self._camera_velocity[:] = 0.0
        self._pending_pan[:] = 0.0
        self._pending_orbit[:] = 0.0
        self._zoom_target = 6.0
        self.setCameraPosition(pos=Vector(0.0, 0.0, 0.0), distance=6.0, elevation=40, azimuth=45)
