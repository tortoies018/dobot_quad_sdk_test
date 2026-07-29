"""3D 可视化窗口——实时显示机器人位姿与运动轨迹"""

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

import pyqtgraph as pg
import pyqtgraph.opengl as gl


# 坐标轴颜色
COLOR_X = (255, 80, 80)   # 红 - X
COLOR_Y = (80, 255, 80)   # 绿 - Y
COLOR_Z = (80, 130, 255)  # 蓝 - Z


class Viz3D(QWidget):
    """3D 轨迹与位姿可视化面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1a1a1a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title = QLabel("  3D 位姿 / 轨迹")
        title.setStyleSheet("color: #0af; font: bold 14px; padding: 6px; background: #222;")
        layout.addWidget(title)

        # 3D 视图
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor("k")
        self.view.setCameraPosition(distance=4, elevation=30, azimuth=45)
        layout.addWidget(self.view)

        # ---- 场景元素 ----

        # 1. 地面网格
        g = gl.GLGridItem()
        g.setSize(6, 6)
        g.setSpacing(0.2, 0.2)
        g.translate(0, 0, -0.3)
        self.view.addItem(g)

        # 2. 坐标轴（从原点出发的三条线）
        axis_len = 1.5
        lines = np.array([
            [[0, 0, 0], [axis_len, 0, 0]],  # X
            [[0, 0, 0], [0, axis_len, 0]],  # Y
            [[0, 0, 0], [0, 0, axis_len]],  # Z
        ], dtype=float)
        colors = np.array([COLOR_X, COLOR_Y, COLOR_Z], dtype=float) / 255.0
        self.axis = gl.GLLinePlotItem(pos=lines.reshape(-1, 3), color=colors.repeat(2, axis=0).reshape(-1, 3),
                                      width=2, mode='lines')
        self.view.addItem(self.axis)

        # 3. 坐标轴标签（用 GLTextItem 不方便，用小球标记端点）
        for name, pos, clr in [("X", (axis_len, 0, 0), COLOR_X),
                                ("Y", (0, axis_len, 0), COLOR_Y),
                                ("Z", (0, 0, axis_len), COLOR_Z)]:
            s = gl.GLScatterPlotItem(pos=[pos], color=[c / 255.0 for c in clr] + [1], size=12)
            self.view.addItem(s)

        # 4. 机器人位置球体
        self.robot_sphere = gl.MeshData.sphere(rows=10, cols=10, radius=0.12)
        self.robot_item = gl.GLMeshItem(meshdata=self.robot_sphere, smooth=True,
                                        color=(0, 0.7, 1, 0.9), shader="shaded")
        self.robot_item.translate(0, 0, 0)
        self.view.addItem(self.robot_item)

        # 5. 机器人朝向坐标系（三轴箭头，附着在机器人上）
        arm_len = 0.25
        self.orient_lines = gl.GLLinePlotItem(pos=np.zeros((6, 3)), color=np.zeros((6, 3)),
                                              width=2, mode='lines')
        self.view.addItem(self.orient_lines)

        # 6. 轨迹线
        self.trail_points = np.zeros((300, 3))
        self.trail_idx = 0
        self.trail_count = 0
        trail_color = np.zeros((300, 4))
        trail_color[:, 2] = 1.0   # 蓝色
        trail_color[:, 3] = np.linspace(0.1, 0.8, 300)  # 透明度渐变
        self.trail = gl.GLLinePlotItem(pos=self.trail_points, color=trail_color, width=2, mode='line_strip')
        self.view.addItem(self.trail)

        # 7. 位置标签
        self.label_pos = QLabel("位置: —  朝向: —", self)
        self.label_pos.setStyleSheet("color: #aaa; font: 12px; padding: 4px; background: rgba(0,0,0,0.6);")
        self.label_pos.setFixedHeight(28)
        layout.addWidget(self.label_pos)

    def update_pose(self, pos, rpy):
        """更新机器人位置与姿态"""
        if len(pos) < 3:
            return

        x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
        roll, pitch, yaw = (float(rpy[0]), float(rpy[1]), float(rpy[2])) if len(rpy) >= 3 else (0, 0, 0)

        # 更新球体位置
        self.robot_item.resetTransform()
        self.robot_item.translate(x, y, z)

        # 构建旋转矩阵 (ZYX 欧拉角)
        cz, sz = np.cos(yaw), np.sin(yaw)
        cy, sy = np.cos(pitch), np.sin(pitch)
        cr, sr = np.cos(roll), np.sin(roll)
        R = np.array([
            [cz*cy,  cz*sy*sr - sz*cr,  cz*sy*cr + sz*sr],
            [sz*cy,  sz*sy*sr + cz*cr,  sz*sy*cr - cz*sr],
            [-sy,    cy*sr,              cy*cr],
        ])

        # 朝向轴端点（局部坐标系 +0.25m，旋转到全局）
        arm_len = 0.25
        local_axes = np.array([
            [arm_len, 0, 0],
            [-arm_len, 0, 0],
            [0, arm_len, 0],
            [0, -arm_len, 0],
            [0, 0, arm_len],
            [0, 0, -arm_len],
        ])
        global_axes = local_axes @ R.T + np.array([x, y, z])

        # 朝向轴颜色：X红 Y绿 Z蓝
        orient_pos = global_axes
        orient_clr = np.array([
            [1,0.3,0.3], [1,0.3,0.3],
            [0.3,1,0.3], [0.3,1,0.3],
            [0.3,0.5,1], [0.3,0.5,1],
        ])
        self.orient_lines.setData(pos=orient_pos, color=orient_clr)

        # 更新轨迹
        self.trail_points[self.trail_idx] = [x, y, z]
        self.trail_idx = (self.trail_idx + 1) % 300
        self.trail_count = min(self.trail_count + 1, 300)

        # 按时间顺序排序轨迹点
        if self.trail_count < 300:
            trail = self.trail_points[:self.trail_count]
        else:
            trail = np.concatenate([self.trail_points[self.trail_idx:],
                                    self.trail_points[:self.trail_idx]])
        self.trail.setData(pos=trail)

        # 更新标签
        self.label_pos.setText(f"位置: [{x:.3f}, {y:.3f}, {z:.3f}]  "
                               f"RPY: [{np.degrees(roll):.1f}°, {np.degrees(pitch):.1f}°, {np.degrees(yaw):.1f}°]")
