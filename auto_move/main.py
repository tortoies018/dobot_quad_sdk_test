"""
自动前后移动控制程序——设置移动距离、循环次数等参数，
驱动机器人往复运动，并用 IMU 数据实时矫正航向漂移。
"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QTextEdit, QStatusBar,
    QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QProgressBar, QSlider,
)

from auto_worker import AutoMoveWorker
from trajectory_plot import TrajectoryPlot


class MainWindow(QMainWindow):
    """自动前后移动主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dobot Quad 自动前后移动 (IMU矫正 + 轨迹)")
        self.setMinimumSize(1180, 780)
        self.resize(1320, 880)
        self.setStyleSheet("QMainWindow { background:#202225; }")

        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)

        # ═══════ 左侧：参数设置 ═══════
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # ── 移动参数 ──
        grp = QGroupBox("移动参数")
        grp.setStyleSheet(self._grp_style("#4fc3f7"))
        form = QFormLayout(grp)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["前后来回", "仅前进", "仅后退"])
        self.mode_combo.setStyleSheet(self._input_style())
        form.addRow("运动模式:", self.mode_combo)

        self.dist_spin = QDoubleSpinBox()
        self.dist_spin.setRange(0.1, 10.0)  # 距离上限 10 m
        self.dist_spin.setDecimals(1)
        self.dist_spin.setValue(1.0)
        self.dist_spin.setSingleStep(0.1)
        self.dist_spin.setSuffix(" m")
        self.dist_spin.setStyleSheet(self._input_style())
        form.addRow("移动距离:", self.dist_spin)

        # 循环次数 + 无限循环开关
        rep_row = QHBoxLayout()
        self.rep_spin = QSpinBox()
        self.rep_spin.setRange(1, 100)
        self.rep_spin.setValue(3)
        self.rep_spin.setSuffix(" 次")
        self.rep_spin.setStyleSheet(self._input_style())
        rep_row.addWidget(self.rep_spin)

        self.infinite_check = QCheckBox("无限循环")
        self.infinite_check.setStyleSheet("color:#ffb74d; font:13px;")
        self.infinite_check.toggled.connect(
            lambda on: self.rep_spin.setEnabled(not on))
        rep_row.addWidget(self.infinite_check)
        rep_row.addStretch()
        form.addRow("循环次数:", rep_row)

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(10, 100)   # 速度比范围 [10, 100]
        self.speed_spin.setValue(50)
        self.speed_spin.setStyleSheet(self._input_style())
        form.addRow("速度比:", self.speed_spin)

        # 速度实时调节滑块
        speed_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(10, 100)
        self.speed_slider.setValue(50)
        self.speed_slider.setOrientation(Qt.Horizontal)
        self.speed_slider.setStyleSheet("""
            QSlider::groove:horizontal { height:6px; background:#3c3f44; border-radius:3px; }
            QSlider::handle:horizontal { width:18px; margin:-6px 0; background:#29b6f6;
                                          border-radius:9px; }
        """)
        self.speed_slider.valueChanged.connect(self._on_speed_slider)
        self.speed_spin.valueChanged.connect(lambda v: self.speed_slider.setValue(v))
        speed_row.addWidget(self.speed_slider, 1)
        self.lbl_speed_val = QLabel("50")
        self.lbl_speed_val.setStyleSheet("color:#29b6f6; font:bold 14px; min-width:40px;")
        speed_row.addWidget(self.lbl_speed_val)
        form.addRow("速度(实时):", speed_row)

        self.seg_spin = QDoubleSpinBox()
        self.seg_spin.setRange(0.1, 1.0)
        self.seg_spin.setDecimals(1)
        self.seg_spin.setValue(0.3)
        self.seg_spin.setSuffix(" m")
        self.seg_spin.setToolTip("每移动一小段即用 IMU 实时矫正（闭环控制）")
        self.seg_spin.setStyleSheet(self._input_style())
        form.addRow("分段长度:", self.seg_spin)

        self.settle_spin = QDoubleSpinBox()
        self.settle_spin.setRange(0.1, 5.0)
        self.settle_spin.setDecimals(1)
        self.settle_spin.setValue(0.5)
        self.settle_spin.setSuffix(" s")
        self.settle_spin.setStyleSheet(self._input_style())
        form.addRow("稳定等待:", self.settle_spin)

        left_layout.addWidget(grp)

        # ── IMU 矫正参数 ──
        grp2 = QGroupBox("IMU 矫正")
        grp2.setStyleSheet(self._grp_style("#69f0ae"))
        form2 = QFormLayout(grp2)

        self.imu_check = QCheckBox("启用 IMU 矫正")
        self.imu_check.setChecked(True)
        self.imu_check.setStyleSheet("color:#fff; font:13px;")
        form2.addRow(self.imu_check)

        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.5, 30.0)
        self.thresh_spin.setDecimals(1)
        self.thresh_spin.setValue(3.0)
        self.thresh_spin.setSuffix(" °")
        self.thresh_spin.setStyleSheet(self._input_style())
        form2.addRow("矫正阈值:", self.thresh_spin)

        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0.1, 1.0)
        self.gain_spin.setDecimals(1)
        self.gain_spin.setValue(0.7)
        self.gain_spin.setToolTip("每次转向纠正误差的比例（0.7=转误差的70%，留余量防过冲）")
        self.gain_spin.setStyleSheet(self._input_style())
        form2.addRow("转向增益:", self.gain_spin)

        left_layout.addWidget(grp2)

        # ── 控制按钮 ──
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ 开始")
        self.btn_start.setStyleSheet(self._btn_style("#2e7d32", "#43a047"))
        self.btn_start.clicked.connect(self._start)
        btn_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(self._btn_style("#c62828", "#e53935"))
        self.btn_stop.clicked.connect(self._stop)
        btn_row.addWidget(self.btn_stop)
        left_layout.addLayout(btn_row)

        left_layout.addStretch()
        main.addWidget(left, 2)

        # ═══════ 右侧：状态 + 日志 ═══════
        right = QWidget()
        right_layout = QVBoxLayout(right)

        # 进度
        grp3 = QGroupBox("运行状态")
        grp3.setStyleSheet(self._grp_style("#ffb74d"))
        v3 = QVBoxLayout(grp3)
        self.lbl_stage = QLabel("待机")
        self.lbl_stage.setStyleSheet("color:#fff; font:bold 15px;")
        v3.addWidget(self.lbl_stage)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background:#34373c; border:1px solid #4a4d52; border-radius:4px;
                           height:20px; text-align:center; color:#fff; }
            QProgressBar::chunk { background:#29b6f6; border-radius:4px; }
        """)
        v3.addWidget(self.progress_bar)

        self.lbl_yaw = QLabel("偏航角: —    矫正量: —")
        self.lbl_yaw.setStyleSheet("color:#cfd8dc; font:13px monospace;")
        v3.addWidget(self.lbl_yaw)
        right_layout.addWidget(grp3)

        # IMU 轨迹
        grp4 = QGroupBox("IMU 轨迹")
        grp4.setStyleSheet(self._grp_style("#69f0ae"))
        v4 = QVBoxLayout(grp4)
        self.traj_plot = TrajectoryPlot()
        v4.addWidget(self.traj_plot, 1)
        btn_clear_traj = QPushButton("清空轨迹")
        btn_clear_traj.setStyleSheet("QPushButton { background:#e65100; color:#fff; padding:6px 12px; "
                                     "border:1px solid #6d6d6d; border-radius:4px; }"
                                     "QPushButton:hover { background:#f57c00; }")
        btn_clear_traj.clicked.connect(self.traj_plot.clear)
        v4.addWidget(btn_clear_traj)
        right_layout.addWidget(grp4, 1)

        # 日志
        right_layout.addWidget(QLabel("日志", styleSheet="color:#4fc3f7; font:bold 14px;"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(150)
        self._log.setStyleSheet("background:#101214; color:#7ee787; font:12px monospace; border:1px solid #3a3d42;")
        right_layout.addWidget(self._log, 1)
        main.addWidget(right, 3)

        # ═══════ 状态栏 ═══════
        self._sb = QStatusBar()
        self._sb.setStyleSheet("color:#b8bec4; background:#26292d; font:12px;")
        self.setStatusBar(self._sb)

        # ═══════ 工作线程 ═══════
        self._worker = AutoMoveWorker(addr="10.30.12.154:50051")
        self._worker.progress.connect(self._on_progress)
        self._worker.pos_ready.connect(self._on_pos)
        self._worker.log_msg.connect(self._log_msg)
        self._worker.connected.connect(self._on_connected)
        self._worker.finished_ok.connect(self._on_finished)
        self._running = False

    def _on_pos(self, x, y):
        """收到 IMU 位置：添加到轨迹图"""
        self.traj_plot.add_point(x, y)

    # ─── 样式辅助 ───────────────────────────────────

    @staticmethod
    def _grp_style(color):
        return (f"QGroupBox {{ font:bold 14px; color:{color}; border:1px solid #42464c; "
                f"border-radius:6px; margin-top:12px; padding-top:16px; background:#2b2d31; }} "
                f"QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 6px; }}")

    @staticmethod
    def _input_style():
        return ("QSpinBox, QDoubleSpinBox, QComboBox { background:#3a3d42; color:#f5f5f5; padding:5px; "
                "border:1px solid #55585e; border-radius:4px; }"
                "QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border:1px solid #29b6f6; }"
                # 下拉弹出列表：深色底 + 亮色文字，避免默认白底白字看不清
                "QComboBox QAbstractItemView { background:#2b2d31; color:#f5f5f5; "
                "border:1px solid #55585e; outline:none; "
                "selection-background-color:#29b6f6; selection-color:#fff; }"
                "QComboBox QAbstractItemView::item { padding:6px 8px; }"
                "QComboBox QAbstractItemView::item:hover { background:#3a3d42; }")

    @staticmethod
    def _btn_style(base, hover):
        return (f"QPushButton {{ background:{base}; color:#fff; font:bold 14px; "
                f"padding:10px 20px; border-radius:5px; }} "
                f"QPushButton:hover {{ background:{hover}; }} "
                f"QPushButton:disabled {{ background:#4a4d52; color:#9a9da2; }}")

    # ─── 控制 ───────────────────────────────────────

    def _start(self):
        """读取参数并启动任务"""
        if self._running:
            return

        # 同步参数到工作线程
        self._worker.mode = ["back_and_forth", "forward_only", "backward_only"][self.mode_combo.currentIndex()]
        self._worker.distance = self.dist_spin.value()
        self._worker.segment = self.seg_spin.value()
        self._worker.repetitions = self.rep_spin.value()
        self._worker.infinite = self.infinite_check.isChecked()
        self._worker.speed_ratio = self.speed_spin.value()
        self._worker.settle_time = self.settle_spin.value()
        self._worker.use_imu = self.imu_check.isChecked()
        self._worker.yaw_threshold = self.thresh_spin.value()
        self._worker.turn_gain = self.gain_spin.value()

        self._running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_stage.setText("连接中...")
        self.traj_plot.clear()   # 每次启动清空轨迹
        self._log_msg("─" * 40)
        loop_txt = "无限" if self.infinite_check.isChecked() else f"{self.rep_spin.value()}次"
        self._log_msg(f"[{self._ts()}] [INFO] 启动: 模式={self.mode_combo.currentText()} "
                      f"距离={self.dist_spin.value()}m 分段={self.seg_spin.value()}m "
                      f"循环={loop_txt} 速度={self.speed_spin.value()} "
                      f"IMU矫正={'开' if self.imu_check.isChecked() else '关'}")
        self._worker.start()

    def _on_speed_slider(self, val):
        """速度滑块实时调节：更新显示并同步到工作线程"""
        self.lbl_speed_val.setText(str(val))
        self.speed_spin.setValue(val)
        # 运行中实时生效，未运行时仅保存数值
        if self._running:
            self._worker.update_speed(val)

    def _stop(self):
        """请求停止任务"""
        self._worker.stop()
        self._log_msg(f"[{self._ts()}] [INFO] 已请求停止...")

    # ─── 信号回调 ───────────────────────────────────

    def _on_progress(self, cycle, total, stage, yaw, corr):
        """更新进度、阶段和偏航信息（total=0 表示无限循环）"""
        if total > 0:
            # 有限循环：进度条显示当前/总数
            self.lbl_stage.setText(f"{stage}")
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(cycle)
            self.progress_bar.setFormat(f"{cycle}/{total}")
        else:
            # 无限循环：显示已完成的循环次数
            self.lbl_stage.setText(f"{stage}  (第 {cycle} 次)")
            self.progress_bar.setRange(0, 0)   # 不定进度条
            self.progress_bar.setFormat(f"∞ 已循环 {cycle} 次")
        self.lbl_yaw.setText(f"偏航角: {yaw:.2f}°    矫正量: {corr:.2f}°")

    def _on_connected(self, ok):
        if ok:
            self._sb.setStyleSheet("color:#69f0ae; background:#26292d; font:12px;")

    def _on_finished(self, msg):
        """任务结束：恢复按钮"""
        self._running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_stage.setText("完成" if "完成" in msg else "停止")
        # 恢复进度条为有限循环模式
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")
        self._log_msg(f"[{self._ts()}] [INFO] 任务结束: {msg}")

    @staticmethod
    def _ts():
        """当前时间戳 HH:MM:SS"""
        import time as _t
        return _t.strftime("%H:%M:%S")

    def _log_msg(self, msg):
        self._log.append(msg)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        self._worker.stop()
        self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad 自动移动")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
