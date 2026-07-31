"""
机器人指令中心——命令按钮 + 相机画面 + 3D IMU轨迹 + 指令日志

通过高层 gRPC API (RobotClient) 向机器狗下达各种控制指令，
同时显示 DDS 相机画面和机体位姿的 3D 轨迹，并记录指令日志。
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QTextEdit, QStatusBar,
    QGridLayout, QSpinBox, QLineEdit, QFormLayout, QSplitter,
)

from robot_worker import RobotWorker
from dds_camera import FourCamWorker
from camera_view import CameraView
from viz_3d import Viz3D

# ─── 按钮样式定义 ─────────────────────────────────────
# 通用按钮基础样式（字体、内边距、圆角、最小宽度）
STYLE_BTN = "QPushButton { font:13px; padding:8px 14px; border-radius:4px; min-width:80px; }"
# 绿色：安全/正常动作按钮
STYLE_OK = STYLE_BTN + "QPushButton { background:#0a0; color:#fff; } QPushButton:hover { background:#0c0; }"
# 橙色：警告类动作按钮（如恢复、趴下）
STYLE_WARN = STYLE_BTN + "QPushButton { background:#a60; color:#fff; } QPushButton:hover { background:#c80; }"
# 红色：危险动作按钮（如紧急停止、被动）
STYLE_DANGER = STYLE_BTN + "QPushButton { background:#a33; color:#fff; } QPushButton:hover { background:#c55; }"
# 蓝色：信息类按钮（状态切换）
STYLE_INFO = STYLE_BTN + "QPushButton { background:#0af; color:#fff; } QPushButton:hover { background:#0cf; }"
# 紫色：特殊动作按钮（跳舞、跳跃等）
STYLE_SPECIAL = STYLE_BTN + "QPushButton { background:#a0a; color:#fff; } QPushButton:hover { background:#c0c; }"


class MainWindow(QMainWindow):
    """指令中心主窗口"""

    def __init__(self):
        """初始化界面布局、创建工作线程、连接信号"""
        super().__init__()
        self.setWindowTitle("Dobot Quad 指令中心")
        self.setMinimumSize(1400, 850)
        self.setStyleSheet("QMainWindow { background:#1e1e1e; }")

        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)

        # ═══════ 左侧：命令按钮区域 ═══════
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # ── 机器人状态信息栏 ──
        info = QGroupBox("机器人状态")
        info.setStyleSheet("QGroupBox { font:bold 14px; color:#0af; border:1px solid #333; border-radius:6px; "
                           "margin-top:12px; padding-top:16px; background:#252525; } "
                           "QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; }")
        form = QFormLayout(info)
        self.lbl_type = QLabel("-")   # 机器人类型
        self.lbl_fsm = QLabel("-")    # FSM 状态
        self.lbl_speed = QLabel("-")  # 速度比
        self.lbl_avoid = QLabel("-")  # 避障开关
        for l in [self.lbl_type, self.lbl_fsm, self.lbl_speed, self.lbl_avoid]:
            l.setStyleSheet("color:#fff; font:bold 14px monospace;")
        form.addRow("类型:", self.lbl_type)
        form.addRow("FSM:", self.lbl_fsm)
        form.addRow("速度:", self.lbl_speed)
        form.addRow("避障:", self.lbl_avoid)
        left_layout.addWidget(info)

        # ── 滚动命令区容器 ──
        scroll = QWidget()
        scroll_layout = QVBoxLayout(scroll)

        # ── 分组1：状态切换 ──
        grp = QGroupBox("状态切换")
        grp.setStyleSheet(info.styleSheet())
        g = QGridLayout(grp)
        g.setSpacing(4)
        for i, (t, s, ss) in enumerate([
            ("被动", "passive", STYLE_DANGER),      # 电机断电
            ("趴下", "stand_down", STYLE_WARN),     # 趴下
            ("平衡站", "balance_stand", STYLE_OK),  # 平衡站立
            ("行走", "walk", STYLE_OK),             # 行走模式
            ("奔跑", "flying_trot", STYLE_OK),      # 奔跑模式
            ("编舞", "choreo", STYLE_INFO),         # 编舞状态
            ("RL", "rl", STYLE_SPECIAL),            # RL 模式
            ("跳舞", "dance", STYLE_SPECIAL),       # 跳舞
            ("紧急", "emergency", STYLE_DANGER),    # 紧急停止
            ("恢复", "recovery", STYLE_WARN),       # 恢复/自救
            ("跳跃", "jump", STYLE_SPECIAL),        # 跳跃
            ("后空翻", "backflip", STYLE_DANGER),   # 后空翻
            ("切换腿", "change_mode", STYLE_INFO),  # 切换腿部构型
            ("挥手", "wave_hand", STYLE_SPECIAL),   # 打招呼
        ]):
            btn = QPushButton(t)
            btn.setStyleSheet(ss)
            btn.clicked.connect(lambda _, c=s: self._cmd(c))
            g.addWidget(btn, i // 4, i % 4)
        scroll_layout.addWidget(grp)

        # ── 分组2：轮足专用 ──
        grp2 = QGroupBox("轮足专用")
        grp2.setStyleSheet(info.styleSheet().replace("#0af", "#f0a"))
        g2 = QGridLayout(grp2)
        g2.setSpacing(4)
        for i, (t, s) in enumerate([("轮式", "wheel_loco"), ("漂移", "drift"), ("倒立", "handstand")]):
            btn = QPushButton(t)
            btn.setStyleSheet(STYLE_INFO)
            btn.clicked.connect(lambda _, c=s: self._cmd(c))
            g2.addWidget(btn, 0, i)
        scroll_layout.addWidget(grp2)

        # ── 分组3：运动控制 ──
        grp3 = QGroupBox("运动控制")
        grp3.setStyleSheet(info.styleSheet().replace("#0af", "#0f0"))
        g3 = QGridLayout(grp3)
        g3.setSpacing(4)
        self._dist_le = QLineEdit("1.0")   # 默认距离 1 米
        self._dist_le.setStyleSheet("background:#333; color:#fff; padding:4px; max-width:60px;")
        self._angle_le = QLineEdit("90")   # 默认角度 90 度
        self._angle_le.setStyleSheet("background:#333; color:#fff; padding:4px; max-width:60px;")
        g3.addWidget(QLabel("距离:"), 0, 0)
        g3.addWidget(self._dist_le, 0, 1)
        g3.addWidget(QLabel("角度:"), 0, 2)
        g3.addWidget(self._angle_le, 0, 3)
        for i, (t, s) in enumerate([
            ("前进", "walk_forward"),   # 向前走
            ("后退", "walk_backward"),  # 向后走
            ("左移", "move_left"),      # 向左移动
            ("右移", "move_right"),     # 向右移动
            ("左转", "rotate_left"),    # 左转
            ("右转", "rotate_right"),   # 右转
            ("左圈", "circle_left"),    # 原地左转圈
            ("右圈", "circle_right"),   # 原地右转圈
        ]):
            btn = QPushButton(t)
            btn.setStyleSheet(STYLE_OK)
            btn.clicked.connect(lambda _, c=s: self._motion(c))
            g3.addWidget(btn, 1 + i // 4, (i % 4))
        scroll_layout.addWidget(grp3)

        # ── 分组4：配置 ──
        grp4 = QGroupBox("配置")
        grp4.setStyleSheet(info.styleSheet().replace("#0af", "#fa0"))
        g4 = QFormLayout(grp4)
        self._speed_spin = QSpinBox()   # 速度比调节控件
        self._speed_spin.setRange(10, 100)  # 速度比范围 [10, 100]
        self._speed_spin.setValue(50)       # 默认 50
        self._speed_spin.setStyleSheet("background:#333; color:#fff; padding:4px;")
        btn_speed = QPushButton("设置")
        btn_speed.setStyleSheet(STYLE_OK)
        btn_speed.clicked.connect(lambda: self._cmd("set_speed_ratio", self._speed_spin.value()))
        h = QHBoxLayout()
        h.addWidget(self._speed_spin)
        h.addWidget(btn_speed)
        h.addStretch()
        g4.addRow("速度比:", h)

        self._avoid_btn = QPushButton("切换避障")
        self._avoid_btn.setStyleSheet(STYLE_WARN)
        self._avoid_btn.clicked.connect(self._toggle_avoid)
        g4.addRow(self._avoid_btn)

        btn_kill = QPushButton("安全停止 (kill_robot)")
        btn_kill.setStyleSheet(STYLE_DANGER + "QPushButton { font-weight:bold; }")
        btn_kill.clicked.connect(lambda: self._cmd("set_target_state", "passive"))
        g4.addRow(btn_kill)
        scroll_layout.addWidget(grp4)

        scroll_layout.addStretch()
        left_layout.addWidget(scroll, 1)
        main.addWidget(left, 4)

        # ═══════ 中间：四相机（缩放适应窗口） ═══════
        self._cam_view = CameraView()
        main.addWidget(self._cam_view, 6)

        # ═══════ 右侧：指令日志（可调整宽度） ═══════
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("指令日志", styleSheet="color:#0af; font:bold 14px; padding:4px;"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumWidth(260)
        self._log.setStyleSheet("background:#111; color:#0f0; font:12px monospace; border:1px solid #333;")
        right_layout.addWidget(self._log, 1)
        main.addWidget(right, 3)

        # 左侧命令区 + 3D 轨迹放在最左列（上下分割）
        # 3D IMU 轨迹视图（基于 gRPC 机体位姿），移到命令面板下方
        self._viz3d = Viz3D()
        left_split = QSplitter(Qt.Vertical)
        left_split.addWidget(left)      # 上方：命令面板
        left_split.addWidget(self._viz3d)  # 下方：3D 轨迹
        left_split.setStretchFactor(0, 3)
        left_split.setStretchFactor(1, 2)
        left_split.setStyleSheet("QSplitter::handle { background:#444; height:2px; }")
        # 将原来的 left（宽度比例4）替换为 left_split
        main.removeWidget(left)
        main.insertWidget(0, left_split, 4)

        # ═══════ 状态栏 ═══════
        self._sb = QStatusBar()
        self._sb.setStyleSheet("color:#aaa; background:#222; font:12px;")
        self.setStatusBar(self._sb)

        # ═══════ gRPC 工作线程 ═══════
        self._worker = RobotWorker(addr="192.168.1.6:50051")
        self._worker.status_updated.connect(self._on_status)  # 状态更新
        self._worker.pose_ready.connect(self._viz3d.update_pose)  # 3D 轨迹
        self._worker.command_result.connect(self._log_msg)    # 指令结果日志
        self._worker.connected.connect(self._on_connected)    # 连接状态
        self._worker.log.connect(self._sb.showMessage)        # 日志消息
        self._worker.start()

        # ═══════ DDS 四相机线程 ═══════
        cam_cfg = str(Path(__file__).resolve().parent / "config" / "dds_config.yaml")
        self._four_cam = FourCamWorker(config_path=cam_cfg)
        self._four_cam.frame_ready.connect(self._cam_view.update_frame)
        self._four_cam.log_msg.connect(self._sb.showMessage)
        self._four_cam.start()

        self._avoid_state = False  # 避障当前状态（初始关闭）

    # ─── 指令处理 ─────────────────────────────────────

    def _cmd(self, name, *args):
        """通用指令发送：通过名称调用 RobotClient 方法"""
        res = self._worker.send(name, *args)
        self._log_msg(res)

    def _motion(self, name):
        """运动指令处理：根据按钮名称自动适配参数"""
        d = float(self._dist_le.text() or "1.0")   # 读取距离输入
        a = float(self._angle_le.text() or "90")   # 读取角度输入
        if "left" in name or "right" in name:
            if "rotate" in name:
                # 左转/右转 → rotate_left(angle) / rotate_right(angle)
                self._worker.send(name, a)
            elif "circle" in name:
                # 左圈/右圈 → circle(direction, turns)
                # 将角度换算为圈数（90°/圈），限制最大 10 圈
                self._worker.send("circle", name.split("_")[1], min(int(a // 90), 10))
            elif "walk" in name:
                # 前进/后退 → walk_forward/walk_backward(distance)
                self._worker.send(name, d)
            else:
                # 左移/右移 → move_left/move_right(distance)
                self._worker.send(name, d)
        else:
            # 其他动作使用距离参数
            self._worker.send(name, d)

    def _toggle_avoid(self):
        """切换避障开关状态"""
        self._avoid_state = not self._avoid_state
        self._worker.send("set_obstacle_avoidance", self._avoid_state)

    # ─── 信号回调 ─────────────────────────────────────

    def _on_status(self, rt, fsm, speed, avoid, info, tele):
        """机器人状态更新回调：刷新状态栏标签"""
        self.lbl_type.setText(rt)
        self.lbl_fsm.setText(fsm)
        self.lbl_speed.setText(str(speed))
        self.lbl_avoid.setText("已开启" if avoid else "已关闭")
        self.lbl_avoid.setStyleSheet(
            "color:{}; font:bold 14px monospace;".format("#0f0" if avoid else "#f44")
        )

    def _on_connected(self, ok):
        """连接状态变化回调：成功时状态栏变绿"""
        if ok:
            self._sb.setStyleSheet("color:#0f0; background:#222; font:12px;")

    def _log_msg(self, msg):
        """追加一条日志消息并滚动到底部"""
        self._log.append(msg)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        """窗口关闭：停止所有后台线程并等待退出"""
        self._worker.stop()
        self._worker.wait(2000)
        self._four_cam.stop()
        self._four_cam.wait(2000)
        super().closeEvent(event)


def main():
    """程序入口：创建 Qt 应用并显示主窗口"""
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad 指令中心")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
