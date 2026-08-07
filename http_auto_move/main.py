"""MH4 HTTP 自动移动图形程序。"""

from __future__ import annotations

import math
import sys
import time
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
    from .motion import direction_axes, scaled_duration
except ImportError:  # 支持 python3 http_auto_move/main.py
    from http_client import MH4HttpClient
    from http_worker import HttpAutoMoveWorker
    from motion import direction_axes, scaled_duration


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
        self._worker.log_msg.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.command_preview.connect(self._on_preview)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.emergency_result.connect(self._on_emergency_result)
        self._worker.finished.connect(self._on_worker_thread_finished)
        self._connected = False
        self._moving = False
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
        right_layout.addWidget(self._build_log_group(), 1)
        splitter.addWidget(right)
        splitter.setSizes([570, 670])

        self._set_connected_ui(False)

    # ── UI 创建 ──────────────────────────────────

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("HTTP 连接")
        group.setStyleSheet(self._group_style("#4fc3f7"))
        form = QFormLayout(group)

        row = QHBoxLayout()
        self.address_edit = QLineEdit("192.168.1.6:22000")
        self.address_edit.setPlaceholderText("192.168.1.6:22000")
        self.address_edit.setStyleSheet(self._input_style())
        self.address_edit.setToolTip("AP 默认 192.168.1.6:22000；网线默认 192.168.5.2:22000")
        row.addWidget(self.address_edit, 1)
        self.connect_button = QPushButton("连接")
        self.connect_button.setStyleSheet(self._button_style("#1565c0", "#1e88e5"))
        self.connect_button.clicked.connect(self._connect)
        row.addWidget(self.connect_button)
        form.addRow("控制接口:", row)

        options = QHBoxLayout()
        self.connection_type_combo = QComboBox()
        for label, value in (("AP", "AP"), ("Station", "Station"), ("4G", "4G")):
            self.connection_type_combo.addItem(label, value)
        self.connection_type_combo.setStyleSheet(self._input_style())
        options.addWidget(self.connection_type_combo)
        self.client_name_edit = QLineEdit("HTTP Auto Move")
        self.client_name_edit.setStyleSheet(self._input_style())
        options.addWidget(self.client_name_edit, 1)
        form.addRow("方式 / 名称:", options)

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
        self._add_distance_tab("前后移动", "longitudinal")
        self._add_distance_tab("左右移动", "lateral")
        self._add_rotate_tab()
        self._add_raw_tab()
        layout.addWidget(self.tabs)
        return group

    def _add_distance_tab(self, title: str, axis: str) -> None:
        tab = QWidget()
        form = QFormLayout(tab)
        if axis == "longitudinal":
            directions = (("前进", "forward"), ("后退", "backward"))
            default_speed = 0.6
            description = "btn_move.y：前进为负，后退为正（文档未定义方向，请先低幅值验证）"
        else:
            directions = (("左移", "left"), ("右移", "right"))
            default_speed = 0.4
            description = "btn_move.x：左移为负，右移为正（文档未定义方向，请先低幅值验证）"
        form.addRow(self._intro(description))

        direction = QComboBox()
        for label, value in directions:
            direction.addItem(label, value)
        direction.setStyleSheet(self._input_style())
        form.addRow("方向:", direction)

        target = self._double_spin(0.05, 100.0, 1.0, " m", 2, 0.1)
        form.addRow("目标距离:", target)
        amplitude = self._stick_spin()
        form.addRow("摇杆幅值:", amplitude)
        calibrated_rate = self._double_spin(0.01, 5.0, default_speed, " m/s", 2, 0.05)
        calibrated_rate.setToolTip("实测满摇杆速度；程序按摇杆幅值线性缩放后估算持续时间")
        form.addRow("满幅标定速度:", calibrated_rate)
        invert = QCheckBox("反转该方向的摇杆正负号")
        invert.setStyleSheet("color:#ffcc80;")
        form.addRow("方向修正:", invert)

        self._action_configs.append(
            {
                "kind": "distance",
                "title": title,
                "direction": direction,
                "target": target,
                "amplitude": amplitude,
                "rate": calibrated_rate,
                "invert": invert,
            }
        )
        self.tabs.addTab(tab, title)

    def _add_rotate_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(self._intro(
            "btn_turn.x：左转为负，右转为正；角度由“标定角速度 × 时间”开环估算。"
        ))
        direction = QComboBox()
        direction.addItem("左转", "rotate_left")
        direction.addItem("右转", "rotate_right")
        direction.setStyleSheet(self._input_style())
        form.addRow("方向:", direction)
        target = self._double_spin(1.0, 3600.0, 90.0, " °", 1, 5.0)
        form.addRow("目标角度:", target)
        amplitude = self._stick_spin()
        form.addRow("摇杆幅值:", amplitude)
        calibrated_rate = self._double_spin(1.0, 720.0, 90.0, " °/s", 1, 5.0)
        calibrated_rate.setToolTip("实测满摇杆角速度；程序按摇杆幅值线性缩放后估算持续时间")
        form.addRow("满幅标定角速度:", calibrated_rate)
        invert = QCheckBox("反转该方向的摇杆正负号")
        invert.setStyleSheet("color:#ffcc80;")
        form.addRow("方向修正:", invert)
        self._action_configs.append(
            {
                "kind": "rotate",
                "title": "原地旋转",
                "direction": direction,
                "target": target,
                "amplitude": amplitude,
                "rate": calibrated_rate,
                "invert": invert,
            }
        )
        self.tabs.addTab(tab, "原地旋转")

    def _add_raw_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(self._intro(
            "直接发送文档定义的 btn_move / btn_turn，范围 -32768～32767；结束后自动归零。"
        ))
        spins: dict[str, QSpinBox] = {}
        for name, default in (
            ("move_x", 0), ("move_y", 0), ("turn_x", 0), ("turn_y", 0)
        ):
            spin = QSpinBox()
            spin.setRange(-32768, 32767)
            spin.setValue(default)
            spin.setSingleStep(1000)
            spin.setStyleSheet(self._input_style())
            form.addRow(f"{name}:", spin)
            spins[name] = spin
        duration = self._double_spin(0.05, 600.0, 2.0, " s", 2, 0.1)
        form.addRow("持续时间:", duration)
        self._action_configs.append(
            {"kind": "raw", "title": "原始摇杆", "spins": spins, "duration": duration}
        )
        self.tabs.addTab(tab, "原始摇杆")

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
        form.addRow("循环:", loop_row)

        timings = QHBoxLayout()
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(2.0, 50.0)
        self.rate_spin.setValue(20.0)
        self.rate_spin.setSuffix(" Hz")
        self.rate_spin.setStyleSheet(self._input_style())
        timings.addWidget(self.rate_spin)
        self.settle_spin = self._double_spin(0.0, 30.0, 0.5, " s", 1, 0.1)
        timings.addWidget(self.settle_spin)
        form.addRow("发送频率 / 间隔:", timings)

        speed_row = QHBoxLayout()
        self.speed_ratio_check = QCheckBox("同步到 22002")
        self.speed_ratio_check.setChecked(False)
        self.speed_ratio_check.setToolTip("调用 /algs/settings/movement/speedRatio")
        self.speed_ratio_check.setStyleSheet("color:#80cbc4;")
        speed_row.addWidget(self.speed_ratio_check)
        self.speed_ratio_spin = QSpinBox()
        self.speed_ratio_spin.setRange(10, 100)
        self.speed_ratio_spin.setValue(50)
        self.speed_ratio_spin.setSuffix(" %")
        self.speed_ratio_spin.setStyleSheet(self._input_style())
        speed_row.addWidget(self.speed_ratio_spin)
        speed_row.addStretch()
        form.addRow("算法速度比例:", speed_row)
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
        self.battery_label = self._status_label("—")
        self.motion_label = self._status_label("—")
        self.emergency_label = self._status_label("—")
        self.heartbeat_label = self._status_label("—")
        form.addRow("连接:", self.connection_label)
        form.addRow("IMU RPY:", self.rpy_label)
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
        warning = QLabel(
            "注意：HTTP 文档无位置反馈和按距离接口；距离/角度是按标定速度换算的开环估计。"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#ffcc80; font:11px;")
        layout.addWidget(warning)
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
            )
        except Exception as exc:
            QMessageBox.warning(self, "连接参数错误", str(exc))
            return
        self.connection_label.setText("连接中…")
        self.connect_button.setEnabled(False)
        self.address_edit.setEnabled(False)
        self.connection_type_combo.setEnabled(False)
        self.client_name_edit.setEnabled(False)
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
        if command["duration"] > 120.0:
            answer = QMessageBox.question(
                self,
                "确认长时间动作",
                f"估算单次持续时间为 {command['duration']:.1f} 秒，是否继续？",
            )
            if answer != QMessageBox.Yes:
                return
        self._moving = True
        self._set_connected_ui(True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self._worker.start_move(command)

    def _build_command(self) -> dict[str, Any]:
        index = self.tabs.currentIndex()
        if not 0 <= index < len(self._action_configs):
            raise ValueError("请选择动作")
        config = self._action_configs[index]
        kind = config["kind"]
        if kind == "raw":
            axes = {name: spin.value() for name, spin in config["spins"].items()}
            duration = config["duration"].value()
        else:
            direction = config["direction"].currentData()
            axes = direction_axes(direction, config["amplitude"].value())
            if config["invert"].isChecked():
                axes = {name: -value for name, value in axes.items()}
            duration = scaled_duration(
                config["target"].value(),
                config["rate"].value(),
                config["amplitude"].value(),
            )
        return {
            "name": config["title"],
            **axes,
            "duration": duration,
            "repetitions": self.repetition_spin.value(),
            "infinite": self.infinite_check.isChecked(),
            "settle_time": self.settle_spin.value(),
            "rate_hz": self.rate_spin.value(),
            "set_speed_ratio": self.speed_ratio_check.isChecked(),
            "speed_ratio": self.speed_ratio_spin.value(),
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
                degrees = [math.degrees(float(value)) for value in rpy[:3]]
                self.rpy_label.setText(
                    f"r={degrees[0]:.1f}°  p={degrees[1]:.1f}°  y={degrees[2]:.1f}°"
                )
            except (TypeError, ValueError):
                self.rpy_label.setText(str(rpy))
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
