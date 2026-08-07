"""MH4 HTTP 自动移动图形程序。"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from .http_client import MH4HttpClient
    from .http_worker import HttpAutoMoveWorker
    from .motion import direction_axes
except ImportError:  # 支持 python3 http_auto_move/main.py
    from http_client import MH4HttpClient
    from http_worker import HttpAutoMoveWorker
    from motion import direction_axes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from auto_move.trajectory_plot import TrajectoryPlot3D


class MainWindow(QMainWindow):
    """HTTP 摇杆自动移动和状态监控窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MH4 HTTP 自动移动测试")
        self.setMinimumSize(860, 620)
        self.resize(1240, 820)
        self.setStyleSheet("QMainWindow { background:#202225; }")

        self._worker = HttpAutoMoveWorker(self)
        self._worker.connected.connect(self._on_connected)
        self._worker.exchange_data.connect(self._on_exchange)
        self._worker.odom_data.connect(self._on_odom)
        self._worker.trajectory_status.connect(self._on_trajectory_status)
        self._worker.log_msg.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.command_preview.connect(self._on_preview)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.emergency_result.connect(self._on_emergency_result)
        self._worker.finished.connect(self._on_worker_thread_finished)
        self._connected = False
        self._moving = False
        self._last_http_rpy = [0.0, 0.0, 0.0]
        self._last_position: list[float] | None = None
        self._action_configs: list[dict[str, Any]] = []

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("QSplitter::handle { background:#42464c; }")
        outer.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._build_connection_group())
        left_layout.addWidget(self._build_action_group(), 1)
        left_layout.addWidget(self._build_common_group())
        left_layout.addLayout(self._build_control_buttons())
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self._build_status_group())
        right_layout.addWidget(self._build_progress_group())
        detail_splitter = QSplitter(Qt.Vertical)
        detail_splitter.setChildrenCollapsible(False)
        detail_splitter.setHandleWidth(6)
        detail_splitter.setStyleSheet("QSplitter::handle { background:#42464c; }")
        detail_splitter.addWidget(self._build_trajectory_group())
        detail_splitter.addWidget(self._build_log_group())
        detail_splitter.setSizes([430, 190])
        right_layout.addWidget(detail_splitter, 1)
        splitter.addWidget(right)
        splitter.setSizes([570, 670])

        self._set_connected_ui(False)

    # ── UI 创建 ──────────────────────────────────

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("HTTP 连接")
        group.setStyleSheet(self._group_style("#4fc3f7"))
        form = QFormLayout(group)

        row = QHBoxLayout()
        self.address_edit = QLineEdit("10.30.12.196:22000")
        self.address_edit.setPlaceholderText("例如 10.30.12.196:22000")
        self.address_edit.setStyleSheet(self._input_style())
        self.address_edit.setToolTip("当前机器狗：10.30.12.196:22000")
        row.addWidget(self.address_edit, 1)
        self.connect_button = QPushButton("连接")
        self.connect_button.setStyleSheet(self._button_style("#1565c0", "#1e88e5"))
        self.connect_button.clicked.connect(self._connect)
        row.addWidget(self.connect_button)
        form.addRow("控制接口:", row)

        options = QHBoxLayout()
        self.connection_type_combo = QComboBox()
        for label, value in (
            ("自动检测", "Auto"),
            ("AP", "AP"),
            ("Station", "Station"),
            ("4G", "4G"),
        ):
            self.connection_type_combo.addItem(label, value)
        self.connection_type_combo.setStyleSheet(self._input_style())
        options.addWidget(self.connection_type_combo)
        self.client_name_edit = QLineEdit("HTTP Auto Move")
        self.client_name_edit.setStyleSheet(self._input_style())
        options.addWidget(self.client_name_edit, 1)
        form.addRow("方式 / 名称:", options)

        self.grpc_port_spin = QSpinBox()
        self.grpc_port_spin.setRange(1, 65535)
        self.grpc_port_spin.setValue(50051)
        self.grpc_port_spin.setStyleSheet(self._input_style())
        self.grpc_port_spin.setToolTip("只读实际位置用于轨迹；IMU 始终来自 HTTP exchange")
        form.addRow("轨迹端口:", self.grpc_port_spin)

        note = QLabel("连接后以 5 Hz 调用 /protocol/exchange，维持 occupied 状态。")
        note.setWordWrap(True)
        note.setStyleSheet("color:#a8b3bc; font:11px;")
        form.addRow(note)
        return group

    def _build_action_group(self) -> QGroupBox:
        group = QGroupBox("自动动作（HTTP 摇杆时序）")
        group.setStyleSheet(self._group_style("#69f0ae"))
        layout = QVBoxLayout(group)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #55585e; background:#303238; }"
            "QTabBar::tab { background:#3a3d42; color:#d8d8d8; padding:7px 10px; }"
            "QTabBar::tab:selected { background:#00796b; color:#fff; }"
        )
        self._add_pair_tab(
            "前后来回", "一组：前进 → 后退",
            ("前进", "forward"), ("后退", "backward"),
        )
        self._add_pair_tab(
            "左右来回", "一组：左移 → 右移",
            ("左移", "left"), ("右移", "right"),
        )
        self._add_pair_tab(
            "左右旋转", "一组：左转 → 右转",
            ("左转", "rotate_left"), ("右转", "rotate_right"),
        )
        layout.addWidget(self.tabs)
        return group

    def _add_pair_tab(
        self,
        title: str,
        description: str,
        first: tuple[str, str],
        second: tuple[str, str],
    ) -> None:
        """创建只包含摇杆幅值和两个持续时间的双向动作页签。"""
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(self._intro(
            f"{description}\n每个方向持续发送带 timestamp 的 HTTP 摇杆，结束后自动归零。"
        ))
        amplitude = self._stick_spin()
        form.addRow("摇杆幅值:", amplitude)
        first_duration = self._double_spin(0.1, 600.0, 2.0, " s", 1, 0.1)
        second_duration = self._double_spin(0.1, 600.0, 2.0, " s", 1, 0.1)
        form.addRow(f"{first[0]}持续时间:", first_duration)
        form.addRow(f"{second[0]}持续时间:", second_duration)
        self._action_configs.append({
            "title": title,
            "amplitude": amplitude,
            "segments": (
                (first[0], first[1], first_duration),
                (second[0], second[1], second_duration),
            ),
        })
        self.tabs.addTab(tab, title)

    def _build_common_group(self) -> QGroupBox:
        group = QGroupBox("执行参数")
        group.setStyleSheet(self._group_style("#ffb74d"))
        form = QFormLayout(group)

        loop_row = QHBoxLayout()
        self.repetition_spin = QSpinBox()
        self.repetition_spin.setRange(1, 999)
        self.repetition_spin.setValue(1)
        self.repetition_spin.setSuffix(" 次")
        self.repetition_spin.setStyleSheet(self._input_style())
        loop_row.addWidget(self.repetition_spin)
        self.infinite_check = QCheckBox("无限循环")
        self.infinite_check.setStyleSheet("color:#ffb74d;")
        self.infinite_check.toggled.connect(
            lambda enabled: self.repetition_spin.setEnabled(not enabled)
        )
        loop_row.addWidget(self.infinite_check)
        loop_row.addStretch()
        form.addRow("执行组数:", loop_row)

        self.settle_spin = self._double_spin(0.0, 30.0, 0.5, " s", 1, 0.1)
        self.settle_spin.setToolTip("每个方向结束并归零后，等待多久再执行下一方向")
        form.addRow("动作间隔:", self.settle_spin)

        self.prepare_action_combo = QComboBox()
        for label, action_id in (
            ("WALK (20)", 20),
            ("RL (21)", 21),
            ("FLYING_TROT (22)", 22),
            ("保持当前状态", None),
        ):
            self.prepare_action_combo.addItem(label, action_id)
        self.prepare_action_combo.setStyleSheet(self._input_style())
        self.prepare_action_combo.setToolTip("开始前通过 HTTP /settings/movement/action 切换状态")
        form.addRow("运动状态:", self.prepare_action_combo)
        return group

    def _build_control_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.start_button = QPushButton("▶ 开始")
        self.start_button.setStyleSheet(self._button_style("#2e7d32", "#43a047"))
        self.start_button.clicked.connect(self._start)
        row.addWidget(self.start_button)
        self.stop_button = QPushButton("■ 摇杆归零")
        self.stop_button.setStyleSheet(self._button_style("#ef6c00", "#fb8c00"))
        self.stop_button.clicked.connect(self._stop)
        row.addWidget(self.stop_button)
        self.emergency_button = QPushButton("急停")
        self.emergency_button.setStyleSheet(self._button_style("#b71c1c", "#d32f2f"))
        self.emergency_button.clicked.connect(lambda: self._worker.set_emergency_stop(True))
        row.addWidget(self.emergency_button)
        self.release_button = QPushButton("解除急停")
        self.release_button.setStyleSheet(self._button_style("#455a64", "#607d8b"))
        self.release_button.clicked.connect(lambda: self._worker.set_emergency_stop(False))
        row.addWidget(self.release_button)
        return row

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("exchange 实时状态")
        group.setStyleSheet(self._group_style("#4fc3f7"))
        form = QFormLayout(group)
        self.connection_label = self._status_label("未连接")
        self.rpy_label = self._status_label("—")
        self.gyro_label = self._status_label("—")
        self.accel_label = self._status_label("—")
        self.position_label = self._status_label("—")
        self.trajectory_source_label = self._status_label("未连接")
        self.battery_label = self._status_label("—")
        self.motion_label = self._status_label("—")
        self.emergency_label = self._status_label("—")
        self.heartbeat_label = self._status_label("—")
        form.addRow("连接:", self.connection_label)
        form.addRow("IMU RPY:", self.rpy_label)
        form.addRow("HTTP 陀螺仪:", self.gyro_label)
        form.addRow("HTTP 加速度:", self.accel_label)
        form.addRow("实际位置:", self.position_label)
        form.addRow("轨迹源:", self.trajectory_source_label)
        form.addRow("电池:", self.battery_label)
        form.addRow("运动状态:", self.motion_label)
        form.addRow("急停:", self.emergency_label)
        form.addRow("最近心跳:", self.heartbeat_label)
        return group

    def _build_progress_group(self) -> QGroupBox:
        group = QGroupBox("动作状态")
        group.setStyleSheet(self._group_style("#69f0ae"))
        layout = QVBoxLayout(group)
        self.stage_label = QLabel("待机")
        self.stage_label.setStyleSheet("color:#fff; font:bold 14px;")
        layout.addWidget(self.stage_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background:#34373c; border:1px solid #4a4d52; "
            "border-radius:4px; height:20px; text-align:center; color:#fff; }"
            "QProgressBar::chunk { background:#26a69a; border-radius:4px; }"
        )
        layout.addWidget(self.progress_bar)
        self.preview_label = QLabel("btn_move=(0, 0)　btn_turn=(0, 0)")
        self.preview_label.setStyleSheet(
            "color:#df70ff; background:#25272b; border:1px solid #633675; "
            "border-radius:3px; padding:6px; font:12px monospace;"
        )
        self.preview_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.preview_label)
        warning = QLabel("每组包含两个相反方向；HTTP 摇杆固定以 10 Hz 发送。")
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#ffcc80; font:11px;")
        layout.addWidget(warning)
        return group

    def _build_trajectory_group(self) -> QGroupBox:
        group = QGroupBox("实际 3D 轨迹")
        group.setStyleSheet(self._group_style("#69f0ae"))
        layout = QVBoxLayout(group)
        self.trajectory_plot = TrajectoryPlot3D()
        layout.addWidget(self.trajectory_plot, 1)
        controls = QHBoxLayout()
        hint = QLabel("绿线：实际位置　彩色轴：HTTP IMU 姿态")
        hint.setStyleSheet("color:#a8b3bc; font:11px;")
        controls.addWidget(hint)
        controls.addStretch()
        clear = QPushButton("清除轨迹")
        clear.setStyleSheet(self._button_style("#455a64", "#546e7a", compact=True))
        clear.clicked.connect(self._clear_trajectory)
        controls.addWidget(clear)
        layout.addLayout(controls)
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("日志")
        group.setStyleSheet(self._group_style("#ffb74d"))
        layout = QVBoxLayout(group)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet(
            "background:#101214; color:#7ee787; font:12px monospace; "
            "border:1px solid #3a3d42;"
        )
        layout.addWidget(self.log_edit)
        clear = QPushButton("清除日志")
        clear.setStyleSheet(self._button_style("#455a64", "#546e7a", compact=True))
        clear.clicked.connect(self.log_edit.clear)
        layout.addWidget(clear, alignment=Qt.AlignRight)
        return group

    # ── 交互 ─────────────────────────────────────

    def _connect(self) -> None:
        if self._worker.isRunning():
            return
        try:
            MH4HttpClient(self.address_edit.text())  # 仅做本地格式校验
            self._worker.configure(
                self.address_edit.text().strip(),
                self.client_name_edit.text(),
                self.connection_type_combo.currentData(),
                grpc_port=self.grpc_port_spin.value(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "连接参数错误", str(exc))
            return
        self.connection_label.setText("连接中…")
        self.connect_button.setEnabled(False)
        self.address_edit.setEnabled(False)
        self.connection_type_combo.setEnabled(False)
        self.client_name_edit.setEnabled(False)
        self.grpc_port_spin.setEnabled(False)
        self._append_log(f"[{self._time()}] [INFO] 正在连接 {self.address_edit.text().strip()}")
        self._worker.start()

    def _start(self) -> None:
        if not self._connected or self._moving:
            return
        try:
            command = self._build_command()
        except Exception as exc:
            QMessageBox.warning(self, "动作参数错误", str(exc))
            return
        longest = max(segment["duration"] for segment in command["segments"])
        if longest > 120.0:
            answer = QMessageBox.question(
                self,
                "确认长时间动作",
                f"最长单方向持续时间为 {longest:.1f} 秒，是否继续？",
            )
            if answer != QMessageBox.Yes:
                return
        self._moving = True
        self._set_connected_ui(True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.trajectory_plot.mark_start()
        self._worker.start_move(command)

    def _build_command(self) -> dict[str, Any]:
        index = self.tabs.currentIndex()
        if not 0 <= index < len(self._action_configs):
            raise ValueError("请选择动作")
        config = self._action_configs[index]
        amplitude = config["amplitude"].value()
        segments = []
        for label, direction, duration_spin in config["segments"]:
            segments.append({
                "name": label,
                **direction_axes(direction, amplitude),
                "duration": duration_spin.value(),
            })
        return {
            "name": config["title"],
            "segments": segments,
            "repetitions": self.repetition_spin.value(),
            "infinite": self.infinite_check.isChecked(),
            "settle_time": self.settle_spin.value(),
            "rate_hz": 10.0,
            "prepare_action_id": self.prepare_action_combo.currentData(),
        }

    def _stop(self) -> None:
        if not self._moving:
            return
        self._worker.stop_move()
        self.stage_label.setText("正在停止并归零摇杆…")
        self.stop_button.setEnabled(False)

    def _on_connected(self, ok: bool, detail: str) -> None:
        self._connected = ok
        if ok:
            self.connection_label.setText(f"已连接 {detail}")
            self._set_connected_ui(True)
        else:
            self.connection_label.setText(detail)
            self._moving = False
            self._set_connected_ui(False)

    def _on_worker_thread_finished(self) -> None:
        """连接失败时，等 QThread 真正结束后再允许重新连接。"""
        if not self._connected:
            self.connect_button.setEnabled(True)

    def _on_exchange(self, data: dict[str, Any]) -> None:
        imu = data.get("imu") if isinstance(data.get("imu"), dict) else {}
        rpy = imu.get("rpy", [])
        if isinstance(rpy, (list, tuple)) and len(rpy) >= 3:
            try:
                self._last_http_rpy = [float(value) for value in rpy[:3]]
                degrees = [math.degrees(float(value)) for value in rpy[:3]]
                self.rpy_label.setText(
                    f"r={degrees[0]:.1f}°  p={degrees[1]:.1f}°  y={degrees[2]:.1f}°"
                )
            except (TypeError, ValueError):
                self.rpy_label.setText(str(rpy))
        self.gyro_label.setText(self._format_vector(imu.get("gyroscope"), "rad/s"))
        self.accel_label.setText(self._format_vector(imu.get("accelerometer"), "m/s²"))
        if self._last_position is not None:
            self.trajectory_plot.update_imu_axes(
                *self._last_position, *self._last_http_rpy
            )
        bms = data.get("bms") if isinstance(data.get("bms"), dict) else {}
        battery = bms.get("battery_level", "—")
        health = bms.get("battery_health", "—")
        self.battery_label.setText(f"{battery}%（健康度 {health}%）")
        self.motion_label.setText(
            f"motion={data.get('current_motion_state', '—')}  "
            f"state={data.get('current_state', '—')}/"
            f"{data.get('current_sub_state', '—')}"
        )
        emergency = bool(data.get("emergency_stop", data.get("emergencyStop", False)))
        self.emergency_label.setText("已触发" if emergency else "未触发")
        self.emergency_label.setStyleSheet(
            "color:#ff5252; font:bold 13px monospace;" if emergency
            else "color:#69f0ae; font:13px monospace;"
        )
        self.heartbeat_label.setText(self._time())

    def _on_odom(self, data: dict[str, Any]) -> None:
        pos = data.get("pos", [])
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            return
        try:
            self._last_position = [float(value) for value in pos[:3]]
        except (TypeError, ValueError):
            return
        x, y, z = self._last_position
        self.position_label.setText(f"x={x:.3f} y={y:.3f} z={z:.3f} m")
        self.trajectory_plot.add_point(x, y, z)
        self.trajectory_plot.update_imu_axes(x, y, z, *self._last_http_rpy)

    def _on_trajectory_status(self, ok: bool, detail: str) -> None:
        self.trajectory_source_label.setText(detail)
        self.trajectory_source_label.setStyleSheet(
            "color:#69f0ae; font:13px monospace;" if ok
            else "color:#ffb74d; font:13px monospace;"
        )

    def _clear_trajectory(self) -> None:
        self.trajectory_plot.clear()
        self._append_log(f"[{self._time()}] [INFO] 已清除轨迹")

    def _on_progress(
        self, cycle: int, total: int, stage: str, percent: int
    ) -> None:
        loop = f"第 {cycle} 次" if total == 0 else f"第 {cycle}/{total} 次"
        self.stage_label.setText(f"{loop}　{stage}")
        self.progress_bar.setValue(percent)

    def _on_preview(self, data: dict[str, Any]) -> None:
        if not data:
            self.preview_label.setText("btn_move=(0, 0)　btn_turn=(0, 0)")
            return
        self.preview_label.setText(
            f"btn_move=({data['move_x']}, {data['move_y']})　"
            f"btn_turn=({data['turn_x']}, {data['turn_y']})　"
            f"剩余 {data['remaining']:.2f}s"
        )

    def _on_finished(self, message: str) -> None:
        self._moving = False
        self._set_connected_ui(self._connected)
        self.stage_label.setText(message)
        if "完成" in message:
            self.progress_bar.setValue(100)

    def _on_emergency_result(self, ok: bool, message: str) -> None:
        if ok and "已触发" in message:
            self._moving = False
            self._set_connected_ui(self._connected)
            self.stage_label.setText(message)

    def _set_connected_ui(self, connected: bool) -> None:
        self.start_button.setEnabled(connected and not self._moving)
        self.stop_button.setEnabled(connected and self._moving)
        self.emergency_button.setEnabled(connected)
        self.release_button.setEnabled(connected)
        if not connected:
            self.connect_button.setEnabled(not self._worker.isRunning())
            self.address_edit.setEnabled(True)
            self.connection_type_combo.setEnabled(True)
            self.client_name_edit.setEnabled(True)
            self.grpc_port_spin.setEnabled(True)

    def _append_log(self, message: str) -> None:
        self.log_edit.append(message)
        self.log_edit.moveCursor(QTextCursor.End)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._worker.shutdown()
        if self._worker.isRunning() and not self._worker.wait(8000):
            QMessageBox.warning(
                self,
                "正在安全停止",
                "后台 HTTP 请求尚未退出，请稍后再关闭窗口。",
            )
            event.ignore()
            return
        event.accept()

    # ── 样式与控件辅助 ───────────────────────────

    @staticmethod
    def _time() -> str:
        return time.strftime("%H:%M:%S")

    @staticmethod
    def _format_vector(values: Any, unit: str) -> str:
        if not isinstance(values, (list, tuple)) or len(values) < 3:
            return "—"
        try:
            return (
                f"x={float(values[0]):.3f} y={float(values[1]):.3f} "
                f"z={float(values[2]):.3f} {unit}"
            )
        except (TypeError, ValueError):
            return str(values)

    @staticmethod
    def _group_style(color: str) -> str:
        return (
            f"QGroupBox {{ font:bold 14px; color:{color}; border:1px solid #42464c; "
            "border-radius:6px; margin-top:12px; padding-top:16px; background:#2b2d31; } "
            "QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; } "
            "QGroupBox QLabel { color:#e0e0e0; }"
        )

    @staticmethod
    def _input_style() -> str:
        return (
            "QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit { background:#3a3d42; "
            "color:#f5f5f5; padding:5px; border:1px solid #55585e; border-radius:4px; }"
            "QComboBox QAbstractItemView { background:#2b2d31; color:#f5f5f5; "
            "selection-background-color:#00897b; }"
        )

    @staticmethod
    def _button_style(base: str, hover: str, compact: bool = False) -> str:
        padding = "5px 14px" if compact else "9px 16px"
        return (
            f"QPushButton {{ background:{base}; color:#fff; font:bold 13px; "
            f"padding:{padding}; border-radius:5px; }} "
            f"QPushButton:hover {{ background:{hover}; }} "
            "QPushButton:disabled { background:#4a4d52; color:#9a9da2; }"
        )

    @classmethod
    def _double_spin(
        cls,
        minimum: float,
        maximum: float,
        value: float,
        suffix: str,
        decimals: int,
        step: float,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setSuffix(suffix)
        spin.setStyleSheet(cls._input_style())
        return spin

    @classmethod
    def _stick_spin(cls) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(500, 32767)
        spin.setValue(8000)
        spin.setSingleStep(500)
        spin.setStyleSheet(cls._input_style())
        spin.setToolTip("建议首次使用 2000～5000 的低幅值确认方向")
        return spin

    @staticmethod
    def _intro(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setStyleSheet(
            "color:#bbdefb; background:#25272b; border:1px solid #455a64; "
            "border-radius:3px; padding:6px; font:11px monospace;"
        )
        return label

    @staticmethod
    def _status_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color:#e0e0e0; font:13px monospace;")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("MH4 HTTP Auto Move")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
