"""
IMU 轨迹绘图控件——绘制机器人在世界坐标系中的 XY 运动轨迹。

数据来源：gRPC get_state().robot_state.pos_body（IMU 融合定位）。
"""

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class TrajectoryPlot(QWidget):
    """2D 轨迹绘图：世界坐标 XY 平面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 220)
        self.setStyleSheet("background-color:#111;")

        self._points = []        # [(x, y), ...] 单位 m
        self._clear_pts = []     # 每次移动的起点标记
        self._max_points = 5000

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        bar = QLabel("  世界坐标 XY 轨迹 (IMU 融合定位)")
        bar.setStyleSheet("color:#0af; font:bold 13px; padding:4px; background:#222;")
        layout.addWidget(bar)

    def add_point(self, x, y):
        """追加一个轨迹点并触发重绘"""
        self._points.append((float(x), float(y)))
        if len(self._points) > self._max_points:
            self._points.pop(0)
        self.update()

    def mark_start(self):
        """标记当前位置为一次移动的起点"""
        if self._points:
            self._clear_pts.append(self._points[-1])

    def clear(self):
        """清空轨迹"""
        self._points.clear()
        self._clear_pts.clear()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # 无数据时提示
        if not self._points:
            painter.setPen(QPen(QColor("#555"), 1))
            painter.drawText(w // 2 - 60, h // 2, "等待 IMU 位置数据...")
            painter.end()
            return

        # 计算数据范围（自动缩放）
        xs = [p[0] for p in self._points]
        ys = [p[1] for p in self._points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # 保证最小范围，避免缩放异常（所有点重合时以点为中心展开）
        rx = max(max_x - min_x, 0.5)
        ry = max(max_y - min_y, 0.5)
        cx0, cy0 = (min_x + max_x) / 2, (min_y + max_y) / 2
        min_x, max_x = cx0 - rx, cx0 + rx
        min_y, max_y = cy0 - ry, cy0 + ry
        # 留边距
        min_x -= rx * 0.1; max_x += rx * 0.1
        min_y -= ry * 0.1; max_y += ry * 0.1
        rx = max(max_x - min_x, 0.1); ry = max(max_y - min_y, 0.1)

        def to_screen(x, y):
            sx = (x - min_x) / rx * (w - 40) + 20
            sy = h - 20 - (y - min_y) / ry * (h - 40)
            return QPointF(sx, sy)

        # 网格：每 0.5m 一格（数据范围大时自动变稀）
        painter.setPen(QPen(QColor("#222"), 1))
        grid = 0.5
        while rx / grid > 10:
            grid *= 2
        gx = int(min_x // grid) * grid
        while gx <= max_x:
            p1 = to_screen(gx, min_y)
            p2 = to_screen(gx, max_y)
            painter.drawLine(p1, p2)
            gx += grid
        gy = int(min_y // grid) * grid
        while gy <= max_y:
            p1 = to_screen(min_x, gy)
            p2 = to_screen(max_x, gy)
            painter.drawLine(p1, p2)
            gy += grid

        # 轴标签
        painter.setPen(QPen(QColor("#888"), 1))
        painter.drawText(10, 12, f"X: {min_x:.1f}~{max_x:.1f} m")
        painter.drawText(10, h - 6, f"Y: {min_y:.1f}~{max_y:.1f} m")

        # 移动起点标记（橙点）
        for sx, sy in self._clear_pts:
            p = to_screen(sx, sy)
            painter.setPen(QPen(QColor("#fa0"), 1))
            painter.setBrush(QColor("#fa0"))
            painter.drawEllipse(p, 5, 5)

        # 轨迹线（绿色）
        if len(self._points) >= 2:
            path = QPolygonF([to_screen(x, y) for x, y in self._points])
            painter.setPen(QPen(QColor("#0f0"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(path)

        # 当前位置（红点）
        if self._points:
            p = to_screen(*self._points[-1])
            painter.setPen(QPen(QColor("#f00"), 1))
            painter.setBrush(QColor("#f00"))
            painter.drawEllipse(p, 5, 5)
            painter.setPen(QPen(QColor("#fff"), 1))
            painter.drawText(int(p.x()) + 8, int(p.y()) - 4,
                             f"({self._points[-1][0]:.2f}, {self._points[-1][1]:.2f})")

        painter.end()
