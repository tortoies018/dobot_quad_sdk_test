# 说明图形主程序负责的界面控制与状态展示范围。
"""MH4 HTTP 自动移动图形程序。"""

# 导入本模块所需的库、类型和外部组件。
from __future__ import annotations

# 导入本模块所需的库、类型和外部组件。
import copy
import json
import math
import sys
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

# 导入本模块所需的库、类型和外部组件。
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# 尝试执行可能失败的操作并交由异常分支处理。
try:
    from .api_catalog import ENDPOINTS, ApiEndpoint
    from .http_client import MH4HttpClient
    from .http_worker import HttpAutoMoveWorker
    from .motion_totals import MotionTotals
    from .motion import direction_axes
    from .trajectory_plot import TrajectoryPlot3D
    from .video_panel import TwoVideoPanel
# 捕获异常并执行日志记录或安全降级。
except ImportError:  # 支持 python3 http_auto_move/main.py
    from api_catalog import ENDPOINTS, ApiEndpoint
    from http_client import MH4HttpClient
    from http_worker import HttpAutoMoveWorker
    from motion_totals import MotionTotals
    from motion import direction_axes
    from trajectory_plot import TrajectoryPlot3D
    from video_panel import TwoVideoPanel


# 封装主窗口、操作控件以及机器人状态展示。
class MainWindow(QMainWindow):
    """HTTP 摇杆自动移动和状态监控窗口。"""

    # 初始化对象状态以及运行所需的资源。
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MH4 HTTP 自动移动测试")
        self.setMinimumSize(860, 620)
        self.resize(1920, 1200)
        self.setStyleSheet("QMainWindow { background:#202225; }")

        # 初始化或更新本段运行所需的对象状态。
        self._worker = HttpAutoMoveWorker(self)
        self._worker.connected.connect(self._on_connected)
        self._worker.exchange_data.connect(self._on_exchange)
        self._worker.odom_data.connect(self._on_odom)
        self._worker.trajectory_status.connect(self._on_trajectory_status)
        self._worker.recovery_command.connect(self._on_recovery_command)
        self._worker.log_msg.connect(self._append_log)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.emergency_result.connect(self._on_emergency_result)
        self._worker.manual_api_result.connect(self._on_manual_api_result)
        self._worker.video_stream_result.connect(self._on_video_stream_result)
        self._worker.finished.connect(self._on_worker_thread_finished)
        self._connected = False
        self._moving = False
        self._last_http_rpy = [0.0, 0.0, 0.0]
        self._last_http_rpy_at = 0.0
        self._last_position: list[float] | None = None
        self._last_position_at = 0.0
        self._boundary_region: dict[str, Any] | None = None
        self._patrol_safe_region: dict[str, Any] | None = None
        self._boundary_points: list[list[float]] = []
        self._action_configs: list[dict[str, Any]] = []
        self._api_request_pending = False
        self._selected_api_endpoint: ApiEndpoint | None = None
        self._api_payload_template: Any | None = None
        self._api_param_widgets: dict[tuple[Any, ...], QWidget] = {}
        self._api_query_widgets: dict[str, QLineEdit] = {}
        self._motion_totals = MotionTotals()

        # 创建本区域的界面容器并准备后续布局。
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("QSplitter::handle { background:#42464c; }")
        outer.addWidget(splitter)

        # 创建本区域的界面容器并准备后续布局。
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._build_connection_group())
        left_layout.addWidget(self._build_operation_tabs(), 1)
        splitter.addWidget(left)

        # 创建本区域的界面容器并准备后续布局。
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self._build_status_group())
        detail_splitter = QSplitter(Qt.Vertical)
        detail_splitter.setChildrenCollapsible(False)
        detail_splitter.setHandleWidth(6)
        detail_splitter.setStyleSheet("QSplitter::handle { background:#42464c; }")
        detail_splitter.addWidget(self._build_monitor_tabs())
        detail_splitter.addWidget(self._build_log_group())
        detail_splitter.setSizes([430, 190])
        right_layout.addWidget(detail_splitter, 1)
        splitter.addWidget(right)
        splitter.setSizes([570, 670])

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        self._set_connected_ui(False)
        self._totals_timer = QTimer(self)
        self._totals_timer.setInterval(100)
        self._totals_timer.timeout.connect(self._update_motion_totals_display)
        self._totals_timer.start()

    # ── UI 创建 ──────────────────────────────────

    # 构建 connection_group 对应的界面区域。
    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("HTTP 连接")
        group.setStyleSheet(self._group_style("#4fc3f7"))
        form = QFormLayout(group)

        # 创建本段布局并组织对应的界面控件。
        row = QHBoxLayout()
        self.address_edit = QLineEdit("10.30.12.105:22000")
        self.address_edit.setPlaceholderText("例如 10.30.12.196:22000")
        self.address_edit.setStyleSheet(self._input_style())
        self.address_edit.setToolTip("当前机器狗：10.30.12.196:22000")
        row.addWidget(self.address_edit, 1)
        self.connect_button = QPushButton("连接")
        self.connect_button.setStyleSheet(self._button_style("#1565c0", "#1e88e5"))
        self.connect_button.clicked.connect(self._connect)
        row.addWidget(self.connect_button)
        form.addRow("控制接口:", row)

        # 创建本段布局并组织对应的界面控件。
        options = QHBoxLayout()
        self.connection_type_combo = QComboBox()
        # 逐项处理当前集合中的数据。
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

        # 创建并保存本段使用的 Qt 界面控件。
        self.grpc_port_spin = QSpinBox()
        self.grpc_port_spin.setRange(1, 65535)
        self.grpc_port_spin.setValue(50051)
        self.grpc_port_spin.setStyleSheet(self._input_style())
        self.grpc_port_spin.setToolTip("只读实际位置用于轨迹；IMU 始终来自 HTTP exchange")
        form.addRow("轨迹端口:", self.grpc_port_spin)

        # 准备本逻辑段使用的局部数据和中间状态。
        note = QLabel("连接后以 5 Hz 调用 /protocol/exchange，维持 occupied 状态。")
        note.setWordWrap(True)
        note.setStyleSheet("color:#a8b3bc; font:11px;")
        form.addRow(note)
        return group

    # 构建 operation_tabs 对应的界面区域。
    def _build_operation_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #55585e; background:#292b30; }"
            "QTabBar::tab { background:#3a3d42; color:#d8d8d8; padding:8px 14px; }"
            "QTabBar::tab:selected { background:#1565c0; color:#fff; }"
        )

        # 创建本区域的界面容器并准备后续布局。
        auto_tab = QWidget()
        auto_layout = QVBoxLayout(auto_tab)
        auto_layout.addWidget(self._build_action_group(), 1)
        auto_layout.addWidget(self._build_common_group())
        auto_layout.addWidget(self._build_boundary_group())
        auto_layout.addLayout(self._build_control_buttons())
        tabs.addTab(auto_tab, "自动来回动作")

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        tabs.addTab(self._build_api_console(), f"全部 HTTP 接口（{len(ENDPOINTS)}）")
        return tabs

    # 构建 api_console 对应的界面区域。
    def _build_api_console(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 准备本逻辑段使用的局部数据和中间状态。
        note = QLabel(
            "按钮目录来自《MH4 HTTP接口定义》：蓝色为读取，橙色为控制，红色为"
            "高风险控制。参数使用开关、下拉框和数值框，不需要填写 JSON。"
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#ffcc80; background:#342e24; border:1px solid #795548; "
            "border-radius:4px; padding:7px;"
        )
        layout.addWidget(note)

        # 创建本段布局并组织对应的界面控件。
        filters = QHBoxLayout()
        self.api_category_combo = QComboBox()
        self.api_category_combo.addItem("全部分类")
        # 逐项处理当前集合中的数据。
        for category in dict.fromkeys(endpoint.category for endpoint in ENDPOINTS):
            self.api_category_combo.addItem(category)
        self.api_category_combo.setStyleSheet(self._input_style())
        filters.addWidget(self.api_category_combo)
        self.api_search_edit = QLineEdit()
        self.api_search_edit.setPlaceholderText("搜索接口名称，例如：急停、动作、SLAM")
        self.api_search_edit.setClearButtonEnabled(True)
        self.api_search_edit.setStyleSheet(self._input_style())
        filters.addWidget(self.api_search_edit, 1)
        layout.addLayout(filters)

        # 创建本区域的界面容器并准备后续布局。
        self.api_button_widget = QWidget()
        self.api_button_widget.setStyleSheet("background:#292b30;")
        self.api_button_grid = QGridLayout(self.api_button_widget)
        self.api_button_grid.setContentsMargins(2, 2, 2, 2)
        self.api_button_grid.setSpacing(6)
        button_scroll = QScrollArea()
        button_scroll.setWidgetResizable(True)
        button_scroll.setMinimumHeight(175)
        button_scroll.setWidget(self.api_button_widget)
        button_scroll.setStyleSheet(
            "QScrollArea { border:1px solid #42464c; background:#292b30; }"
        )
        layout.addWidget(button_scroll, 2)

        # 创建并保存本段使用的 Qt 界面控件。
        self.api_selected_label = QLabel("请选择一个接口按钮")
        self.api_selected_label.setWordWrap(True)
        self.api_selected_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.api_selected_label.setStyleSheet(
            "color:#bbdefb; background:#25272b; border:1px solid #455a64; "
            "border-radius:4px; padding:6px; font:12px monospace;"
        )
        layout.addWidget(self.api_selected_label)

        # 创建本区域的界面容器并准备后续布局。
        self.api_param_widget = QWidget()
        self.api_param_widget.setStyleSheet(
            "QWidget { background:#292b30; color:#e0e0e0; }"
        )
        self.api_param_form = QFormLayout(self.api_param_widget)
        self.api_param_form.setContentsMargins(4, 4, 4, 4)
        param_scroll = QScrollArea()
        param_scroll.setWidgetResizable(True)
        param_scroll.setMinimumHeight(120)
        param_scroll.setWidget(self.api_param_widget)
        param_scroll.setStyleSheet(
            "QScrollArea { border:1px solid #42464c; background:#292b30; }"
        )
        layout.addWidget(param_scroll, 2)

        # 创建本段布局并组织对应的界面控件。
        buttons = QHBoxLayout()
        self.api_confirm_check = QCheckBox("普通 POST 也确认")
        self.api_confirm_check.setChecked(True)
        self.api_confirm_check.setStyleSheet("color:#ffb74d;")
        buttons.addWidget(self.api_confirm_check)
        buttons.addStretch()
        self.api_send_button = QPushButton("请选择接口")
        self.api_send_button.setStyleSheet(self._button_style("#1565c0", "#1e88e5"))
        self.api_send_button.clicked.connect(self._send_manual_api)
        buttons.addWidget(self.api_send_button)
        layout.addLayout(buttons)

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        layout.addWidget(QLabel("响应:"))
        self.api_response_edit = QPlainTextEdit()
        self.api_response_edit.setReadOnly(True)
        self.api_response_edit.setStyleSheet(
            "background:#101214; color:#7ee787; font:12px monospace; "
            "border:1px solid #3a3d42;"
        )
        layout.addWidget(self.api_response_edit, 2)

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        self.api_category_combo.currentTextChanged.connect(self._refresh_api_buttons)
        self.api_search_edit.textChanged.connect(self._refresh_api_buttons)
        self._refresh_api_buttons()
        safe_endpoint = next(
            endpoint for endpoint in ENDPOINTS
            if endpoint.method == "GET" and endpoint.path == "/settings/version"
        )
        self._select_api_endpoint(safe_endpoint)
        return tab

    # 构建 action_group 对应的界面区域。
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
        self._add_random_patrol_tab()
        layout.addWidget(self.tabs)
        return group

    # 封装 add_pair_tab 对应的独立处理逻辑。
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
        duration = self._double_spin(0.1, 600.0, 2.0, " s", 1, 0.1)
        duration.setToolTip("两个相反方向使用相同时间，组结束时理论上回到起点")
        form.addRow("每方向持续时间:", duration)
        self._action_configs.append({
            "title": title,
            "amplitude": amplitude,
            "segments": (
                (first[0], first[1], duration),
                (second[0], second[1], duration),
            ),
        })
        self.tabs.addTab(tab, title)

    # 封装 add_random_patrol_tab 对应的独立处理逻辑。
    def _add_random_patrol_tab(self) -> None:
        """创建只按时间运动、只在越界时回中心的随机巡逻页签。"""  # 说明本页签不再设置位置或角度容差。
        tab = QWidget()  # 创建随机巡逻页签容器。
        form = QFormLayout(tab)  # 使用表单布局排列说明和参数。
        intro = "必须先设置矩形或多点围栏。程序在可调安全距离内生成随机点，每段朝该点开环转向后按设定时间前进；橙线只限制生成点，实际出界和回中心始终以蓝色外部围栏为准。"  # 明确随机点安全线与实际出界线的不同用途。
        form.addRow(self._intro(intro))  # 把简化逻辑说明显示在页签顶部。
        move_speed = self._stick_spin()  # 创建向前巡逻摇杆幅值输入框。
        move_speed.setValue(20000)  # 设置适合首次低速测试的默认前进幅值。
        move_speed.setSuffix(" 摇杆")  # 标明该数值直接对应摇杆幅值。
        move_speed.setToolTip("向前巡逻和回中心直行使用的 HTTP 摇杆幅值")  # 解释前进速度参数用途。
        form.addRow("前进速度:", move_speed)  # 把前进速度输入框加入表单。
        turn_speed = self._stick_spin()  # 创建独立的旋转摇杆幅值输入框。
        turn_speed.setValue(32000)  # 默认使用更容易越过实机转向死区的旋转幅值。
        turn_speed.setSuffix(" 摇杆")  # 标明该数值直接对应右摇杆 X 幅值。
        turn_speed.setToolTip("随机左右转和越界回中心转向使用的 HTTP 摇杆幅值")  # 解释旋转速度不会改变直行速度。
        form.addRow("旋转速度:", turn_speed)  # 把旋转速度输入框加入表单。
        move_duration = self._double_spin(0.1, 60.0, 2.0, " s", 1, 0.1)  # 创建每段前进时间输入框。
        move_duration.setToolTip("每次随机转向后，保持向前摇杆的时间")  # 解释时间参数不代表定位距离。
        form.addRow("每段前进时间:", move_duration)  # 把前进时间输入框加入表单。
        safety_margin = self._double_spin(0.05, 10.0, 2, " m", 2, 0.05)  # 创建边界安全距离输入框。
        safety_margin.setToolTip("随机点与蓝色外部围栏至少保持此距离；橙色安全线不参与实际出界判定")  # 解释该参数只约束目标点生成。
        form.addRow("边界安全距离:", safety_margin)  # 把安全距离输入框加入表单。
        self._action_configs.append({"kind": "random_patrol", "title": "范围内简化随机巡逻", "move_speed": move_speed, "turn_speed": turn_speed, "move_duration": move_duration, "safety_margin": safety_margin})  # 保存前进、旋转、时间和安全距离控件。
        self.tabs.addTab(tab, "随机巡逻")  # 把配置页加入自动动作选项卡。

    # 构建 common_group 对应的界面区域。
    def _build_common_group(self) -> QGroupBox:
        group = QGroupBox("执行参数")
        group.setStyleSheet(self._group_style("#ffb74d"))
        form = QFormLayout(group)

        # 创建本段布局并组织对应的界面控件。
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

        # 初始化或更新本段运行所需的对象状态。
        self.settle_spin = self._double_spin(0.0, 30.0, 0.1, " s", 1, 0.1)
        self.settle_spin.setToolTip("每个方向结束并归零后，等待多久再执行下一方向")
        form.addRow("动作间隔:", self.settle_spin)

        # 创建并保存本段使用的 Qt 界面控件。
        self.prepare_action_combo = QComboBox()
        # 逐项处理当前集合中的数据。
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

    # 构建 boundary_group 对应的界面区域。
    def _build_boundary_group(self) -> QGroupBox:
        group = QGroupBox("运动范围限制（可选）")
        group.setStyleSheet(self._group_style("#80deea"))
        layout = QVBoxLayout(group)

        # 创建并保存本段使用的 Qt 界面控件。
        self.boundary_tabs = QTabWidget()
        self.boundary_tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #55585e; background:#303238; }"
            "QTabBar::tab { background:#3a3d42; color:#d8d8d8; padding:7px 14px; }"
            "QTabBar::tab:selected { background:#00796b; color:#fff; }"
        )

        # 创建本区域的界面容器并准备后续布局。
        rectangle_tab = QWidget()
        rectangle_form = QFormLayout(rectangle_tab)

        # 创建本段布局并组织对应的界面控件。
        dimensions = QHBoxLayout()
        self.boundary_length_spin = self._double_spin(
            0.4, 50.0, 2.0, " m 长", 2, 0.1
        )
        self.boundary_length_spin.setToolTip("沿设定时机身前后方向的总长度")
        dimensions.addWidget(self.boundary_length_spin)
        self.boundary_width_spin = self._double_spin(
            0.4, 50.0, 1.5, " m 宽", 2, 0.1
        )
        self.boundary_width_spin.setToolTip("沿设定时机身左右方向的总宽度")
        dimensions.addWidget(self.boundary_width_spin)
        rectangle_form.addRow("范围尺寸:", dimensions)

        # 创建并保存本段使用的 Qt 界面控件。
        self.boundary_set_button = QPushButton("以当前位置设定矩形")
        self.boundary_set_button.setStyleSheet(
            self._button_style("#00796b", "#009688", compact=True)
        )
        self.boundary_set_button.clicked.connect(self._set_boundary_from_current_pose)
        rectangle_form.addRow(self.boundary_set_button)
        self.boundary_tabs.addTab(rectangle_tab, "矩形围栏")

        # 创建本区域的界面容器并准备后续布局。
        points_tab = QWidget()
        points_form = QFormLayout(points_tab)

        # 创建本段布局并组织对应的界面控件。
        point_buttons = QHBoxLayout()
        self.boundary_point_add_button = QPushButton("记录当前位置")
        self.boundary_point_add_button.setStyleSheet(
            self._button_style("#6a1b9a", "#8e24aa", compact=True)
        )
        self.boundary_point_add_button.clicked.connect(self._add_boundary_point)
        point_buttons.addWidget(self.boundary_point_add_button)
        self.boundary_points_apply_button = QPushButton("生成多点范围")
        self.boundary_points_apply_button.setStyleSheet(
            self._button_style("#00796b", "#009688", compact=True)
        )
        self.boundary_points_apply_button.clicked.connect(
            self._set_boundary_from_points
        )
        point_buttons.addWidget(self.boundary_points_apply_button)
        self.boundary_points_clear_button = QPushButton("清除标点")
        self.boundary_points_clear_button.setStyleSheet(
            self._button_style("#455a64", "#607d8b", compact=True)
        )
        self.boundary_points_clear_button.clicked.connect(
            self._clear_boundary_points
        )
        point_buttons.addWidget(self.boundary_points_clear_button)
        points_form.addRow(point_buttons)

        # 创建并保存本段使用的 Qt 界面控件。
        self.boundary_points_label = QLabel("未记录标点（至少需要 3 个）")
        self.boundary_points_label.setWordWrap(True)
        self.boundary_points_label.setStyleSheet("color:#ce93d8; font:11px monospace;")
        points_form.addRow("标点状态:", self.boundary_points_label)
        self.boundary_tabs.addTab(points_tab, "多点围栏")
        layout.addWidget(self.boundary_tabs)

        # 创建并保存本段使用的 Qt 界面控件。
        self.boundary_status_label = QLabel("未设置：自动动作不限制范围")
        self.boundary_status_label.setWordWrap(True)
        self.boundary_status_label.setStyleSheet(
            "color:#a8b3bc; background:#25272b; border:1px solid #455a64; "
            "border-radius:4px; padding:6px; font:11px monospace;"
        )
        status_row = QHBoxLayout()
        status_row.addWidget(self.boundary_status_label, 1)
        self.boundary_clear_button = QPushButton("取消限制")
        self.boundary_clear_button.setStyleSheet(
            self._button_style("#35657b", "#607d8b", compact=True)
        )
        self.boundary_clear_button.clicked.connect(self._clear_boundary)
        status_row.addWidget(self.boundary_clear_button)
        layout.addLayout(status_row)

        # 准备本逻辑段使用的局部数据和中间状态。
        note = QLabel(
            "设定后仍使用上方动作、幅值、持续时间和执行组数；仅在越界时停止"
            "当前方向并自动插入回中心指令。多点围栏会自动取所有标点的凸包，"
            "标点顺序不限。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#ffcc80; font:11px;")
        layout.addWidget(note)

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        self.boundary_length_spin.valueChanged.connect(
            self._resize_existing_boundary
        )
        self.boundary_width_spin.valueChanged.connect(
            self._resize_existing_boundary
        )
        return group

    # 构建 control_buttons 对应的界面区域。
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

    # 构建 status_group 对应的界面区域。
    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("exchange 实时状态与本次统计")
        group.setStyleSheet(self._group_style("#4fc3f7"))
        layout = QVBoxLayout(group)

        # 创建并保存本段使用的 Qt 界面控件。
        self.status_tabs = QTabWidget()
        self.status_tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #55585e; background:#303238; }"
            "QTabBar::tab { background:#3a3d42; color:#d8d8d8; padding:7px 14px; }"
            "QTabBar::tab:selected { background:#1565c0; color:#fff; }"
        )

        # 初始化或更新本段运行所需的对象状态。
        self.connection_label = self._status_label("未连接")
        self.rpy_label = self._status_label("—")
        self.gyro_label = self._status_label("—")
        self.accel_label = self._status_label("—")
        self.position_label = self._status_label("—")
        self.total_distance_label = self._status_label("0.000 m")
        self.total_time_label = self._status_label("00:00:00.0")
        self.trajectory_source_label = self._status_label("未连接")
        self.battery_label = self._status_label("—")
        self.motion_label = self._status_label("—")
        self.emergency_label = self._status_label("—")
        self.heartbeat_label = self._status_label("—")

        # 创建本区域的界面容器并准备后续布局。
        status_tab = QWidget()
        status_columns = QHBoxLayout(status_tab)
        status_left = QFormLayout()
        status_left.addRow("连接:", self.connection_label)
        status_left.addRow("IMU RPY:", self.rpy_label)
        status_left.addRow("HTTP 陀螺仪:", self.gyro_label)
        status_left.addRow("HTTP 加速度:", self.accel_label)
        status_left.addRow("实际位置:", self.position_label)
        status_left.addRow("轨迹源:", self.trajectory_source_label)
        status_columns.addLayout(status_left, 1)
        status_columns.addSpacing(18)

        # 创建本段布局并组织对应的界面控件。
        status_right = QFormLayout()
        status_right.addRow("总里程:", self.total_distance_label)
        status_right.addRow("总时间:", self.total_time_label)
        status_right.addRow("电池:", self.battery_label)
        status_right.addRow("运动状态:", self.motion_label)
        status_right.addRow("急停:", self.emergency_label)
        status_right.addRow("最近心跳:", self.heartbeat_label)
        status_columns.addLayout(status_right, 1)
        self.status_tabs.addTab(status_tab, "实时状态")

        # 创建本区域的界面容器并准备后续布局。
        temperature_tab = QWidget()
        temperature_grid = QGridLayout(temperature_tab)
        self.imu_temperature_label = self._status_label("—")
        self.bms_pcb_temperature_label = self._status_label("—")
        self.bms_afe_temperature_label = self._status_label("—")
        temperature_summary = QHBoxLayout()
        temperature_summary.addWidget(QLabel("IMU:"))
        temperature_summary.addWidget(self.imu_temperature_label)
        temperature_summary.addStretch()
        temperature_summary.addWidget(QLabel("BMS PCB:"))
        temperature_summary.addWidget(self.bms_pcb_temperature_label)
        temperature_summary.addStretch()
        temperature_summary.addWidget(QLabel("BMS AFE:"))
        temperature_summary.addWidget(self.bms_afe_temperature_label)
        temperature_grid.addLayout(temperature_summary, 0, 0, 1, 4)

        # 逐项处理当前集合中的数据。
        for column, title in enumerate(("腿部", "伺服控制板", "MOS 管", "电机")):
            heading = QLabel(title)
            heading.setStyleSheet("color:#80deea; font:bold 12px;")
            temperature_grid.addWidget(heading, 1, column)

        # 初始化或更新本段运行所需的对象状态。
        self.joint_temperature_labels: dict[str, dict[str, QLabel]] = {}
        leg_names = (
            ("left_front_leg", "左前腿"),
            ("right_front_leg", "右前腿"),
            ("left_rear_leg", "左后腿"),
            ("right_rear_leg", "右后腿"),
        )
        temperature_fields = ("mcu_temp", "mos_temp", "motor_temp")
        # 逐项处理当前集合中的数据。
        for row, (leg_key, leg_title) in enumerate(leg_names, start=2):
            temperature_grid.addWidget(QLabel(f"{leg_title}:"), row, 0)
            field_labels: dict[str, QLabel] = {}
            # 逐项处理当前集合中的数据。
            for column, field in enumerate(temperature_fields, start=1):
                field_label = self._status_label("—")
                field_labels[field] = field_label
                temperature_grid.addWidget(field_label, row, column)
            self.joint_temperature_labels[leg_key] = field_labels
        # 逐项处理当前集合中的数据。
        for column in range(1, 4):
            temperature_grid.setColumnStretch(column, 1)
        self.status_tabs.addTab(temperature_tab, "温度")

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        layout.addWidget(self.status_tabs)
        return group

    # 在同一区域提供轨迹与前后双路视频选项卡。
    def _build_monitor_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #55585e; background:#292b30; }"
            "QTabBar::tab { background:#3a3d42; color:#d8d8d8; padding:7px 14px; }"
            "QTabBar::tab:selected { background:#00897b; color:#fff; }"
        )
        tabs.addTab(self._build_trajectory_group(), "3D 轨迹")
        self.video_panel = TwoVideoPanel()
        self.video_panel.restart_requested.connect(
            lambda: self._worker.set_video_streaming(True)
        )
        tabs.addTab(self.video_panel, "前后视频")
        return tabs

    # 构建 trajectory_group 对应的界面区域。
    def _build_trajectory_group(self) -> QGroupBox:
        group = QGroupBox("实际 3D 轨迹")
        group.setStyleSheet(self._group_style("#69f0ae"))
        layout = QVBoxLayout(group)
        self.trajectory_plot = TrajectoryPlot3D()
        layout.addWidget(self.trajectory_plot, 1)
        controls = QHBoxLayout()
        hint = QLabel(
            "绿线：实际轨迹　彩色轴：HTTP IMU　青框/黄点：限制范围/中心　"
            "紫点：围栏标点　紫线：越界回中指令"
        )
        hint.setStyleSheet("color:#a8b3bc; font:11px;")
        controls.addWidget(hint)
        controls.addStretch()
        clear = QPushButton("清除轨迹")
        clear.setStyleSheet(self._button_style("#455a64", "#546e7a", compact=True))
        clear.clicked.connect(self._clear_trajectory)
        controls.addWidget(clear)
        layout.addLayout(controls)
        return group

    # 构建 log_group 对应的界面区域。
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

    # 封装 refresh_api_buttons 对应的独立处理逻辑。
    def _refresh_api_buttons(self, *_args: Any) -> None:
        # 在运行条件成立期间持续执行本段逻辑。
        while self.api_button_grid.count():
            item = self.api_button_grid.takeAt(0)
            widget = item.widget()
            # 必要条件或数据不满足时执行安全处理。
            if widget is not None:
                widget.deleteLater()

        # 准备本逻辑段使用的局部数据和中间状态。
        category = self.api_category_combo.currentText()
        keyword = self.api_search_edit.text().strip().lower()
        visible = []
        # 逐项处理当前集合中的数据。
        for endpoint in ENDPOINTS:
            # 根据当前状态或输入选择对应的处理路径。
            if category != "全部分类" and endpoint.category != category:
                continue
            haystack = f"{endpoint.category} {endpoint.name} {endpoint.path}".lower()
            # 必要条件或数据不满足时执行安全处理。
            if keyword and keyword not in haystack:
                continue
            visible.append(endpoint)

        # 逐项处理当前集合中的数据。
        for index, endpoint in enumerate(visible):
            button = QPushButton(f"{endpoint.name}\n{endpoint.method} :{endpoint.port}")
            # 根据当前状态或输入选择对应的处理路径。
            if endpoint.dangerous:
                colors = ("#9f1d20", "#c62828")
            # 前一条件不成立时继续检查下一种情况。
            elif endpoint.method == "GET":
                colors = ("#1565c0", "#1e88e5")
            # 其余情况进入默认的处理路径。
            else:
                colors = ("#c45b00", "#ef6c00")
            button.setStyleSheet(self._button_style(*colors, compact=True))
            button.setMinimumHeight(48)
            button.setToolTip(endpoint.path)
            button.clicked.connect(
                lambda _checked=False, selected=endpoint: self._select_api_endpoint(selected)
            )
            self.api_button_grid.addWidget(button, index // 2, index % 2)

        # 必要条件或数据不满足时执行安全处理。
        if not visible:
            empty = QLabel("没有匹配的接口")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#a8b3bc; padding:20px;")
            self.api_button_grid.addWidget(empty, 0, 0, 1, 2)
            self._selected_api_endpoint = None
            # 在运行条件成立期间持续执行本段逻辑。
            while self.api_param_form.rowCount():
                self.api_param_form.removeRow(0)
            self._api_param_widgets.clear()
            self._api_query_widgets.clear()
            self._api_payload_template = None
            self.api_selected_label.setText("没有匹配的接口")
            self.api_send_button.setText("请选择接口")
            self.api_send_button.setEnabled(False)
        # 前一条件不成立时继续检查下一种情况。
        elif self._selected_api_endpoint not in visible:
            self._select_api_endpoint(visible[0])

    # 封装 select_api_endpoint 对应的独立处理逻辑。
    def _select_api_endpoint(self, endpoint: ApiEndpoint) -> None:
        self._selected_api_endpoint = endpoint
        risk = "　⚠ 高风险" if endpoint.dangerous else ""
        self.api_selected_label.setText(
            f"{endpoint.category} / {endpoint.name}{risk}\n"
            f"{endpoint.method}　端口 {endpoint.port}　{endpoint.path}"
        )
        # 在运行条件成立期间持续执行本段逻辑。
        while self.api_param_form.rowCount():
            self.api_param_form.removeRow(0)
        self._api_param_widgets.clear()
        self._api_query_widgets.clear()
        self._api_payload_template = copy.deepcopy(endpoint.payload)

        # 根据当前状态或输入选择对应的处理路径。
        if "?" in endpoint.path:
            query = endpoint.path.split("?", 1)[1]
            # 逐项处理当前集合中的数据。
            for item in query.split("&"):
                key, _, default = item.partition("=")
                edit = QLineEdit("" if default in ("xxxxxx", "mapName") else default)
                edit.setPlaceholderText(default)
                edit.setStyleSheet(self._input_style())
                self._api_query_widgets[key] = edit
                self.api_param_form.addRow(f"查询参数 {key}:", edit)

        # 准备本逻辑段使用的局部数据和中间状态。
        added = False
        # 必要条件或数据不满足时执行安全处理。
        if self._api_payload_template is not None:
            added = self._add_api_payload_controls(
                self._api_payload_template, (), endpoint.path
            )
        # 必要条件或数据不满足时执行安全处理。
        if not self._api_query_widgets and not added:
            message = (
                "此接口不需要参数"
                if endpoint.payload is None
                else "文档未提供可展开参数，将按空对象发送"
            )
            label = QLabel(message)
            label.setStyleSheet("color:#a8b3bc; padding:6px;")
            self.api_param_form.addRow(label)

        # 准备本逻辑段使用的局部数据和中间状态。
        verb = "读取" if endpoint.method == "GET" else "执行"
        self.api_send_button.setText(f"{verb}：{endpoint.name}")
        self.api_send_button.setEnabled(
            self._connected and not self._moving and not self._api_request_pending
        )

    # 封装 add_api_payload_controls 对应的独立处理逻辑。
    def _add_api_payload_controls(
        self,
        value: Any,
        field_path: tuple[Any, ...],
        endpoint_path: str,
    ) -> bool:
        added = False
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(value, dict):
            # 逐项处理当前集合中的数据。
            for key, child in value.items():
                added = self._add_api_payload_controls(
                    child, field_path + (key,), endpoint_path
                ) or added
            return added
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(value, list):
            # 逐项处理当前集合中的数据。
            for index, child in enumerate(value):
                added = self._add_api_payload_controls(
                    child, field_path + (index,), endpoint_path
                ) or added
            return added

        # 准备本逻辑段使用的局部数据和中间状态。
        field_key = ".".join(str(item) for item in field_path)
        label_text = self._api_field_label(field_path)
        choices = self._api_parameter_choices(endpoint_path, field_key)
        # 根据当前状态或输入选择对应的处理路径。
        if choices:
            widget = QComboBox()
            # 逐项处理当前集合中的数据。
            for text_value, data_value in choices:
                widget.addItem(text_value, data_value)
            # 按照输入值选择对应的处理分支。
            match = widget.findData(value)
            # 根据当前状态或输入选择对应的处理路径。
            if match >= 0:
                widget.setCurrentIndex(match)
            widget.setStyleSheet(self._input_style())
        # 前一条件不成立时继续检查下一种情况。
        elif isinstance(value, bool):
            widget = QCheckBox("开启 / 是")
            widget.setChecked(value)
            widget.setStyleSheet("color:#e0e0e0;")
        # 前一条件不成立时继续检查下一种情况。
        elif isinstance(value, int):
            widget = QSpinBox()
            minimum, maximum = self._api_integer_range(endpoint_path, field_key)
            widget.setRange(minimum, maximum)
            widget.setValue(max(minimum, min(maximum, value)))
            widget.setStyleSheet(self._input_style())
        # 前一条件不成立时继续检查下一种情况。
        elif isinstance(value, float):
            widget = QDoubleSpinBox()
            widget.setRange(-1_000_000.0, 1_000_000.0)
            widget.setDecimals(4)
            widget.setValue(value)
            widget.setStyleSheet(self._input_style())
        # 前一条件不成立时继续检查下一种情况。
        elif endpoint_path == "/upload/formdata/audio" and field_key == "file":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            widget = QLineEdit(str(value))
            widget.setReadOnly(True)
            widget.setPlaceholderText("请选择音频文件")
            widget.setStyleSheet(self._input_style())
            row_layout.addWidget(widget, 1)
            choose = QPushButton("选择文件")
            choose.setStyleSheet(self._button_style("#455a64", "#607d8b", compact=True))
            choose.clicked.connect(lambda: self._choose_api_audio_file(widget))
            row_layout.addWidget(choose)
            self._api_param_widgets[field_path] = widget
            self.api_param_form.addRow(f"{label_text}:", row)
            return True
        # 其余情况进入默认的处理路径。
        else:
            widget = QLineEdit("" if value is None else str(value))
            widget.setStyleSheet(self._input_style())

        # 初始化或更新本段运行所需的对象状态。
        self._api_param_widgets[field_path] = widget
        self.api_param_form.addRow(f"{label_text}:", widget)
        return True

    # 封装 choose_api_audio_file 对应的独立处理逻辑。
    def _choose_api_audio_file(self, target: QLineEdit) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择要上传的音频文件",
            "",
            "音频文件 (*.wav *.mp3 *.aac *.m4a *.ogg);;所有文件 (*)",
        )
        # 根据当前状态或输入选择对应的处理路径。
        if path:
            target.setText(path)

    # 封装 api_field_label 对应的独立处理逻辑。
    @staticmethod
    def _api_field_label(field_path: tuple[Any, ...]) -> str:
        text = ""
        # 逐项处理当前集合中的数据。
        for item in field_path:
            # 根据当前状态或输入选择对应的处理路径。
            if isinstance(item, int):
                text += f"[{item}]"
            # 其余情况进入默认的处理路径。
            else:
                text += ("." if text else "") + str(item)
        return text

    # 封装 api_parameter_choices 对应的独立处理逻辑。
    @staticmethod
    def _api_parameter_choices(
        endpoint_path: str, field_key: str
    ) -> list[tuple[str, Any]]:
        choices = {
            ("/connection/state", "connectionType"): [
                ("Station", "Station"), ("AP", "AP"), ("4G", "4G")
            ],
            ("/connection/type", "value"): [("Station", "Station"), ("AP", "AP")],
            ("/settings/streaming/record", "action"): [("开始", "start"), ("停止", "stop")],
            ("/settings/streaming/record", "camera"): [("前摄像头", "front"), ("后摄像头", "back")],
            ("/settings/streaming/switch", "camera"): [("前摄像头", "front"), ("后摄像头", "back")],
            ("/settings/streaming/agora/start", "camera"): [("前摄像头", "front"), ("后摄像头", "back")],
            ("/settings/language", "language"): [("中文", "zh-Hans"), ("英文", "en")],
            ("/settings/voice/property", "type"): [("循环", 0), ("单次", 1), ("多次", 2)],
            ("/upload/url/audio", "type"): [("音频", "audio"), ("喊话", "shout")],
            ("/upload/formdata/audio", "type"): [("音频", "audio"), ("喊话", "shout")],
            ("/upload/tts/audio", "type"): [("文字转语音", "tts"), ("音频", "audio"), ("喊话", "shout")],
            ("/download/logs/upload", "module"): [("控制器", "controller"), ("算法", "algorithm"), ("全部", "all")],
            ("/algs/slam/new", "action"): [("开始", "start"), ("停止", "stop"), ("取消", "cancel")],
            ("/algs/slam/initPosition", "type"): [("地图坐标", "map"), ("图像坐标", "image")],
            ("/algs/slam/roadNetwork", "roadNetworkPoints.0.pose.type"): [("地图坐标", "map"), ("图像坐标", "image")],
            ("/algs/slam/startSinglePointPatrol", "position.type"): [("地图坐标", "map"), ("图像坐标", "image")],
            ("/algs/slam/updateNetworkPatrolStatus", "status"): [("暂停", "pause"), ("巡逻", "patrolling"), ("取消", "cancel")],
            ("/algs/slam/updateSinglePointPatrolStatus", "status"): [("暂停", "pause"), ("巡逻", "patrolling"), ("取消", "cancel")],
            ("/algs/settings/movement/speedMode", "mode"): [("低速", "low"), ("高速", "high")],
            ("/algs/settings/autoIntelligence/follow", "open"): [("关闭", 0), ("开启", 1), ("预跟随", 2)],
            ("/algs/settings/autoIntelligence/follow", "type"): [("后跟随", "rear"), ("前跟随", "front")],
            ("/algs/settings/autoIntelligence/follow", "distance"): [("1.5 m", 1.5), ("3.0 m", 3.0)],
        }
        return choices.get((endpoint_path, field_key), [])

    # 封装 api_integer_range 对应的独立处理逻辑。
    @staticmethod
    def _api_integer_range(endpoint_path: str, field_key: str) -> tuple[int, int]:
        # 根据当前状态或输入选择对应的处理路径。
        if endpoint_path == "/settings/movement/joystickControl" and field_key.endswith((".x", ".y")):
            return -32768, 32767
        # 根据当前状态或输入选择对应的处理路径。
        if field_key == "currentClient":
            return 1, 4
        # 根据当前状态或输入选择对应的处理路径。
        if field_key in ("id", "index", "repeatCount", "cycleTime"):
            return 0, 1_000_000
        # 根据当前状态或输入选择对应的处理路径。
        if field_key == "volume":
            return 0, 100
        # 根据当前状态或输入选择对应的处理路径。
        if field_key == "ratio":
            return 10, 100
        # 根据当前状态或输入选择对应的处理路径。
        if field_key == "role":
            return 1, 2
        return -1_000_000_000, 1_000_000_000

    # 封装 read_api_payload 对应的独立处理逻辑。
    def _read_api_payload(self, value: Any, field_path: tuple[Any, ...] = ()) -> Any:
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(value, dict):
            return {
                key: self._read_api_payload(child, field_path + (key,))
                for key, child in value.items()
            }
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(value, list):
            return [
                self._read_api_payload(child, field_path + (index,))
                for index, child in enumerate(value)
            ]
        widget = self._api_param_widgets[field_path]
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(widget, QComboBox):
            return widget.currentData()        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(widget, QLineEdit):
            return widget.text()
        return value

    # 封装 selected_api_path 对应的独立处理逻辑。
    def _selected_api_path(self, endpoint: ApiEndpoint) -> str:
        base = endpoint.path.split("?", 1)[0]
        # 必要条件或数据不满足时执行安全处理。
        if not self._api_query_widgets:
            return base
        query = urlencode({
            key: widget.text().strip()
            for key, widget in self._api_query_widgets.items()
        })
        return f"{base}?{query}"

    # 封装 send_manual_api 对应的独立处理逻辑。
    def _send_manual_api(self) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if not self._connected:
            QMessageBox.warning(self, "尚未连接", "请先连接机器狗再调用接口。")
            return
        # 根据当前状态或输入选择对应的处理路径。
        if self._moving:
            QMessageBox.warning(self, "动作执行中", "请先停止自动动作再调用手动接口。")
            return
        # 根据当前状态或输入选择对应的处理路径。
        if self._api_request_pending:
            return
        endpoint = self._selected_api_endpoint
        # 必要条件或数据不满足时执行安全处理。
        if endpoint is None:
            QMessageBox.warning(self, "未选择接口", "请先点击一个接口按钮。")
            return

        # 准备本逻辑段使用的局部数据和中间状态。
        method = endpoint.method
        port = endpoint.port
        path = self._selected_api_path(endpoint)
        # 必要条件或数据不满足时执行安全处理。
        if any(not widget.text().strip() for widget in self._api_query_widgets.values()):
            QMessageBox.warning(self, "缺少查询参数", "请填写所有查询参数。")
            return
        payload = (
            self._read_api_payload(self._api_payload_template)
            if endpoint.method == "POST" and endpoint.payload is not None
            else None
        )

        # 准备本逻辑段使用的局部数据和中间状态。
        must_confirm = endpoint.dangerous or (
            endpoint.method == "POST" and self.api_confirm_check.isChecked()
        )
        # 根据当前状态或输入选择对应的处理路径。
        if must_confirm:
            level = "高风险接口" if endpoint.dangerous else "写入接口"
            answer = QMessageBox.question(
                self,
                f"确认{level}",
                f"即将发送：\n{method} :{port}{path}\n\n"
                "该请求可能改变机器人状态，是否继续？",
            )
            # 根据当前状态或输入选择对应的处理路径。
            if answer != QMessageBox.Yes:
                return

        # 初始化或更新本段运行所需的对象状态。
        self._api_request_pending = True
        self.api_send_button.setEnabled(False)
        self.api_response_edit.setPlainText(
            f"请求中…\n{method} :{port}{path}"
        )
        self._worker.call_api(method, path, payload, port)

    # 处理 manual_api_result 事件并同步界面状态。
    def _on_manual_api_result(
        self, ok: bool, request_description: str, result: Any
    ) -> None:
        self._api_request_pending = False
        self.api_send_button.setEnabled(self._connected and not self._moving)
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            response = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError):
            response = str(result)
        status = "成功" if ok else "失败或控制器拒绝"
        self.api_response_edit.setPlainText(
            f"{status}\n{request_description}\n\n{response}"
        )

    # 封装 connect 对应的独立处理逻辑。
    def _connect(self) -> None:
        # 根据当前状态或输入选择对应的处理路径。
        if self._worker.isRunning():
            return
        # 必要条件或数据不满足时执行安全处理。
        if self._boundary_region is not None:
            self._clear_boundary(silent=True)
        # 根据当前状态或输入选择对应的处理路径。
        if self._boundary_points:
            self._clear_boundary_points(silent=True)
        self._last_position = None
        self._last_position_at = 0.0
        self._last_http_rpy_at = 0.0
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            MH4HttpClient(self.address_edit.text())  # 仅做本地格式校验
            self._worker.configure(
                self.address_edit.text().strip(),
                self.client_name_edit.text(),
                self.connection_type_combo.currentData(),
                grpc_port=self.grpc_port_spin.value(),
            )
        # 捕获异常并执行日志记录或安全降级。
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

    # 封装 start 对应的独立处理逻辑。
    def _start(self) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if not self._connected or self._moving:
            return
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            command = self._build_command()
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:
            QMessageBox.warning(self, "动作参数错误", str(exc))
            return
        # 根据当前状态或输入选择对应的处理路径。
        if command.get("mode") != "random_patrol":
            longest = max(segment["duration"] for segment in command["segments"])
            long_action_text = f"最长单方向持续时间为 {longest:.1f} 秒，是否继续？"
            # 根据当前状态或输入选择对应的处理路径。
            if longest > 120.0:
                answer = QMessageBox.question(
                    self,
                    "确认长时间动作",
                    long_action_text,
                )
                # 根据当前状态或输入选择对应的处理路径。
                if answer != QMessageBox.Yes:
                    return
        self._motion_totals.start(time.monotonic(), self._last_position)
        self._update_motion_totals_display()
        self._moving = True
        self._set_connected_ui(True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.trajectory_plot.mark_start()
        # 根据当前状态或输入选择对应的处理路径。
        if command.get("mode") == "random_patrol":  # 随机巡逻开始时显示内部安全线。
            self._patrol_safe_region = copy.deepcopy(command["safe_boundary"])  # 持久保存安全线，确保停止后和二次启动仍可恢复。
            self.trajectory_plot.set_patrol_safe_region(self._patrol_safe_region)  # 显示构建命令时已经验证的内部安全线。
        # 其余情况进入默认的处理路径。
        else:  # 非巡逻动作不使用随机点安全距离。
            self._patrol_safe_region = None  # 清除旧巡逻留下的安全线状态。
            self.trajectory_plot.set_patrol_safe_region(None)  # 从 3D 视图移除橙色安全线。
        self._worker.start_move(command)

    # 构建 command 对应的界面区域。
    def _build_command(self) -> dict[str, Any]:
        index = self.tabs.currentIndex()
        # 必要条件或数据不满足时执行安全处理。
        if not 0 <= index < len(self._action_configs):
            raise ValueError("请选择动作")
        config = self._action_configs[index]
        common = {
            "repetitions": self.repetition_spin.value(),
            "infinite": self.infinite_check.isChecked(),
            "settle_time": self.settle_spin.value(),
            "prepare_action_id": self.prepare_action_combo.currentData(),
            "boundary": copy.deepcopy(self._boundary_region),
        }
        # 根据当前状态或输入选择对应的处理路径。
        if config.get("kind") == "random_patrol":
            # 必要条件或数据不满足时执行安全处理。
            if self._boundary_region is None:
                raise ValueError("随机巡逻必须先设置矩形或多点运动范围")
            safety_margin = config["safety_margin"].value()  # 读取用户设置的边界安全距离。
            validated = self._worker._validated_boundary(self._boundary_region)  # 按后台规则校验外部围栏。
            safe_boundary = self._worker._inset_boundary(validated, safety_margin)  # 提前验证安全距离并生成内部安全线。
            return {
                **common,
                "mode": "random_patrol",
                "name": config["title"],
                "move_speed": config["move_speed"].value(),  # 单独传递直行摇杆幅值。
                "turn_speed": config["turn_speed"].value(),  # 单独传递随机转向和回中心转向幅值。
                "move_duration": config["move_duration"].value(),  # 只传递开环前进时间，不再传距离和偏航死区。
                "safety_margin": safety_margin,  # 传递仅用于随机点生成的边界安全距离。
                "safe_boundary": safe_boundary,  # 供主线程立即绘制经过验证的内部安全线。
            }
        amplitude = config["amplitude"].value()
        segments = []
        # 逐项处理当前集合中的数据。
        for label, direction, duration_spin in config["segments"]:
            segments.append({
                "name": label,
                **direction_axes(direction, amplitude),
                "duration": duration_spin.value(),
            })
        return {
            **common,
            "name": config["title"],
            "segments": segments,
            "rate_hz": 10.0,
        }

    # 设置 boundary_from_current_pose 相关状态或显示内容。
    def _set_boundary_from_current_pose(self) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if not self._connected or self._moving:
            return
        now = time.monotonic()
        # 根据当前状态或输入选择对应的处理路径。
        if (
            self._last_position is None
            or now - self._last_position_at > 1.0
            or now - self._last_http_rpy_at > 1.0
        ):
            QMessageBox.warning(
                self,
                "无法设定范围",
                "需要最近 1 秒内的 gRPC 位置和 HTTP IMU，请先确认两种数据都在更新。",
            )
            return
        center = list(self._last_position)
        yaw = float(self._last_http_rpy[2])
        self._boundary_region = self._worker._boundary_geometry(
            center,
            self.boundary_length_spin.value(),
            self.boundary_width_spin.value(),
            yaw,
        )
        self._patrol_safe_region = None  # 外部围栏改变后旧安全线立即失效。
        self.trajectory_plot.set_patrol_safe_region(None)  # 清除旧围栏对应的橙色安全线。
        self._show_boundary()
        self._append_log(
            f"[{self._time()}] [BOUNDARY] 已设定运动范围: "
            f"中心=({center[0]:.3f},{center[1]:.3f})m，"
            f"长={self.boundary_length_spin.value():.2f}m，"
            f"宽={self.boundary_width_spin.value():.2f}m，"
            f"方向={math.degrees(yaw):.1f}°"
        )
        self._set_connected_ui(self._connected)

    # 封装 resize_existing_boundary 对应的独立处理逻辑。
    def _resize_existing_boundary(self, _value: float) -> None:
        region = self._boundary_region
        # 根据当前状态或输入选择对应的处理路径。
        if (
            region is None
            or region.get("kind") == "polygon"
            or self._moving
        ):
            return
        self._boundary_region = self._worker._boundary_geometry(
            list(region["center"]),
            self.boundary_length_spin.value(),
            self.boundary_width_spin.value(),
            float(region["yaw"]),
        )
        self._patrol_safe_region = None  # 围栏尺寸改变后等待下次巡逻重新计算安全线。
        self.trajectory_plot.set_patrol_safe_region(None)  # 清除旧尺寸对应的橙色安全线。
        self._show_boundary()

    # 封装 show_boundary 对应的独立处理逻辑。
    def _show_boundary(self) -> None:
        region = self._boundary_region
        # 必要条件或数据不满足时执行安全处理。
        if region is None:
            return
        center = region["center"]
        self.trajectory_plot.set_boundary_region(region)
        # 根据当前状态或输入选择对应的处理路径。
        if region.get("kind") == "polygon":
            self.boundary_status_label.setText(
                f"多点限制已启用：{len(region['corners'])} 个凸包顶点；"
                f"中心 x={center[0]:.3f} y={center[1]:.3f} m；"
                f"跨度 x={region['length']:.2f} m y={region['width']:.2f} m"
            )
        # 其余情况进入默认的处理路径。
        else:
            self.boundary_status_label.setText(
                f"矩形限制已启用：中心 x={center[0]:.3f} "
                f"y={center[1]:.3f} m；长={region['length']:.2f} m，"
                f"宽={region['width']:.2f} m；"
                f"方向={math.degrees(region['yaw']):.1f}°"
            )
        self.boundary_status_label.setStyleSheet(
            "color:#80deea; background:#25272b; border:1px solid #397680; "
            "border-radius:4px; padding:6px; font:11px monospace;"
        )

    # 清除 boundary 相关状态和显示内容。
    def _clear_boundary(self, _checked: bool = False, *, silent: bool = False) -> None:
        self._boundary_region = None
        self._patrol_safe_region = None
        self.trajectory_plot.set_boundary_region(None)
        self.trajectory_plot.set_patrol_safe_region(None)
        self.trajectory_plot.set_current_command(None)
        self.boundary_status_label.setText("未设置：自动动作不限制范围")
        self.boundary_status_label.setStyleSheet(
            "color:#a8b3bc; background:#25272b; border:1px solid #455a64; "
            "border-radius:4px; padding:6px; font:11px monospace;"
        )
        # 必要条件或数据不满足时执行安全处理。
        if not silent:
            self._append_log(f"[{self._time()}] [BOUNDARY] 已取消运动范围限制")
        self._set_connected_ui(self._connected)

    # 封装 add_boundary_point 对应的独立处理逻辑。
    def _add_boundary_point(self) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if not self._connected or self._moving:
            return
        now = time.monotonic()
        # 必要条件或数据不满足时执行安全处理。
        if self._last_position is None or now - self._last_position_at > 1.0:
            QMessageBox.warning(
                self,
                "无法记录标点",
                "需要最近 1 秒内的 gRPC 位置，请先确认轨迹数据正在更新。",
            )
            return
        point = list(self._last_position[:3])
        # 逐项处理当前集合中的数据。
        for index, existing in enumerate(self._boundary_points, start=1):
            # 根据当前状态或输入选择对应的处理路径。
            if math.hypot(point[0] - existing[0], point[1] - existing[1]) < 0.05:
                QMessageBox.information(
                    self,
                    "标点过近",
                    f"当前位置与第 {index} 个标点相距不足 0.05 m，请移动后再记录。",
                )
                return
        # 根据当前状态或输入选择对应的处理路径。
        if len(self._boundary_points) >= 100:
            QMessageBox.warning(self, "标点数量已满", "最多记录 100 个围栏标点。")
            return
        self._boundary_points.append(point)
        self._show_boundary_points()
        self._append_log(
            f"[{self._time()}] [BOUNDARY] 已记录第 {len(self._boundary_points)} 个标点: "
            f"({point[0]:.3f},{point[1]:.3f},{point[2]:.3f})m"
        )
        self._set_connected_ui(self._connected)

    # 设置 boundary_from_points 相关状态或显示内容。
    def _set_boundary_from_points(self) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if not self._connected or self._moving:
            return
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            region = self._worker._polygon_boundary_geometry(
                copy.deepcopy(self._boundary_points)
            )
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:
            QMessageBox.warning(self, "无法生成多点范围", str(exc))
            return
        self._boundary_region = region
        self._patrol_safe_region = None  # 多点围栏改变后旧安全线不再有效。
        self.trajectory_plot.set_patrol_safe_region(None)  # 清除旧多点围栏对应的橙色安全线。
        self._show_boundary()
        self._append_log(
            f"[{self._time()}] [BOUNDARY] 已从 {len(self._boundary_points)} 个标点"
            f"生成多点范围: 凸包顶点={len(region['corners'])}，"
            f"中心=({region['center'][0]:.3f},{region['center'][1]:.3f})m"
        )
        self._set_connected_ui(self._connected)

    # 封装 show_boundary_points 对应的独立处理逻辑。
    def _show_boundary_points(self) -> None:
        count = len(self._boundary_points)
        self.trajectory_plot.set_boundary_points(self._boundary_points)
        # 根据当前状态或输入选择对应的处理路径。
        if count < 3:
            self.boundary_points_label.setText(
                f"已记录 {count} 个标点，还需要 {3 - count} 个"
            )
        # 其余情况进入默认的处理路径。
        else:
            self.boundary_points_label.setText(
                f"已记录 {count} 个标点，可以生成多点范围"
            )

    # 清除 boundary_points 相关状态和显示内容。
    def _clear_boundary_points(
        self, _checked: bool = False, *, silent: bool = False
    ) -> None:
        count = len(self._boundary_points)
        self._boundary_points.clear()
        self.trajectory_plot.set_boundary_points(None)
        self.boundary_points_label.setText("未记录标点（至少需要 3 个）")
        # 必要条件或数据不满足时执行安全处理。
        if count and not silent:
            self._append_log(
                f"[{self._time()}] [BOUNDARY] 已清除 {count} 个围栏标点"
            )
        self._set_connected_ui(self._connected)

    # 封装 stop 对应的独立处理逻辑。
    def _stop(self) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if not self._moving:
            return
        self._worker.stop_move()
        self._append_log(f"[{self._time()}] [CMD] ■ 请求停止，正在发送全零摇杆")
        self.stop_button.setEnabled(False)

    # 处理 connected 事件并同步界面状态。
    def _on_connected(self, ok: bool, detail: str) -> None:
        self._connected = ok
        # 根据当前状态或输入选择对应的处理路径。
        if ok:
            self.connection_label.setText(f"已连接 {detail}")
            self._set_connected_ui(True)
            control_base = MH4HttpClient(self.address_edit.text()).control_base
            host = urlsplit(control_base).hostname
            if host:
                self.video_panel.configure_host(host)
                self._worker.set_video_streaming(True)
        # 其余情况进入默认的处理路径。
        else:
            self.connection_label.setText(detail)
            self._finish_motion_totals()
            self._moving = False
            self._api_request_pending = False
            self._set_connected_ui(False)
            self.video_panel.stop()

    # HTTP 图传启停完成后再建立异步 WebRTC，避免相机未就绪时无效重试。
    def _on_video_stream_result(self, ok: bool, detail: str) -> None:
        self.video_panel.set_streaming_result(ok, detail)

    # 处理 worker_thread_finished 事件并同步界面状态。
    def _on_worker_thread_finished(self) -> None:
        """连接失败时，等 QThread 真正结束后再允许重新连接。"""
        # 必要条件或数据不满足时执行安全处理。
        if not self._connected:
            self.connect_button.setEnabled(True)

    # 处理 exchange 事件并同步界面状态。
    def _on_exchange(self, data: dict[str, Any]) -> None:
        imu = data.get("imu") if isinstance(data.get("imu"), dict) else {}
        rpy = imu.get("rpy", [])
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(rpy, (list, tuple)) and len(rpy) >= 3:
            # 尝试执行可能失败的操作并交由异常分支处理。
            try:
                self._last_http_rpy = [float(value) for value in rpy[:3]]
                # 必要条件或数据不满足时执行安全处理。
                if not all(math.isfinite(value) for value in self._last_http_rpy):
                    raise ValueError("HTTP IMU 含非有限值")
                self._last_http_rpy_at = time.monotonic()
                degrees = [math.degrees(float(value)) for value in rpy[:3]]
                self.rpy_label.setText(
                    f"r={degrees[0]:.1f}°  p={degrees[1]:.1f}°  y={degrees[2]:.1f}°"
                )
            # 捕获异常并执行日志记录或安全降级。
            except (TypeError, ValueError):
                self.rpy_label.setText(str(rpy))
        self.gyro_label.setText(self._format_vector(imu.get("gyroscope"), "rad/s"))
        self.accel_label.setText(self._format_vector(imu.get("accelerometer"), "m/s²"))
        # 必要条件或数据不满足时执行安全处理。
        if self._last_position is not None:
            self.trajectory_plot.update_imu_axes(
                *self._last_position, *self._last_http_rpy
            )
        bms = data.get("bms") if isinstance(data.get("bms"), dict) else {}
        battery = bms.get("battery_level", "—")
        health = bms.get("battery_health", "—")
        self.battery_label.setText(f"{battery}%（健康度 {health}%）")
        self.imu_temperature_label.setText(
            self._format_temperature(imu.get("temperature"))
        )
        self.bms_pcb_temperature_label.setText(
            self._format_temperature(bms.get("pcb_board_temp"))
        )
        self.bms_afe_temperature_label.setText(
            self._format_temperature(bms.get("afe_chip_temp"))
        )
        joints = data.get("joint") if isinstance(data.get("joint"), dict) else {}
        # 逐项处理当前集合中的数据。
        for leg_key, field_labels in self.joint_temperature_labels.items():
            leg = joints.get(leg_key) if isinstance(joints.get(leg_key), dict) else {}
            # 逐项处理当前集合中的数据。
            for field, label in field_labels.items():
                label.setText(self._format_temperature(leg.get(field)))
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

    # 处理 odom 事件并同步界面状态。
    def _on_odom(self, data: dict[str, Any]) -> None:
        pos = data.get("pos", [])
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            return
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            self._last_position = [float(value) for value in pos[:3]]
            # 必要条件或数据不满足时执行安全处理。
            if not all(math.isfinite(value) for value in self._last_position):
                return
            self._last_position_at = time.monotonic()
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError):
            return
        x, y, z = self._last_position
        self.position_label.setText(f"x={x:.3f} y={y:.3f} z={z:.3f} m")
        # 根据当前状态或输入选择对应的处理路径。
        if self._moving:
            self._motion_totals.observe_position(self._last_position)
            self._update_motion_totals_display()
        self.trajectory_plot.add_point(x, y, z)
        self.trajectory_plot.update_imu_axes(x, y, z, *self._last_http_rpy)

    # 处理 trajectory_status 事件并同步界面状态。
    def _on_trajectory_status(self, ok: bool, detail: str) -> None:
        self.trajectory_source_label.setText(detail)
        self.trajectory_source_label.setStyleSheet(
            "color:#69f0ae; font:13px monospace;" if ok
            else "color:#ffb74d; font:13px monospace;"
        )

    # 处理 recovery_command 事件并同步界面状态。
    def _on_recovery_command(self, command: object) -> None:
        self.trajectory_plot.set_current_command(command)

    # 清除 trajectory 相关状态和显示内容。
    def _clear_trajectory(self) -> None:
        self.trajectory_plot.clear()
        # 必要条件或数据不满足时执行安全处理。
        if self._boundary_region is not None:
            self._show_boundary()
        # 必要条件或数据不满足时执行安全处理。
        if self._patrol_safe_region is not None:  # 清除轨迹后恢复当前巡逻安全线。
            self.trajectory_plot.set_patrol_safe_region(self._patrol_safe_region)  # 重新绘制橙色内部安全线。
        self._show_boundary_points()
        self._append_log(f"[{self._time()}] [INFO] 已清除轨迹")

    # 处理 finished 事件并同步界面状态。
    def _on_finished(self, message: str) -> None:
        self._finish_motion_totals()
        self._moving = False
        self.trajectory_plot.set_current_command(None)
        # 必要条件或数据不满足时执行安全处理。
        if self._patrol_safe_region is not None:  # 巡逻停止后仍保留安全线供检查和二次启动。
            self.trajectory_plot.set_patrol_safe_region(self._patrol_safe_region)  # 防止动作结束清理误删安全线。
        self._set_connected_ui(self._connected)

    # 处理 emergency_result 事件并同步界面状态。
    def _on_emergency_result(self, ok: bool, message: str) -> None:
        # 根据当前状态或输入选择对应的处理路径。
        if ok and "已触发" in message:
            self._finish_motion_totals()
            self._moving = False
            self.trajectory_plot.set_current_command(None)
            # 必要条件或数据不满足时执行安全处理。
            if self._patrol_safe_region is not None:  # 急停只清除运动指令，不删除安全线配置。
                self.trajectory_plot.set_patrol_safe_region(self._patrol_safe_region)  # 保留橙色内部安全线。
            self._set_connected_ui(self._connected)

    # 设置 connected_ui 相关状态或显示内容。
    def _set_connected_ui(self, connected: bool) -> None:
        self.start_button.setEnabled(connected and not self._moving)
        self.stop_button.setEnabled(connected and self._moving)
        self.boundary_set_button.setEnabled(connected and not self._moving)
        self.boundary_clear_button.setEnabled(
            not self._moving and self._boundary_region is not None
        )
        self.boundary_point_add_button.setEnabled(connected and not self._moving)
        self.boundary_points_apply_button.setEnabled(
            connected and not self._moving and len(self._boundary_points) >= 3
        )
        self.boundary_points_clear_button.setEnabled(
            not self._moving and bool(self._boundary_points)
        )
        self.boundary_length_spin.setEnabled(not self._moving)
        self.boundary_width_spin.setEnabled(not self._moving)
        self.emergency_button.setEnabled(connected)
        self.release_button.setEnabled(connected)
        self.api_send_button.setEnabled(
            connected and not self._moving and not self._api_request_pending
        )
        # 必要条件或数据不满足时执行安全处理。
        if not connected:
            self.connect_button.setEnabled(not self._worker.isRunning())
            self.address_edit.setEnabled(True)
            self.connection_type_combo.setEnabled(True)
            self.client_name_edit.setEnabled(True)
            self.grpc_port_spin.setEnabled(True)

    # 封装 append_log 对应的独立处理逻辑。
    def _append_log(self, message: str) -> None:
        self.log_edit.append(message)
        self.log_edit.moveCursor(QTextCursor.End)

    # 封装 update_motion_totals_display 对应的独立处理逻辑。
    def _update_motion_totals_display(self) -> None:
        elapsed = self._motion_totals.elapsed(time.monotonic())
        self.total_distance_label.setText(f"{self._motion_totals.distance_m:.3f} m")
        self.total_time_label.setText(self._format_elapsed(elapsed))

    # 封装 finish_motion_totals 对应的独立处理逻辑。
    def _finish_motion_totals(self) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if not self._motion_totals.running:
            return
        self._motion_totals.stop(time.monotonic())
        self._update_motion_totals_display()
        self._append_log(
            f"[{self._time()}] [STATS] 总里程="
            f"{self._motion_totals.distance_m:.3f}m，"
            f"总时间={self._format_elapsed(self._motion_totals.elapsed_s)}"
        )

    # 封装 closeEvent 对应的独立处理逻辑。
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # 先通知 WebRTC 后台退出，让其与 HTTP 安全停止并行收尾。
        self.video_panel.stop()
        self._worker.shutdown()
        # 必要条件或数据不满足时执行安全处理。
        if self._worker.isRunning() and not self._worker.wait(8000):
            QMessageBox.warning(
                self,
                "正在安全停止",
                "后台 HTTP 请求尚未退出，请稍后再关闭窗口。",
            )
            event.ignore()
            return
        self.video_panel.shutdown()
        event.accept()

    # ── 样式与控件辅助 ───────────────────────────

    # 封装 time 对应的独立处理逻辑。
    @staticmethod
    def _time() -> str:
        return time.strftime("%H:%M:%S")

    # 把 elapsed 格式化为界面可读文本。
    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        tenths = max(0, int(float(seconds) * 10.0))
        hours, remainder = divmod(tenths, 36000)
        minutes, remainder = divmod(remainder, 600)
        whole_seconds, tenth = divmod(remainder, 10)
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{tenth}"

    # 把 vector 格式化为界面可读文本。
    @staticmethod
    def _format_vector(values: Any, unit: str) -> str:
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(values, (list, tuple)) or len(values) < 3:
            return "—"
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            return (
                f"x={float(values[0]):.3f} y={float(values[1]):.3f} "
                f"z={float(values[2]):.3f} {unit}"
            )
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError):
            return str(values)

    # 把 temperature 格式化为界面可读文本。
    @staticmethod
    def _format_temperature(value: Any) -> str:
        # 必要条件或数据不满足时执行安全处理。
        if value is None:
            return "—"
        values = value if isinstance(value, (list, tuple)) else (value,)
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            numbers = [float(item) for item in values]
            # 必要条件或数据不满足时执行安全处理。
            if not numbers or not all(math.isfinite(item) for item in numbers):
                return "—"
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError):
            return str(value)
        formatted = " / ".join(f"{item:g}" for item in numbers)
        return f"{formatted} °C"

    # 封装 group_style 对应的独立处理逻辑。
    @staticmethod
    def _group_style(color: str) -> str:
        return (
            f"QGroupBox {{ font:bold 14px; color:{color}; border:1px solid #42464c; "
            "border-radius:6px; margin-top:12px; padding-top:16px; background:#2b2d31; } "
            "QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; } "
            "QGroupBox QLabel { color:#e0e0e0; }"
        )

    # 封装 input_style 对应的独立处理逻辑。
    @staticmethod
    def _input_style() -> str:
        return (
            "QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit { background:#3a3d42; "
            "color:#f5f5f5; padding:5px; border:1px solid #55585e; border-radius:4px; }"
            "QComboBox QAbstractItemView { background:#2b2d31; color:#f5f5f5; "
            "selection-background-color:#00897b; }"
        )

    # 封装 button_style 对应的独立处理逻辑。
    @staticmethod
    def _button_style(base: str, hover: str, compact: bool = False) -> str:
        padding = "5px 14px" if compact else "9px 16px"
        return (
            f"QPushButton {{ background:{base}; color:#fff; font:bold 13px; "
            f"padding:{padding}; border-radius:5px; }} "
            f"QPushButton:hover {{ background:{hover}; }} "
            "QPushButton:disabled { background:#4a4d52; color:#9a9da2; }"
        )

    # 封装 double_spin 对应的独立处理逻辑。
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

    # 封装 stick_spin 对应的独立处理逻辑。
    @classmethod
    def _stick_spin(cls) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(500, 32767)
        spin.setValue(8000)
        spin.setSingleStep(500)
        spin.setStyleSheet(cls._input_style())
        spin.setToolTip("建议首次使用 2000～5000 的低幅值确认方向")
        return spin

    # 封装 intro 对应的独立处理逻辑。
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

    # 封装 status_label 对应的独立处理逻辑。
    @staticmethod
    def _status_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color:#e0e0e0; font:13px monospace;")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label


# 创建应用程序并启动图形界面事件循环。
def main() -> None:
    app = QApplication(sys.argv)
    app.setOrganizationName("Dobot")
    app.setApplicationName("MH4 HTTP Auto Move")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


# 仅在直接运行本模块时启动应用程序。
if __name__ == "__main__":
    main()
