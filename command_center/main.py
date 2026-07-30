"""机器人指令面板——状态显示 + 分类命令按钮"""

import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QTextEdit, QStatusBar,
    QGridLayout, QSlider, QSpinBox, QLineEdit, QFormLayout,
)

from robot_worker import RobotWorker


STYLE_BTN = "QPushButton { font:13px; padding:8px 14px; border-radius:4px; min-width:80px; }"
STYLE_OK = STYLE_BTN + "QPushButton { background:#0a0; color:#fff; } QPushButton:hover { background:#0c0; }"
STYLE_WARN = STYLE_BTN + "QPushButton { background:#a60; color:#fff; } QPushButton:hover { background:#c80; }"
STYLE_DANGER = STYLE_BTN + "QPushButton { background:#a33; color:#fff; } QPushButton:hover { background:#c55; }"
STYLE_INFO = STYLE_BTN + "QPushButton { background:#0af; color:#fff; } QPushButton:hover { background:#0cf; }"
STYLE_SPECIAL = STYLE_BTN + "QPushButton { background:#a0a; color:#fff; } QPushButton:hover { background:#c0c; }"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dobot Quad 指令中心")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet("QMainWindow { background:#1e1e1e; }")

        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)

        # ─── 左侧：命令按钮 ─────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # 信息栏
        info = QGroupBox("机器人状态")
        info.setStyleSheet("QGroupBox { font:bold 14px; color:#0af; border:1px solid #333; border-radius:6px; "
                           "margin-top:12px; padding-top:16px; background:#252525; } "
                           "QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; }")
        form = QFormLayout(info)
        self.lbl_type = QLabel("-"); self.lbl_fsm = QLabel("-"); self.lbl_speed = QLabel("-"); self.lbl_avoid = QLabel("-")
        for l in [self.lbl_type, self.lbl_fsm, self.lbl_speed, self.lbl_avoid]:
            l.setStyleSheet("color:#fff; font:bold 14px monospace;")
        form.addRow("类型:", self.lbl_type); form.addRow("FSM:", self.lbl_fsm)
        form.addRow("速度:", self.lbl_speed); form.addRow("避障:", self.lbl_avoid)
        left_layout.addWidget(info)

        # 滚动命令区
        scroll = QWidget()
        scroll_layout = QVBoxLayout(scroll)

        # 状态切换
        grp = QGroupBox("状态切换"); grp.setStyleSheet(info.styleSheet())
        g = QGridLayout(grp); g.setSpacing(4)
        for i, (t, s, ss) in enumerate([
            ("被动", "passive", STYLE_DANGER), ("趴下", "stand_down", STYLE_WARN),
            ("平衡站", "balance_stand", STYLE_OK), ("行走", "walk", STYLE_OK),
            ("奔跑", "flying_trot", STYLE_OK), ("编舞", "choreo", STYLE_INFO),
            ("RL", "rl", STYLE_SPECIAL), ("跳舞", "dance", STYLE_SPECIAL),
            ("紧急", "emergency", STYLE_DANGER), ("恢复", "recovery", STYLE_WARN),
            ("跳跃", "jump", STYLE_SPECIAL), ("后空翻", "backflip", STYLE_DANGER),
            ("切换腿", "change_mode", STYLE_INFO), ("挥手", "wave_hand", STYLE_SPECIAL),
        ]):
            btn = QPushButton(t); btn.setStyleSheet(ss)
            btn.clicked.connect(lambda _, c=s: self._cmd(c))
            g.addWidget(btn, i // 4, i % 4)
        scroll_layout.addWidget(grp)

        # 轮足专用
        grp2 = QGroupBox("轮足专用"); grp2.setStyleSheet(info.styleSheet().replace("#0af","#f0a"))
        g2 = QGridLayout(grp2); g2.setSpacing(4)
        for i, (t, s) in enumerate([("轮式", "wheel_loco"), ("漂移", "drift"), ("倒立", "handstand")]):
            btn = QPushButton(t); btn.setStyleSheet(STYLE_INFO)
            btn.clicked.connect(lambda _, c=s: self._cmd(c))
            g2.addWidget(btn, 0, i)
        scroll_layout.addWidget(grp2)

        # 运动
        grp3 = QGroupBox("运动控制"); grp3.setStyleSheet(info.styleSheet().replace("#0af","#0f0"))
        g3 = QGridLayout(grp3); g3.setSpacing(4)
        self._dist_le = QLineEdit("1.0"); self._dist_le.setStyleSheet("background:#333; color:#fff; padding:4px; max-width:60px;")
        self._angle_le = QLineEdit("90"); self._angle_le.setStyleSheet("background:#333; color:#fff; padding:4px; max-width:60px;")
        g3.addWidget(QLabel("距离:"), 0, 0); g3.addWidget(self._dist_le, 0, 1)
        g3.addWidget(QLabel("角度:"), 0, 2); g3.addWidget(self._angle_le, 0, 3)
        for i, (t, s) in enumerate([
            ("前进", "walk_forward"), ("后退", "walk_backward"),
            ("左移", "move_left"), ("右移", "move_right"),
            ("左转", "rotate_left"), ("右转", "rotate_right"),
            ("左圈", "circle_left"), ("右圈", "circle_right"),
        ]):
            btn = QPushButton(t); btn.setStyleSheet(STYLE_OK)
            btn.clicked.connect(lambda _, c=s: self._motion(c))
            g3.addWidget(btn, 1 + i // 4, (i % 4))
        scroll_layout.addWidget(grp3)

        # 配置
        grp4 = QGroupBox("配置"); grp4.setStyleSheet(info.styleSheet().replace("#0af","#fa0"))
        g4 = QFormLayout(grp4)
        self._speed_spin = QSpinBox(); self._speed_spin.setRange(10, 100); self._speed_spin.setValue(50)
        self._speed_spin.setStyleSheet("background:#333; color:#fff; padding:4px;")
        btn_speed = QPushButton("设置"); btn_speed.setStyleSheet(STYLE_OK)
        btn_speed.clicked.connect(lambda: self._cmd("set_speed_ratio", self._speed_spin.value()))
        h = QHBoxLayout(); h.addWidget(self._speed_spin); h.addWidget(btn_speed); h.addStretch()
        g4.addRow("速度比:", h)

        self._avoid_btn = QPushButton("切换避障"); self._avoid_btn.setStyleSheet(STYLE_WARN)
        self._avoid_btn.clicked.connect(self._toggle_avoid)
        g4.addRow(self._avoid_btn)

        btn_kill = QPushButton("安全停止 (kill_robot)"); btn_kill.setStyleSheet(STYLE_DANGER + "QPushButton { font-weight:bold; }")
        btn_kill.clicked.connect(lambda: self._cmd("set_target_state", "passive"))
        g4.addRow(btn_kill)
        scroll_layout.addWidget(grp4)

        scroll_layout.addStretch()
        left_layout.addWidget(scroll, 1)
        main.addWidget(left, 4)

        # ─── 右侧：日志 ───────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("指令日志", styleSheet="color:#0af; font:bold 14px; padding:4px;"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("background:#111; color:#0f0; font:12px monospace; border:1px solid #333;")
        right_layout.addWidget(self._log, 1)
        main.addWidget(right, 3)

        # ─── 状态栏 ───────────────────────────────
        self._sb = QStatusBar()
        self._sb.setStyleSheet("color:#aaa; background:#222; font:12px;")
        self.setStatusBar(self._sb)

        # ─── 工作线程 ─────────────────────────────
        self._worker = RobotWorker(addr="192.168.1.6:50051")
        self._worker.status_updated.connect(self._on_status)
        self._worker.command_result.connect(self._log_msg)
        self._worker.connected.connect(self._on_connected)
        self._worker.log.connect(self._sb.showMessage)
        self._worker.start()

        self._avoid_state = False

    def _cmd(self, name, *args):
        res = self._worker.send(name, *args)
        self._log_msg(res)

    def _motion(self, name):
        d = float(self._dist_le.text() or "1.0")
        a = float(self._angle_le.text() or "90")
        if "left" in name or "right" in name:
            if "rotate" in name:
                self._worker.send(name.replace("rotate_", "rotate"), a)
            elif "circle" in name:
                self._worker.send("circle", name.split("_")[1], min(int(a // 90), 10))
            elif "walk" in name:
                self._worker.send(name, d)
            else:
                self._worker.send(name, d)
        else:
            self._worker.send(name, d)

    def _toggle_avoid(self):
        self._avoid_state = not self._avoid_state
        self._worker.send("set_obstacle_avoidance", self._avoid_state)

    def _on_status(self, rt, fsm, speed, avoid, info, tele):
        self.lbl_type.setText(rt)
        self.lbl_fsm.setText(fsm)
        self.lbl_speed.setText(str(speed))
        self.lbl_avoid.setText("已开启" if avoid else "已关闭")
        self.lbl_avoid.setStyleSheet("color:{}; font:bold 14px monospace;".format("#0f0" if avoid else "#f44"))

    def _on_connected(self, ok):
        if ok:
            self._sb.setStyleSheet("color:#0f0; background:#222; font:12px;")

    def _log_msg(self, msg):
        self._log.append(msg)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        self._worker.stop()
        self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad 指令中心")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
