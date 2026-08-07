"""
自动移动控制程序——每个页签对应一个 SDK 动作 API，
页签内设置该 API 的参数并选择是否记录精度数据。
"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QTextEdit, QStatusBar,
    QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QProgressBar, QLineEdit,
    QSplitter, QTabWidget,
)

from auto_worker import AutoMoveWorker
from trajectory_plot import TrajectoryPlot3D


class MainWindow(QMainWindow):
    """按动作 API 组织的自动移动与精度测试主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dobot Quad 自动移动与指令测试 (3D轨迹)")
        # 主窗口本身可自由缩放；内部区域由 QSplitter 单独调节。
        self.setMinimumSize(760, 560)
        self.resize(1320, 880)
        self.setStyleSheet("QMainWindow { background:#202225; }")

        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(6)
        main_splitter.setStyleSheet("QSplitter::handle { background:#42464c; }")
        main.addWidget(main_splitter)

        # ═══════ 左侧：参数设置 ═══════
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # ── 连接设置 ──
        grp_conn = QGroupBox("连接设置")
        grp_conn.setStyleSheet(self._grp_style("#4fc3f7"))
        form_conn = QFormLayout(grp_conn)
        conn_row = QHBoxLayout()
        self.addr_edit = QLineEdit("10.30.12.21:50051")
        self.addr_edit.setPlaceholderText("例如 10.30.12.154:50051")
        self.addr_edit.setStyleSheet(self._input_style())
        self.addr_edit.setToolTip("机器人 gRPC 地址，格式：IP:端口")
        conn_row.addWidget(self.addr_edit, 1)
        self.btn_connect = QPushButton("连接")
        self.btn_connect.setStyleSheet(self._btn_style("#1565c0", "#1e88e5"))
        self.btn_connect.clicked.connect(self._on_connect)
        conn_row.addWidget(self.btn_connect)
        form_conn.addRow("机器人地址:", conn_row)
        note = QLabel("连接后轨迹/IMU 持续工作，移动指令独立下发")
        note.setStyleSheet("color:#a8b3bc; font:11px;")
        form_conn.addRow(note)
        left_layout.addWidget(grp_conn)

        # ── 动作 API 与对应参数 ──
        grp = QGroupBox("动作 API 测试")
        grp.setStyleSheet(self._grp_style("#4fc3f7"))
        form = QFormLayout(grp)

        self.command_tabs = QTabWidget()
        self.command_tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #55585e; background:#303238; }"
            "QTabBar::tab { background:#3a3d42; color:#d8d8d8; padding:7px 9px; }"
            "QTabBar::tab:selected { background:#1565c0; color:#fff; }")
        self.action_configs = []
        self.precision_checks = []
        self._add_line_walk_tab("前后移动", "longitudinal")
        self._add_line_walk_tab("左右移动", "lateral")
        self._add_rotate_tab()
        self._add_velocity_sequence_tab()
        form.addRow(self.command_tabs)

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

        self.settle_spin = QDoubleSpinBox()
        self.settle_spin.setRange(0.1, 5.0)
        self.settle_spin.setDecimals(1)
        self.settle_spin.setValue(0.5)
        self.settle_spin.setSuffix(" s")
        self.settle_spin.setStyleSheet(self._input_style())
        form.addRow("稳定等待:", self.settle_spin)

        auto_return_row = QHBoxLayout()
        self.auto_return_check = QCheckBox("启用")
        self.auto_return_check.setChecked(True)
        self.auto_return_check.setStyleSheet("color:#ffcc80; font:12px;")
        self.auto_return_check.setToolTip(
            "每组指令完成后检查；超过阈值时自动返回本次任务起点并恢复初始朝向")
        auto_return_row.addWidget(self.auto_return_check)
        self.auto_return_distance_spin = QDoubleSpinBox()
        self.auto_return_distance_spin.setRange(0.5, 100.0)
        self.auto_return_distance_spin.setDecimals(1)
        self.auto_return_distance_spin.setSingleStep(0.5)
        self.auto_return_distance_spin.setValue(5.0)
        self.auto_return_distance_spin.setSuffix(" m")
        self.auto_return_distance_spin.setStyleSheet(self._input_style())
        self.auto_return_distance_spin.setToolTip("机器人离本次任务起点超过此距离后触发回中")
        self.auto_return_check.toggled.connect(self.auto_return_distance_spin.setEnabled)
        auto_return_row.addWidget(self.auto_return_distance_spin)
        auto_return_row.addStretch()
        form.addRow("自动回中:", auto_return_row)

        left_layout.addWidget(grp)

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

        # ── 状态列表 ──
        grp_status = QGroupBox("状态")
        grp_status.setStyleSheet(self._grp_style("#ffb74d"))
        form_status = QFormLayout(grp_status)
        self.lbl_status_conn = QLabel("未连接")
        self.lbl_status_conn.setStyleSheet("color:#e0e0e0; font:13px monospace;")
        form_status.addRow("连接状态:", self.lbl_status_conn)
        self.lbl_status_pos = QLabel("—")
        self.lbl_status_pos.setStyleSheet("color:#e0e0e0; font:13px monospace;")
        form_status.addRow("当前位置:", self.lbl_status_pos)
        self.lbl_status_rpy = QLabel("—")
        self.lbl_status_rpy.setStyleSheet("color:#e0e0e0; font:13px monospace;")
        form_status.addRow("欧拉角(rad):", self.lbl_status_rpy)
        left_layout.addWidget(grp_status)

        left_layout.addStretch()
        left.setMinimumWidth(270)
        main_splitter.addWidget(left)

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
        right_layout.addWidget(grp3)

        # IMU 3D 轨迹
        grp4 = QGroupBox("IMU 3D 轨迹")
        grp4.setStyleSheet(self._grp_style("#69f0ae"))
        v4 = QVBoxLayout(grp4)
        self.traj_plot = TrajectoryPlot3D()
        v4.addWidget(self.traj_plot, 1)
        traj_button_row = QHBoxLayout()
        traj_button_row.addStretch()
        btn_clear_traj = QPushButton("清除已有轨迹")
        btn_clear_traj.setStyleSheet("QPushButton { background:#e65100; color:#fff; padding:6px 18px; "
                                     "border:1px solid #6d6d6d; border-radius:4px; }"
                                     "QPushButton:hover { background:#f57c00; }")
        btn_clear_traj.clicked.connect(self._clear_trajectory)
        traj_button_row.addWidget(btn_clear_traj)
        v4.addLayout(traj_button_row)
        hint = QLabel("左/中键平移 | 右键旋转 | 滚轮缩放 | WASDQE飞行（Shift加速）| R重置")
        hint.setStyleSheet("color:#888; font:11px;")
        hint.setAlignment(Qt.AlignCenter)
        v4.addWidget(hint)
        legend = QLabel("橙色折线/箭头: 指令移动方向　橙色点: 每段目标位置")
        legend.setStyleSheet("color:#ff9800; font:11px;")
        legend.setAlignment(Qt.AlignCenter)
        v4.addWidget(legend)
        self.lbl_command_preview = QLabel("当前指令: 待机")
        self.lbl_command_preview.setStyleSheet(
            "color:#df70ff; background:#25272b; border:1px solid #633675; "
            "border-radius:3px; padding:4px; font:12px monospace;")
        self.lbl_command_preview.setAlignment(Qt.AlignCenter)
        v4.addWidget(self.lbl_command_preview)
        # 轨迹和日志都是可调大小的子区域。
        detail_splitter = QSplitter(Qt.Vertical)
        detail_splitter.setChildrenCollapsible(False)
        detail_splitter.setHandleWidth(6)
        detail_splitter.setStyleSheet("QSplitter::handle { background:#42464c; }")
        detail_splitter.addWidget(grp4)

        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("日志", styleSheet="color:#4fc3f7; font:bold 14px;"))
        log_header.addStretch()
        btn_clear_log = QPushButton("清除日志")
        btn_clear_log.setStyleSheet(
            "QPushButton { background:#455a64; color:#fff; padding:4px 14px; "
            "border:1px solid #607d8b; border-radius:4px; }"
            "QPushButton:hover { background:#546e7a; }")
        btn_clear_log.clicked.connect(self._clear_log)
        log_header.addWidget(btn_clear_log)
        log_layout.addLayout(log_header)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(80)
        self._log.setStyleSheet("background:#101214; color:#7ee787; font:12px monospace; border:1px solid #3a3d42;")
        log_layout.addWidget(self._log)
        detail_splitter.addWidget(log_panel)
        detail_splitter.setStretchFactor(0, 4)
        detail_splitter.setStretchFactor(1, 1)
        right_layout.addWidget(detail_splitter, 1)

        right.setMinimumWidth(380)
        main_splitter.addWidget(right)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes([430, 850])

        # ═══════ 状态栏 ═══════
        self._sb = QStatusBar()
        self._sb.setStyleSheet("color:#b8bec4; background:#26292d; font:12px;")
        self.setStatusBar(self._sb)

        # ═══════ 工作线程 ═══════
        self._worker = AutoMoveWorker(addr=self.addr_edit.text().strip())
        self._worker.progress.connect(self._on_progress)
        self._worker.pos_ready.connect(self._on_pos)
        self._worker.ideal_path.connect(self.traj_plot.set_ideal_path)
        self._worker.command_preview.connect(self._on_command_preview)
        self._worker.imu_data.connect(self._on_imu_data)
        self._worker.log_msg.connect(self._log_msg)
        self._worker.connected.connect(self._on_connected)
        self._worker.finished_ok.connect(self._on_finished)
        self._running = False

    def _on_pos(self, x, y, z):
        """收到 IMU 位置：添加到 3D 轨迹图"""
        self.traj_plot.add_point(x, y, z)

    def _on_imu_data(self, data):
        """收到 IMU 数据：更新状态列表和 3D 坐标轴"""
        pos = data.get("pos", [0.0, 0.0, 0.0])
        rpy = data.get("rpy", [0.0, 0.0, 0.0])
        rpy_abs = data.get("rpy_abs", rpy)

        self.lbl_status_pos.setText(f"{pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}")
        self.lbl_status_rpy.setText(
            f"r={rpy_abs[0]:.3f} p={rpy_abs[1]:.3f} y={rpy_abs[2]:.3f}"
        )

        # 更新 3D 视图中的 IMU 本体坐标轴（相对初始姿态，站平时竖直）
        self.traj_plot.update_imu_axes(pos[0], pos[1], pos[2], rpy[0], rpy[1], rpy[2])

    def _on_command_preview(self, command):
        """显示当前实际下发的转向/移动目标，并刷新 3D 高亮图层。"""
        self.traj_plot.set_current_command(command)
        if not command:
            self.lbl_command_preview.setText("当前指令: 待机")
            return

        phase = "转向" if command.get("phase") == "turn" else "移动"
        segment = command.get("segment", 0)
        if segment < 0:
            stage = f"自动回中 第 {abs(segment)} 次{phase}"
        elif segment == 0:
            stage = "恢复初始朝向"
        else:
            stage = f"第 {segment}/4 边 {phase}"
        target = command.get("target", [0.0, 0.0, 0.0])
        turn = float(command.get("turn", 0.0))
        direction = "左" if turn > 0 else "右"
        turn_text = "无需转向" if abs(turn) <= 0.5 else f"{direction}转 {abs(turn):.1f}°"
        self.lbl_command_preview.setText(
            f"当前指令: {stage}　目标({target[0]:.2f}, {target[1]:.2f})　"
            f"{turn_text}　剩余 {float(command.get('remaining', 0.0)):.3f}m"
        )

    # ─── 样式辅助 ───────────────────────────────────

    @staticmethod
    def _grp_style(color):
        return (f"QGroupBox {{ font:bold 14px; color:{color}; border:1px solid #42464c; "
                f"border-radius:6px; margin-top:12px; padding-top:16px; background:#2b2d31; }} "
                f"QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 6px; }} "
                # 分组内的 QLabel 默认提亮，避免表单标签深底深字
                f"QGroupBox QLabel {{ color:#e0e0e0; }}")

    @staticmethod
    def _input_style():
        return ("QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit { background:#3a3d42; color:#f5f5f5; padding:5px; "
                "border:1px solid #55585e; border-radius:4px; }"
                "QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus { border:1px solid #29b6f6; }"
                # 下拉弹出列表：强制每项都有独立前景/背景色，避免跟随系统主题导致白底白字
                "QComboBox QAbstractItemView { background-color:#2b2d31; color:#f5f5f5; "
                "border:1px solid #55585e; outline:none; }"
                "QComboBox QAbstractItemView::item { color:#f5f5f5; background-color:#2b2d31; padding:6px 8px; }"
                "QComboBox QAbstractItemView::item:hover { color:#fff; background-color:#3a3d42; }"
                "QComboBox QAbstractItemView::item:selected { color:#fff; background-color:#29b6f6; }")

    @staticmethod
    def _btn_style(base, hover):
        return (f"QPushButton {{ background:{base}; color:#fff; font:bold 14px; "
                f"padding:10px 20px; border-radius:5px; }} "
                f"QPushButton:hover {{ background:{hover}; }} "
                f"QPushButton:disabled {{ background:#4a4d52; color:#9a9da2; }}")

    @staticmethod
    def _api_intro(text):
        """创建可复制的 API 调用说明。"""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setStyleSheet(
            "color:#bbdefb; background:#25272b; border:1px solid #455a64; "
            "border-radius:3px; padding:6px; font:11px monospace;"
        )
        return label

    def _add_line_walk_tab(self, tab_name, axis):
        """按前后/左右方向分别添加 line_walk 动作页签。"""
        tab = QWidget()
        form = QFormLayout(tab)
        if axis == "longitudinal":
            intro = (
                "前后移动使用 line_walk；direction: 0=前进、1=后退\n"
                "robot.line_walk(\n"
                "    direction=0,       # 前进；后退使用 1\n"
                "    distance=1.0,\n"
                "    speed_ratio=50,\n"
                "    show_progress=False,\n"
                ")"
            )
            direction_items = (("前进（0）", "forward"), ("后退（1）", "backward"))
        else:
            intro = (
                "左右移动使用 line_walk；direction: 2=左移、3=右移\n"
                "robot.line_walk(\n"
                "    direction=2,       # 左移；右移使用 3\n"
                "    distance=1.0,\n"
                "    speed_ratio=50,\n"
                "    show_progress=False,\n"
                ")"
            )
            direction_items = (("左移（2）", "left"), ("右移（3）", "right"))
        form.addRow("介绍:", self._api_intro(intro))

        direction_combo = QComboBox()
        for label, value in direction_items:
            direction_combo.addItem(label, value)
        direction_combo.setStyleSheet(self._input_style())
        form.addRow("direction:", direction_combo)

        distance_spin = QDoubleSpinBox()
        distance_spin.setRange(0.1, 3.0)
        distance_spin.setDecimals(1)
        distance_spin.setValue(1.0)
        distance_spin.setSingleStep(0.1)
        distance_spin.setSuffix(" m")
        distance_spin.setStyleSheet(self._input_style())
        form.addRow("distance:", distance_spin)

        speed_spin = QSpinBox()
        speed_spin.setRange(10, 100)
        speed_spin.setValue(50)
        speed_spin.setSuffix(" %")
        speed_spin.setStyleSheet(self._input_style())
        form.addRow("speed_ratio:", speed_spin)

        show_progress_check = QCheckBox("显示 SDK 命令行进度")
        show_progress_check.setChecked(False)
        show_progress_check.setStyleSheet("color:#b0bec5; font:12px;")
        form.addRow("show_progress:", show_progress_check)

        precision_check = self._add_precision_option(form)
        self.action_configs.append({
            "api": "line_walk",
            "mode": "line_walk",
            "axis": axis,
            "direction_combo": direction_combo,
            "distance_spin": distance_spin,
            "speed_spin": speed_spin,
            "show_progress_check": show_progress_check,
            "precision_check": precision_check,
        })
        self.command_tabs.addTab(tab, tab_name)

    def _add_rotate_tab(self):
        """添加 rotate 动作 API 页签。"""
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow("介绍:", self._api_intro(
            "原地旋转 API，direction 可使用 'left' / 'right' 或 0 / 1\n"
            "robot.rotate(\n"
            "    direction='left',\n"
            "    angle=90.0,\n"
            "    show_progress=False,\n"
            ")"
        ))

        direction_combo = QComboBox()
        direction_combo.addItem("左转（left / 0）", "left")
        direction_combo.addItem("右转（right / 1）", "right")
        direction_combo.setStyleSheet(self._input_style())
        form.addRow("direction:", direction_combo)

        angle_spin = QDoubleSpinBox()
        angle_spin.setRange(1.0, 360.0)
        angle_spin.setDecimals(1)
        angle_spin.setValue(90.0)
        angle_spin.setSingleStep(5.0)
        angle_spin.setSuffix(" °")
        angle_spin.setStyleSheet(self._input_style())
        form.addRow("angle:", angle_spin)

        show_progress_check = QCheckBox("显示 SDK 命令行进度")
        show_progress_check.setChecked(False)
        show_progress_check.setStyleSheet("color:#b0bec5; font:12px;")
        form.addRow("show_progress:", show_progress_check)

        precision_check = self._add_precision_option(form)
        self.action_configs.append({
            "api": "rotate",
            "mode": "rotate",
            "direction_combo": direction_combo,
            "angle_spin": angle_spin,
            "show_progress_check": show_progress_check,
            "precision_check": precision_check,
        })
        self.command_tabs.addTab(tab, "原地旋转")

    def _add_velocity_sequence_tab(self):
        """添加 velocity_sequence 动作 API 页签。"""
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow("介绍:", self._api_intro(
            "速度序列 API；当前界面生成一个速度段，并自动追加零速度停止段\n"
            "robot.velocity_sequence(\n"
            "    vel_seq=[(vx, vy, vyaw, duration), (0, 0, 0, 0.3)],\n"
            "    gait='walk',\n"
            "    speed_ratio=50,\n"
            "    stand_down_after=False,\n"
            "    show_progress=False,\n"
            ")"
        ))

        velocity_spins = {}
        velocity_specs = (
            ("vx", " m/s", 0.3),
            ("vy", " m/s", 0.0),
            ("vyaw", " rad/s", 0.0),
        )
        for name, suffix, default in velocity_specs:
            spin = QDoubleSpinBox()
            spin.setRange(-1.5, 1.5)
            spin.setDecimals(2)
            spin.setSingleStep(0.1)
            spin.setValue(default)
            spin.setSuffix(suffix)
            spin.setStyleSheet(self._input_style())
            form.addRow(f"{name}:", spin)
            velocity_spins[name] = spin

        duration_spin = QDoubleSpinBox()
        duration_spin.setRange(0.1, 60.0)
        duration_spin.setDecimals(1)
        duration_spin.setSingleStep(0.5)
        duration_spin.setValue(2.0)
        duration_spin.setSuffix(" s")
        duration_spin.setStyleSheet(self._input_style())
        form.addRow("duration:", duration_spin)

        gait_combo = QComboBox()
        for gait in ("walk", "flying_trot", "rl", "wheel_loco"):
            gait_combo.addItem(gait, gait)
        gait_combo.setStyleSheet(self._input_style())
        form.addRow("gait:", gait_combo)

        speed_spin = QSpinBox()
        speed_spin.setRange(10, 100)
        speed_spin.setValue(50)
        speed_spin.setSuffix(" %")
        speed_spin.setStyleSheet(self._input_style())
        form.addRow("speed_ratio:", speed_spin)

        stand_down_check = QCheckBox("执行完成后趴下")
        stand_down_check.setChecked(False)
        stand_down_check.setStyleSheet("color:#ffcc80; font:12px;")
        form.addRow("stand_down_after:", stand_down_check)

        show_progress_check = QCheckBox("显示 SDK 命令行进度")
        show_progress_check.setChecked(False)
        show_progress_check.setStyleSheet("color:#b0bec5; font:12px;")
        form.addRow("show_progress:", show_progress_check)

        precision_check = self._add_precision_option(form)
        self.action_configs.append({
            "api": "velocity_sequence",
            "mode": "velocity_sequence",
            "vx_spin": velocity_spins["vx"],
            "vy_spin": velocity_spins["vy"],
            "vyaw_spin": velocity_spins["vyaw"],
            "duration_spin": duration_spin,
            "gait_combo": gait_combo,
            "speed_spin": speed_spin,
            "stand_down_check": stand_down_check,
            "show_progress_check": show_progress_check,
            "precision_check": precision_check,
        })
        self.command_tabs.addTab(tab, "速度序列")

    def _add_precision_option(self, form):
        """为一个动作 API 添加独立的数据记录开关。"""
        check = QCheckBox("记录数据（测量精度并生成 CSV 汇总）")
        check.setStyleSheet("color:#80cbc4; font:12px;")
        check.setToolTip("记录每次 API 调用前后的 IMU 数据并计算误差")
        form.addRow("精度测量:", check)
        self.precision_checks.append(check)
        return check

    def _current_action_config(self):
        """返回当前动作 API 页签的配置。"""
        index = self.command_tabs.currentIndex()
        if not 0 <= index < len(self.action_configs):
            raise RuntimeError("未选择有效的动作 API")
        return self.action_configs[index]

    def _precision_enabled(self):
        """返回当前测试页签是否开启精度功能。"""
        return self._current_action_config()["precision_check"].isChecked()

    # ─── 控制 ───────────────────────────────────────

    def _on_connect(self):
        """连接机器人：连接后轨迹/IMU 持续工作，与移动指令独立"""
        if self._worker.isRunning():
            return
        addr = self.addr_edit.text().strip()
        if not self._validate_addr(addr):
            return
        self._worker.set_address(addr)
        self.btn_connect.setEnabled(False)
        self.addr_edit.setEnabled(False)
        self.lbl_status_conn.setText("连接中...")
        self._log_msg(f"[{self._ts()}] [INFO] 正在连接 {addr} ...")
        self._worker.start()

    def _start(self):
        """读取参数并下发移动指令（连接后即可多次下发）"""
        if self._running:
            return

        addr = self.addr_edit.text().strip()
        if not self._validate_addr(addr):
            return

        # 未连接则先连接
        if not self._worker.isRunning():
            self._worker.set_address(addr)
            self.btn_connect.setEnabled(False)
            self.addr_edit.setEnabled(False)
            self.lbl_status_conn.setText("连接中...")
            self._worker.start()

        # 根据当前命令页签组装相匹配的参数。
        config = self._current_action_config()
        mode = config["mode"]
        api_name = config["api"]
        precision_enabled = self._precision_enabled()
        params = {
            "mode": mode,
            "control_api": api_name,
            "repetitions": self.rep_spin.value(),
            "infinite": self.infinite_check.isChecked(),
            "settle_time": self.settle_spin.value(),
            "collect_data": precision_enabled,
            "auto_return": self.auto_return_check.isChecked(),
            "auto_return_distance": self.auto_return_distance_spin.value(),
        }
        if api_name == "line_walk":
            params.update({
                "direction": config["direction_combo"].currentData(),
                "distance": config["distance_spin"].value(),
                "speed_ratio": config["speed_spin"].value(),
                "show_progress": config["show_progress_check"].isChecked(),
            })
        elif api_name == "rotate":
            params.update({
                "direction": config["direction_combo"].currentData(),
                "angle": config["angle_spin"].value(),
                "speed_ratio": 50,
                "show_progress": config["show_progress_check"].isChecked(),
            })
        else:
            params.update({
                "vx": config["vx_spin"].value(),
                "vy": config["vy_spin"].value(),
                "vyaw": config["vyaw_spin"].value(),
                "duration": config["duration_spin"].value(),
                "gait": config["gait_combo"].currentData(),
                "speed_ratio": config["speed_spin"].value(),
                "stand_down_after": config["stand_down_check"].isChecked(),
                "show_progress": config["show_progress_check"].isChecked(),
            })
        self._worker.start_move(params)

        self._running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_stage.setText("连接中...")
        # 新指令只标记一个新起点，历史实测轨迹由用户手动清除。
        self.traj_plot.mark_start()
        self._log_msg("─" * 40)
        loop_txt = "无限" if self.infinite_check.isChecked() else f"{self.rep_spin.value()}次"
        if api_name == "line_walk":
            self._log_msg(
                f"[{self._ts()}] [INFO] 启动 API: line_walk("
                f"direction={params['direction']}, distance={params['distance']}m, "
                f"speed_ratio={params['speed_ratio']}, show_progress={params['show_progress']}) "
                f"循环={loop_txt}"
            )
        elif api_name == "rotate":
            self._log_msg(
                f"[{self._ts()}] [INFO] 启动 API: rotate("
                f"direction={params['direction']}, angle={params['angle']}°, "
                f"show_progress={params['show_progress']}) 循环={loop_txt}"
            )
        else:
            self._log_msg(
                f"[{self._ts()}] [INFO] 启动 API: velocity_sequence("
                f"vx={params['vx']:.2f}, vy={params['vy']:.2f}, "
                f"vyaw={params['vyaw']:.2f}, duration={params['duration']:.1f}s, "
                f"gait={params['gait']}, speed_ratio={params['speed_ratio']}, "
                f"stand_down_after={params['stand_down_after']}, "
                f"show_progress={params['show_progress']}) 循环={loop_txt}"
            )
        self._log_msg(
            f"[{self._ts()}] [INFO] 当前测试精度功能: "
            f"{'开启' if precision_enabled else '关闭'}"
            f"{'（逐条记录误差并生成汇总）' if precision_enabled else ''}"
        )
        self._log_msg(
            f"[{self._ts()}] [INFO] 自动回中: "
            f"{'开启' if self.auto_return_check.isChecked() else '关闭'}"
            f"{f'，触发距离>{self.auto_return_distance_spin.value():.1f}m' if self.auto_return_check.isChecked() else ''}"
        )
        self._log_msg(f"[{self._ts()}] [INFO] 指令已下发（轨迹/IMU 采样持续运行）")

    def _selected_mode(self):
        return self._current_action_config()["mode"]

    def _selected_mode_text(self):
        return self._current_action_config()["api"]

    def _clear_trajectory(self):
        """仅由用户操作清除历史轨迹和预览图层。"""
        self.traj_plot.clear()
        self._log_msg(f"[{self._ts()}] [INFO] 用户已清除全部轨迹")

    def _clear_log(self):
        self._log.clear()
        self._sb.showMessage("日志已清除", 2000)

    def _stop(self):
        """请求停止当前移动指令（轨迹/IMU 采样继续）"""
        self._worker.stop_move()
        self._log_msg(f"[{self._ts()}] [INFO] 已请求停止移动...")

    # ─── 信号回调 ───────────────────────────────────

    def _on_progress(self, cycle, total, stage):
        """更新进度和阶段（total=0 表示无限循环）"""
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

    def _on_connected(self, ok):
        if ok:
            self._sb.setStyleSheet("color:#69f0ae; background:#26292d; font:12px;")
            self.lbl_status_conn.setText("已连接")
            self.lbl_status_conn.setStyleSheet("color:#69f0ae; font:13px monospace;")
            self.btn_connect.setText("已连接")
            self.btn_connect.setEnabled(False)
            self.addr_edit.setEnabled(False)
        else:
            self.lbl_status_conn.setText("未连接")
            self.lbl_status_conn.setStyleSheet("color:#ef5350; font:13px monospace;")
            self.btn_connect.setText("连接")
            self.btn_connect.setEnabled(True)
            self.addr_edit.setEnabled(True)

    def _on_finished(self, msg):
        """移动指令结束：恢复按钮（连接与采样保持）"""
        self._running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_stage.setText("完成" if "完成" in msg else "停止")
        # 恢复进度条为有限循环模式
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")
        self._log_msg(f"[{self._ts()}] [INFO] 移动结束: {msg}（轨迹/IMU 采样继续运行）")

    @staticmethod
    def _ts():
        """当前时间戳 HH:MM:SS"""
        import time as _t
        return _t.strftime("%H:%M:%S")

    def _validate_addr(self, addr):
        """校验地址格式为 IP:端口"""
        if ":" not in addr:
            self._log_msg(f"[{self._ts()}] [ERROR] 地址格式错误，应为 IP:端口，当前: {addr}")
            return False
        host, port_str = addr.rsplit(":", 1)
        try:
            port = int(port_str)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self._log_msg(f"[{self._ts()}] [ERROR] 端口无效: {port_str}（应为 1~65535 的整数）")
            return False
        return True

    def _log_msg(self, msg):
        self._log.append(msg)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        self._worker.shutdown()
        self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dobot Quad 自动移动")
    win = MainWindow()
    # 默认占满当前屏幕的可用桌面区域，同时保留标题栏和还原按钮。
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
