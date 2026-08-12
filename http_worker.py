# 说明后台线程负责的通信、巡逻和安全恢复范围。
"""MH4 HTTP 自动移动后台线程。"""

# 导入本模块所需的库、类型和外部组件。
from __future__ import annotations

# 导入本模块所需的库、类型和外部组件。
import math
import json
import queue
import random
import threading
import time
from typing import Any
from urllib.parse import urlsplit

# 导入本模块所需的库、类型和外部组件。
from PySide6.QtCore import QThread, Signal

# 尝试执行可能失败的操作并交由异常分支处理。
try:
    from .http_client import MH4HttpClient
# 捕获异常并执行日志记录或安全降级。
except ImportError:  # 支持 python3 http_auto_move/main.py
    from http_client import MH4HttpClient


# 封装后台通信、巡逻执行和越界恢复流程。
class HttpAutoMoveWorker(QThread):
    """维持 exchange 心跳，并按固定频率重复发送摇杆时序。"""

    # 定义本模块后续逻辑使用的常量或默认配置。
    _POSE_MAX_AGE = 1.0
    _RETURN_POSE_RECOVERY_TIMEOUT = 3.0
    _RETURN_POSE_POLL_INTERVAL = 0.05
    _RETURN_MAX_AMPLITUDE = 32767
    _RETURN_START_AMPLITUDE = 8000
    _RETURN_MIN_AMPLITUDE = 500
    _RETURN_SLOW_RADIUS = 0.75
    _RETURN_TURN_STALL_TIMEOUT = 3.0
    _RETURN_TURN_PROGRESS = math.radians(3.0)

    # 声明后台线程向界面发送的事件信号。
    connected = Signal(bool, str)
    exchange_data = Signal(dict)
    odom_data = Signal(dict)       # gRPC 仅提供位置/速度；姿态始终来自 HTTP IMU
    trajectory_status = Signal(bool, str)
    recovery_command = Signal(object)
    log_msg = Signal(str)
    finished_ok = Signal(str)
    emergency_result = Signal(bool, str)
    manual_api_result = Signal(bool, str, object)

    # 初始化对象状态以及运行所需的资源。
    def __init__(self, parent=None):
        super().__init__(parent)
        self._address = "10.30.12.196:22000"
        self._client_name = "HTTP Auto Move"
        self._connection_type = "Auto"
        self._effective_connection_type = "AP"
        self._current_client = 1
        self._timeout = 1.5
        self._grpc_port = 50051
        self._client: MH4HttpClient | None = None
        self._commands: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._alive = threading.Event()
        self._stop_motion = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._odom_thread: threading.Thread | None = None
        self._pose_lock = threading.Lock()
        self._latest_position: list[float] | None = None
        self._latest_position_at = 0.0
        self._latest_http_rpy: list[float] | None = None
        self._latest_http_rpy_at = 0.0
        self._random = random.Random()

    # 写入后台线程的连接参数并清除旧姿态。
    def configure(
        self,
        address: str,
        client_name: str,
        connection_type: str,
        grpc_port: int = 50051,
        timeout: float = 1.5,
    ) -> None:
        # 根据当前状态或输入选择对应的处理路径。
        if self.isRunning():
            raise RuntimeError("运行中不能修改连接参数")
        self._address = address
        self._client_name = client_name.strip() or "HTTP Auto Move"
        self._connection_type = connection_type
        self._grpc_port = max(1, min(65535, int(grpc_port)))
        self._timeout = max(0.1, float(timeout))
        # 在受控上下文中安全访问共享资源。
        with self._pose_lock:
            self._latest_position = None
            self._latest_position_at = 0.0
            self._latest_http_rpy = None
            self._latest_http_rpy_at = 0.0

    # 把新的移动任务加入后台执行队列。
    def start_move(self, command: dict[str, Any]) -> None:
        self._commands.put(dict(command))

    # 把手动 API 请求加入后台执行队列。
    def call_api(
        self,
        method: str,
        path: str,
        payload: Any | None,
        port: int,
    ) -> None:
        self._commands.put({
            "_kind": "manual_api",
            "method": method,
            "path": path,
            "payload": payload,
            "port": int(port),
        })

    # 通知当前移动任务尽快停止。
    def stop_move(self) -> None:
        self._stop_motion.set()

    # 停止后台循环并唤醒等待中的任务队列。
    def shutdown(self) -> None:
        self._alive.clear()
        self._stop_motion.set()
        self._commands.put(None)

    # 在独立线程中发送软急停请求。
    def set_emergency_stop(self, enabled: bool) -> None:
        """独立请求急停，避免长动作阻塞 UI 中的急停操作。"""
        # 根据当前状态或输入选择对应的处理路径。
        if enabled:
            self._stop_motion.set()

        # 封装 send 对应的独立处理逻辑。
        def send() -> None:
            client = self._client
            # 必要条件或数据不满足时执行安全处理。
            if client is None:
                self.emergency_result.emit(False, "尚未连接机器人")
                return
            # 尝试执行可能失败的操作并交由异常分支处理。
            try:
                # 根据当前状态或输入选择对应的处理路径。
                if enabled:
                    self._safe_stop(client, attempts=1)
                client.emergency_stop(enabled)
                text = "软急停已触发" if enabled else "软急停已解除"
                self._log("WARN" if enabled else "INFO", text)
                self.emergency_result.emit(True, text)
            # 捕获异常并执行日志记录或安全降级。
            except Exception as exc:
                text = f"软急停请求失败: {exc}"
                self._log("ERROR", text)
                self.emergency_result.emit(False, text)

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        threading.Thread(target=send, name="mh4-emergency", daemon=True).start()

    # 建立连接、启动采集线程并消费任务队列。
    def run(self) -> None:
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            client = MH4HttpClient(self._address, timeout=self._timeout)
            self._client = client
            effective_type = self._resolve_connection_type(client)
            self._effective_connection_type = effective_type
            self._log("HTTP", f"POST {client.control_base}/connection/state")
            client.connect(
                client_name=self._client_name,
                connection_type=effective_type,
                current_client=self._current_client,
            )
            initial = client.exchange()
            self._remember_exchange(initial)
            self.exchange_data.emit(initial)
            self._alive.set()
            self.connected.emit(True, f"{client.control_base}（{effective_type}）")
            self._log(
                "INFO",
                f"已连接 {client.control_base}，方式={effective_type}，exchange 心跳已启动",
            )
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:
            self._log("ERROR", f"连接失败: {exc}")
            self.connected.emit(False, str(exc))
            self._client = None
            return

        # 初始化或更新本段运行所需的对象状态。
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="mh4-exchange", daemon=True
        )
        self._odom_thread = threading.Thread(
            target=self._odom_loop, name="mh4-odom", daemon=True
        )
        self._heartbeat_thread.start()
        self._odom_thread.start()

        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            # 在运行条件成立期间持续执行本段逻辑。
            while self._alive.is_set():
                # 尝试执行可能失败的操作并交由异常分支处理。
                try:
                    command = self._commands.get(timeout=0.2)
                # 捕获异常并执行日志记录或安全降级。
                except queue.Empty:
                    continue
                # 必要条件或数据不满足时执行安全处理。
                if command is None:
                    break
                # 根据当前状态或输入选择对应的处理路径。
                if command.get("_kind") == "manual_api":
                    self._execute_manual_api(command)
                    continue
                self._stop_motion.clear()
                self._execute(command)
        # 无论执行结果如何都完成必要的收尾处理。
        finally:
            self._alive.clear()
            self._stop_motion.set()
            # 必要条件或数据不满足时执行安全处理。
            if self._client is not None:
                self._safe_stop(self._client)
            # 必要条件或数据不满足时执行安全处理。
            if self._heartbeat_thread is not None:
                self._heartbeat_thread.join(timeout=self._timeout + 0.5)
            # 必要条件或数据不满足时执行安全处理。
            if self._odom_thread is not None:
                self._odom_thread.join(timeout=2.0)
            self._client = None
            self.connected.emit(False, "连接已关闭")

    # 解析自动连接模式对应的实际连接类型。
    def _resolve_connection_type(self, client: MH4HttpClient) -> str:
        """优先采用控制器报告的 AP/Station，避免网线连接被登记为 AP。"""
        requested = self._connection_type
        detected = None
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            detected = client.connection_type()
            self._log("INFO", f"控制器报告连接方式: {detected}")
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:
            self._log("WARN", f"自动读取连接方式失败: {exc}")

        # 根据当前状态或输入选择对应的处理路径。
        if detected in ("AP", "Station"):
            # 必要条件或数据不满足时执行安全处理。
            if requested not in ("Auto", detected, "4G"):
                self._log(
                    "WARN",
                    f"界面选择 {requested}，控制器实际为 {detected}；自动改用 {detected}",
                )
            # 根据当前状态或输入选择对应的处理路径。
            if requested != "4G":
                return detected
        # 根据当前状态或输入选择对应的处理路径。
        if requested in ("AP", "Station", "4G"):
            return requested
        # 无法探测时，根据文档中的固定网口地址回退。
        return "Station" if "192.168.5.2" in self._address else "AP"

    # 循环执行 exchange 请求以维护连接心跳。
    def _heartbeat_loop(self) -> None:
        failures = 0
        next_tick = time.monotonic()
        # 在运行条件成立期间持续执行本段逻辑。
        while self._alive.is_set():
            client = self._client
            # 必要条件或数据不满足时执行安全处理。
            if client is None:
                break
            # 尝试执行可能失败的操作并交由异常分支处理。
            try:
                state = client.exchange()
                self._remember_exchange(state)
                self.exchange_data.emit(state)
                # 根据当前状态或输入选择对应的处理路径。
                if failures:
                    self._log("INFO", "exchange 心跳已恢复")
                failures = 0
            # 捕获异常并执行日志记录或安全降级。
            except Exception as exc:
                failures += 1
                # 根据当前状态或输入选择对应的处理路径。
                if failures in (1, 3) or failures % 10 == 0:
                    self._log("ERROR", f"exchange 心跳失败({failures}): {exc}")
            next_tick += 0.2  # 5 Hz，远小于文档中的 3 秒占用超时
            # 请求偶尔变慢时不要连续补发积欠的 exchange，避免与摇杆请求争抢
            # 控制器的 HTTP 处理能力，形成“越慢越密集”的反馈循环。
            if next_tick < time.monotonic():
                next_tick = time.monotonic() + 0.2
            wait = max(0.0, next_tick - time.monotonic())
            time.sleep(wait)

    # 持续读取里程计位置并发送给界面。
    def _odom_loop(self) -> None:
        """以 10 Hz 读取 gRPC 世界坐标；不使用其中的 IMU 姿态。"""
        host = urlsplit(self._client.control_base).hostname if self._client else None
        # 必要条件或数据不满足时执行安全处理。
        if not host:
            self.trajectory_status.emit(False, "无法从 HTTP 地址解析 gRPC 主机")
            return
        address = f"{host}:{self._grpc_port}"
        robot = None
        failures = 0
        available = False
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            from dobot_quad import RobotClient
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:
            self.trajectory_status.emit(False, f"dobot_quad 不可用: {exc}")
            self._log("WARN", f"轨迹采样未启动: {exc}")
            return

        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            # 在运行条件成立期间持续执行本段逻辑。
            while self._alive.is_set():
                # 尝试执行可能失败的操作并交由异常分支处理。
                try:
                    # 必要条件或数据不满足时执行安全处理。
                    if robot is None:
                        robot = RobotClient(address)
                    state = robot.get_state()
                    # 必要条件或数据不满足时执行安全处理。
                    if not state or not getattr(state, "success", True):
                        raise RuntimeError("get_state 返回失败")
                    rs = state.robot_state
                    pos = [float(value) for value in rs.pos_body]
                    # 根据当前状态或输入选择对应的处理路径。
                    if len(pos) < 2:
                        raise RuntimeError("pos_body 缺少 x/y")
                    # 在运行条件成立期间持续执行本段逻辑。
                    while len(pos) < 3:
                        pos.append(0.0)
                    # 必要条件或数据不满足时执行安全处理。
                    if not all(math.isfinite(value) for value in pos[:3]):
                        raise RuntimeError("pos_body 含非有限值")
                    vel = [float(value) for value in rs.vel_body]
                    # 在运行条件成立期间持续执行本段逻辑。
                    while len(vel) < 3:
                        vel.append(0.0)
                    # 在受控上下文中安全访问共享资源。
                    with self._pose_lock:
                        self._latest_position = pos[:3]
                        self._latest_position_at = time.monotonic()
                    self.odom_data.emit({"pos": pos[:3], "vel": vel[:3]})
                    failures = 0
                    # 必要条件或数据不满足时执行安全处理。
                    if not available:
                        available = True
                        self.trajectory_status.emit(True, f"gRPC {address} @ 10 Hz")
                        self._log("INFO", f"实际轨迹采样已启动: gRPC {address} @ 10 Hz")
                # 捕获异常并执行日志记录或安全降级。
                except Exception as exc:
                    failures += 1
                    # 根据当前状态或输入选择对应的处理路径。
                    if failures in (1, 10) or failures % 50 == 0:
                        self._log("WARN", f"gRPC 轨迹采样失败({failures}): {exc}")
                    # 根据当前状态或输入选择对应的处理路径。
                    if available and failures >= 10:
                        available = False
                        self.trajectory_status.emit(False, f"gRPC 轨迹中断: {exc}")
                    # 根据当前状态或输入选择对应的处理路径。
                    if failures >= 10:
                        robot = None
                time.sleep(0.1)
        # 无论执行结果如何都完成必要的收尾处理。
        finally:
            close = getattr(robot, "close", None)
            # 根据当前状态或输入选择对应的处理路径。
            if callable(close):
                # 尝试执行可能失败的操作并交由异常分支处理。
                try:
                    close()
                # 捕获异常并执行日志记录或安全降级。
                except Exception:
                    pass
            self.trajectory_status.emit(False, "gRPC 轨迹采样已停止")

    # 解析并执行一个完整的移动动作配置。
    def _execute(self, command: dict[str, Any]) -> None:
        # 根据当前状态或输入选择对应的处理路径。
        if command.get("mode") == "random_patrol":
            self._execute_random_patrol(command)
            return
        client = self._client
        # 必要条件或数据不满足时执行安全处理。
        if client is None:
            self.finished_ok.emit("执行失败：HTTP 客户端未连接")
            return

        # 准备本逻辑段使用的局部数据和中间状态。
        segments = []
        # 逐项处理当前集合中的数据。
        for raw in command.get("segments", []):
            segments.append({
                "name": str(raw.get("name", "动作")),
                "axes": {
                    "move_x": int(raw.get("move_x", 0)),
                    "move_y": int(raw.get("move_y", 0)),
                    "turn_x": int(raw.get("turn_x", 0)),
                    "turn_y": int(raw.get("turn_y", 0)),
                },
                "duration": max(0.05, float(raw.get("duration", 1.0))),
            })
        # 必要条件或数据不满足时执行安全处理。
        if not segments:
            self.finished_ok.emit("执行失败：动作组为空")
            return
        repetitions = max(1, int(command.get("repetitions", 1)))
        infinite = bool(command.get("infinite", False))
        settle_time = max(0.0, float(command.get("settle_time", 0.3)))
        rate_hz = max(2.0, min(50.0, float(command.get("rate_hz", 10.0))))
        name = str(command.get("name", "摇杆时序"))
        boundary = None

        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            boundary = self._validated_boundary(command.get("boundary"))
            prepare_action_id = command.get("prepare_action_id")
            # 必要条件或数据不满足时执行安全处理。
            if prepare_action_id is not None:
                self._log(
                    "HTTP",
                    f"POST {client.control_base}/settings/movement/action "
                    f"id={int(prepare_action_id)}",
                )
                client.movement_action(int(prepare_action_id))
                # 根据当前状态或输入选择对应的处理路径。
                if self._stop_motion.wait(1.0):
                    self.finished_ok.emit("动作已停止")
                    return
            self._log(
                "INFO",
                f"启动 {name}: 每组 {len(segments)} 个方向，频率 {rate_hz:.1f}Hz，"
                f"组数 {'无限' if infinite else repetitions}",
            )
            # 必要条件或数据不满足时执行安全处理。
            if boundary is not None:
                center = boundary["center"]
                # 根据当前状态或输入选择对应的处理路径。
                if boundary.get("kind") == "polygon":
                    self._log(
                        "BOUNDARY",
                        f"多点范围限制已启用: {len(boundary['corners'])} 个边界点，"
                        f"中心=({center[0]:.3f},{center[1]:.3f})m",
                    )
                # 其余情况进入默认的处理路径。
                else:
                    self._log(
                        "BOUNDARY",
                        f"矩形范围限制已启用: "
                        f"中心=({center[0]:.3f},{center[1]:.3f})m，"
                        f"长={boundary['length']:.2f}m，"
                        f"宽={boundary['width']:.2f}m",
                    )
            cycle = 0
            failure = ""
            # 在运行条件成立期间持续执行本段逻辑。
            while self._alive.is_set() and not self._stop_motion.is_set():
                cycle += 1
                # 必要条件或数据不满足时执行安全处理。
                if not infinite and cycle > repetitions:
                    break
                total = 0 if infinite else repetitions
                group_start = self._pose_snapshot()
                # 逐项处理当前集合中的数据。
                for index, segment in enumerate(segments):
                    stage = f"{name} · {segment['name']} ({index + 1}/{len(segments)})"
                    segment_start = self._pose_snapshot()
                    axes = segment["axes"]
                    self._log(
                        "CMD",
                        f"▶ 第{cycle}组 {self._direction_symbol(axes)} {segment['name']} | "
                        f"btn_move=({axes['move_x']},{axes['move_y']}) "
                        f"btn_turn=({axes['turn_x']},{axes['turn_y']}) | "
                        f"持续={segment['duration']:.1f}s @ {rate_hz:.1f}Hz",
                    )
                    drive_result, boundary_error = self._drive_once(
                        client,
                        stage,
                        segment["axes"],
                        segment["duration"],
                        rate_hz,
                        cycle,
                        total,
                        boundary=boundary,
                    )
                    self._log(
                        "CMD", f"■ 第{cycle}组 {segment['name']}结束，摇杆已归零"
                    )
                    # 根据当前状态或输入选择对应的处理路径。
                    if drive_result == "outside":
                        segment_end = self._pose_snapshot()
                    # 其余情况进入默认的处理路径。
                    else:
                        segment_end = self._pose_after(
                            time.monotonic(), timeout=0.35
                        )
                    self._log_segment_error(
                        cycle, segment["name"], segment["axes"],
                        segment_start, segment_end,
                    )
                    # 必要条件或数据不满足时执行安全处理。
                    if self._stop_motion.is_set() or not self._alive.is_set():
                        break
                    # 必要条件或数据不满足时执行安全处理。
                    if drive_result == "outside" and boundary is not None:
                        self._log(
                            "WARN",
                            f"第{cycle}组 {segment['name']}检测到越界，"
                            f"距中心={boundary_error:.4f}m；已归零，插入回中心指令",
                        )
                        amplitude = max(
                            500,
                            min(32767, max(abs(value) for value in axes.values())),
                        )
                        returned, center_error = self._return_to_boundary_center(
                            client, boundary, amplitude
                        )
                        error_text = (
                            f"{center_error:.4f}m"
                            if math.isfinite(center_error) else "不可用"
                        )
                        # 根据当前状态或输入选择对应的处理路径。
                        if returned != "reached":
                            self._log(
                                "MEASURE",
                                f"第{cycle}组 越界回中心中止: 状态={returned}，"
                                f"中心误差={error_text}",
                            )
                            # 根据当前状态或输入选择对应的处理路径。
                            if returned != "stopped":
                                failure = (
                                    f"越界回中心失败（{returned}，"
                                    f"中心误差={error_text}）"
                                )
                            break
                        self._log(
                            "MEASURE",
                            f"第{cycle}组 越界回中心完成: 中心误差={error_text}",
                        )
                        self._log("BOUNDARY", "已回到中心，继续后续来回动作")
                    # 前一条件不成立时继续检查下一种情况。
                    elif drive_result != "completed":
                        # 根据当前状态或输入选择对应的处理路径。
                        if drive_result != "stopped":
                            failure = f"范围限制停止动作（{drive_result}）"
                            self._log("ERROR", failure)
                        break
                    has_more = (
                        index + 1 < len(segments)
                        or infinite
                        or cycle < repetitions
                    )
                    # 根据当前状态或输入选择对应的处理路径。
                    if settle_time and has_more:
                        self._log("CMD", f"… 动作间隔 {settle_time:.1f}s")
                        # 根据当前状态或输入选择对应的处理路径。
                        if self._stop_motion.wait(settle_time):
                            break

                # 根据当前状态或输入选择对应的处理路径。
                if (
                    not failure
                    and not self._stop_motion.is_set()
                    and self._alive.is_set()
                ):
                    group_end = self._pose_snapshot()
                    self._log_group_error(cycle, name, group_start, group_end)
                # 根据当前状态或输入选择对应的处理路径。
                if failure:
                    break

            # 准备本逻辑段使用的局部数据和中间状态。
            stopped = self._stop_motion.is_set()
            # 根据当前状态或输入选择对应的处理路径。
            if failure:
                message = f"动作执行失败：{failure}"
            # 其余情况进入默认的处理路径。
            else:
                message = "动作已停止" if stopped else "动作执行完成"
            self.finished_ok.emit(message)
            self._log("ERROR" if failure else "INFO", message)
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:
            self._log("ERROR", f"动作执行失败: {exc}")
            self.finished_ok.emit(f"动作执行失败: {exc}")
        # 无论执行结果如何都完成必要的收尾处理。
        finally:
            self._safe_stop(client)
            self.recovery_command.emit(None)

    # 持续生成安全目标并执行随机巡逻。
    def _execute_random_patrol(self, command: dict[str, Any]) -> None:
        """按时间执行随机转向和前进，仅在越界后使用位置姿态回中心。"""  # 说明简化后的巡逻原则。
        client = self._client  # 读取当前已经建立连接的 HTTP 客户端。
        # 必要条件或数据不满足时执行安全处理。
        if client is None:  # 没有客户端时不能向机器狗发送运动命令。
            self.finished_ok.emit("执行失败：HTTP 客户端未连接")  # 把失败原因通知界面。
            return  # 立即结束本次巡逻任务。

        # 准备本逻辑段使用的局部数据和中间状态。
        failure = ""  # 保存需要显示给用户的非异常失败原因。
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:  # 确保无论正常、停止或异常退出都会发送归零命令。
            boundary = self._validated_boundary(command.get("boundary"))  # 校验界面传入的围栏。
            # 必要条件或数据不满足时执行安全处理。
            if boundary is None:  # 随机巡逻必须依靠围栏限制活动范围。
                raise ValueError("随机巡逻必须先设置并启用运动范围")  # 拒绝无围栏巡逻。
            legacy_speed = int(command.get("speed", 5000))  # 读取旧版本共用速度供兼容历史命令。
            move_speed = max(500, min(32767, int(command.get("move_speed", legacy_speed))))  # 限制独立前进摇杆幅值。
            turn_speed = max(500, min(32767, int(command.get("turn_speed", legacy_speed))))  # 限制独立旋转摇杆幅值。
            move_duration = max(0.1, min(60.0, float(command.get("move_duration", 2.0))))  # 限制每段前进时间。
            safety_margin = max(0.05, min(10.0, float(command.get("safety_margin", 0.30))))  # 限制可调边界安全距离。
            repetitions = max(1, int(command.get("repetitions", 1)))  # 至少执行一个巡逻路段。
            infinite = bool(command.get("infinite", False))  # 读取是否无限循环的选项。
            settle_time = max(0.0, float(command.get("settle_time", 0.3)))  # 读取路段间停留时间。
            prepare_action_id = command.get("prepare_action_id")  # 读取可选的运动状态编号。
            patrol_boundary = self._inset_boundary(boundary, safety_margin)  # 生成向内缩进后的实际巡逻安全线。
            # 必要条件或数据不满足时执行安全处理。
            if prepare_action_id is not None:  # 用户选择运动状态时先切换状态。
                self._log("HTTP", f"POST {client.control_base}/settings/movement/action id={int(prepare_action_id)}")  # 记录状态切换请求。
                client.movement_action(int(prepare_action_id))  # 请求控制器切换运动状态。
                # 根据当前状态或输入选择对应的处理路径。
                if self._stop_motion.wait(1.0):  # 给状态切换留出一秒并响应停止按钮。
                    self.finished_ok.emit("动作已停止")  # 通知界面任务已被用户停止。
                    return  # 不再发送后续巡逻命令。

            # 准备本逻辑段使用的局部数据和中间状态。
            total_text = "∞" if infinite else str(repetitions)  # 生成日志中的总路段文本。
            self._log("INFO", f"启动简化随机巡逻: 路段数={total_text}，前进速度={move_speed}，旋转速度={turn_speed}，每段前进={move_duration:.1f}s，随机点安全距离={safety_margin:.2f}m；仅越过蓝色外部围栏时回中心")  # 说明安全距离只约束随机点，出界仍以外部围栏为准。
            segment = 0  # 从尚未执行任何路段开始计数。
            # 在运行条件成立期间持续执行本段逻辑。
            while self._alive.is_set() and not self._stop_motion.is_set():  # 在线且未停止时持续巡逻。
                # 必要条件或数据不满足时执行安全处理。
                if not infinite and segment >= repetitions:  # 有限模式完成指定路段数后退出。
                    break  # 跳出巡逻循环并报告完成。
                segment += 1  # 开始一个新的巡逻路段。
                pose = self._pose_snapshot()  # 获取当前位置和航向，用于生成及显示本段随机目标点。
                current_position = pose.get("pos") if self._valid_pose_vector(pose.get("pos")) else None  # 只使用有效世界坐标。
                random_target = self._random_boundary_target(patrol_boundary, current_position=current_position, rng=self._random)  # 在内部安全线内生成目标点。
                rpy = pose.get("rpy")  # 读取当前 HTTP IMU 姿态。
                # 必要条件或数据不满足时执行安全处理。
                if current_position is not None and self._valid_pose_vector(rpy):  # 坐标和航向都有效时让转向朝向随机点。
                    target_yaw = math.atan2(random_target[1] - float(current_position[1]), random_target[0] - float(current_position[0]))  # 计算随机点方向。
                    yaw_error = self._normalise_radians(target_yaw - float(rpy[2]))  # 计算最短转向方向。
                    turn_left = yaw_error >= 0.0  # 左侧目标使用左转，右侧目标使用右转。
                # 其余情况进入默认的处理路径。
                else:  # 姿态尚不可用时仍允许按原来的方式随机选择方向。
                    turn_left = self._random.random() < 0.5  # 使用随机左右转作为安全回退。
                turn_x = -turn_speed if turn_left else turn_speed  # 按实机标定和独立旋转速度设置转向命令。
                turn_duration = self._random.uniform(0.3, 1.5)  # 随机选择开环转向持续时间。
                turn_name = "随机左转" if turn_left else "随机右转"  # 生成人可读的转向名称。
                self._log("PATROL", f"▶ 巡逻路段 {segment}/{total_text}: 安全随机点=({random_target[0]:.3f},{random_target[1]:.3f})m，{turn_name} {turn_duration:.1f}s，然后前进 {move_duration:.1f}s")  # 记录位于安全区内的随机点和开环动作。

                # 执行本逻辑段的数据处理、状态同步或界面更新。
                turn_result, _center_error = self._drive_once(client, turn_name, {"move_x": 0, "move_y": 0, "turn_x": turn_x, "turn_y": 0}, turn_duration, 10.0, segment, repetitions, boundary=boundary, visualize_command=True, visualization_target=random_target)  # 朝安全随机点开环转向，出界只检查蓝色外部围栏。
                # 根据当前状态或输入选择对应的处理路径。
                if turn_result == "outside":  # 转向漂移导致越界时立即改为回中心。
                    self._log("WARN", "巡逻转向时检测到越界；已归零，开始回中心")  # 记录触发回中心的原因。
                    returned, center_error = self._return_to_boundary_center(client, boundary, move_speed, turn_speed)  # 分别使用前进和旋转幅值回到围栏中心。
                    # 根据当前状态或输入选择对应的处理路径。
                    if returned != "reached":  # 没有安全回到中心时不能继续巡逻。
                        # 根据当前状态或输入选择对应的处理路径。
                        if returned != "stopped":  # 用户主动停止不作为故障显示。
                            failure = f"随机巡逻越界回中心失败（{returned}，中心误差={center_error:.4f}m）"  # 保存回中心失败详情。
                        break  # 结束巡逻循环。
                    self._log("BOUNDARY", f"已回到中心，中心误差={center_error:.4f}m")  # 记录回中心结果。
                    continue  # 从中心开始规划下一个随机路段。
                # 根据当前状态或输入选择对应的处理路径。
                if turn_result == "stopped":  # 停止按钮或线程关闭会结束当前转向。
                    break  # 退出巡逻循环。
                # 根据当前状态或输入选择对应的处理路径。
                if turn_result != "completed":  # 位置数据不可用等安全问题不能忽略。
                    failure = f"巡逻路段 {segment} 转向中止（{turn_result}）"  # 保存安全中止原因。
                    break  # 结束巡逻循环。

                # 执行本逻辑段的数据处理、状态同步或界面更新。
                move_result, _center_error = self._drive_once(client, "向前巡逻", {"move_x": 0, "move_y": move_speed, "turn_x": 0, "turn_y": 0}, move_duration, 10.0, segment, repetitions, boundary=boundary, visualize_command=True, visualization_target=random_target)  # 向安全随机点方向开环前进，出界只检查蓝色外部围栏。
                # 根据当前状态或输入选择对应的处理路径。
                if move_result == "outside":  # 前进越过围栏时立即改为回中心。
                    self._log("WARN", "巡逻前进时检测到越界；已归零，开始回中心")  # 记录触发回中心的原因。
                    returned, center_error = self._return_to_boundary_center(client, boundary, move_speed, turn_speed)  # 分别使用前进和旋转幅值回到围栏中心。
                    # 根据当前状态或输入选择对应的处理路径。
                    if returned != "reached":  # 没有安全回到中心时不能继续巡逻。
                        # 根据当前状态或输入选择对应的处理路径。
                        if returned != "stopped":  # 用户主动停止不作为故障显示。
                            failure = f"随机巡逻越界回中心失败（{returned}，中心误差={center_error:.4f}m）"  # 保存回中心失败详情。
                        break  # 结束巡逻循环。
                    self._log("BOUNDARY", f"已回到中心，中心误差={center_error:.4f}m")  # 记录回中心结果。
                # 前一条件不成立时继续检查下一种情况。
                elif move_result == "stopped":  # 停止按钮或线程关闭会结束当前前进。
                    break  # 退出巡逻循环。
                # 前一条件不成立时继续检查下一种情况。
                elif move_result != "completed":  # 位置数据不可用等安全问题不能忽略。
                    failure = f"巡逻路段 {segment} 前进中止（{move_result}）"  # 保存安全中止原因。
                    break  # 结束巡逻循环。
                # 其余情况进入默认的处理路径。
                else:  # 正常走满设定时间时完成本路段。
                    self._log("PATROL", f"■ 巡逻路段 {segment} 完成，摇杆已归零")  # 只记录动作完成，不计算位置或角度误差。

                # 准备本逻辑段使用的局部数据和中间状态。
                has_more = infinite or segment < repetitions  # 判断后面是否还有巡逻路段。
                # 根据当前状态或输入选择对应的处理路径。
                if settle_time and has_more:  # 仅在路段之间执行用户设置的停留。
                    self._log("PATROL", f"… 路段间停留 {settle_time:.1f}s")  # 记录停留时长。
                    # 根据当前状态或输入选择对应的处理路径。
                    if self._stop_motion.wait(settle_time):  # 停留期间仍然响应停止按钮。
                        break  # 用户停止后退出巡逻循环。

            # 准备本逻辑段使用的局部数据和中间状态。
            stopped = self._stop_motion.is_set() or not self._alive.is_set()  # 汇总用户停止和线程关闭状态。
            message = f"动作执行失败：{failure}" if failure else ("动作已停止" if stopped else "随机巡逻完成")  # 生成最终结果文本。
            self.finished_ok.emit(message)  # 把最终结果发送给界面。
            self._log("ERROR" if failure else "INFO", message)  # 把最终结果写入日志。
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:  # 捕获 HTTP、参数和其他运行异常。
            self._log("ERROR", f"随机巡逻失败: {exc}")  # 记录异常详情。
            self.finished_ok.emit(f"随机巡逻失败: {exc}")  # 把异常详情发送给界面。
        # 无论执行结果如何都完成必要的收尾处理。
        finally:  # 无论以何种方式退出都执行安全清理。
            self._safe_stop(client)  # 重复发送全零摇杆，确保机器狗停止。
            self.recovery_command.emit(None)  # 清除界面上的回中心指令标记。

    # 执行界面提交的手动 API 请求。
    def _execute_manual_api(self, command: dict[str, Any]) -> None:
        """在后台执行控制台请求，避免 HTTP 超时阻塞 Qt 界面。"""
        current = self._client
        # 必要条件或数据不满足时执行安全处理。
        if current is None:
            self.manual_api_result.emit(False, "尚未连接机器人", {})
            return
        method = str(command.get("method", "GET")).upper()
        path = str(command.get("path", "/"))
        port = max(1, min(65535, int(command.get("port", 22000))))
        payload = command.get("payload")
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            parsed = urlsplit(current.control_base)
            host = parsed.hostname
            # 必要条件或数据不满足时执行安全处理。
            if not host:
                raise ValueError("无法从当前连接解析机器人 IP")
            display_host = f"[{host}]" if ":" in host else host
            base = f"{parsed.scheme}://{display_host}:{port}"
            parsed_port = parsed.port or 22000
            client = (
                current
                if port == parsed_port
                else MH4HttpClient(base, timeout=self._timeout)
            )
            # 根据当前状态或输入选择对应的处理路径。
            if (
                method == "POST"
                and path.split("?", 1)[0]
                == "/settings/movement/joystickControl"
                and isinstance(payload, dict)
            ):
                payload = dict(payload)
                payload["timestamp"] = int(time.time() * 1000)

            # 准备本逻辑段使用的局部数据和中间状态。
            safe_payload = self._redact_payload(payload)
            payload_text = (
                ""
                if payload is None
                else " body=" + json.dumps(safe_payload, ensure_ascii=False)
            )
            self._log("API", f"{method} {base}{path}{payload_text}")
            # 根据当前状态或输入选择对应的处理路径。
            if (
                method == "POST"
                and path.split("?", 1)[0] == "/upload/formdata/audio"
            ):
                # 必要条件或数据不满足时执行安全处理。
                if not isinstance(payload, dict):
                    raise ValueError("音频上传缺少表单参数")
                result = client.upload_audio_file(payload)
            # 其余情况进入默认的处理路径。
            else:
                result = client.raw_request(method, path, payload)
            rejected = isinstance(result, dict) and result.get("status") is False
            result_preview = json.dumps(
                self._redact_payload(result), ensure_ascii=False, default=str
            )
            # 根据当前状态或输入选择对应的处理路径。
            if len(result_preview) > 1200:
                result_preview = result_preview[:1200] + "…"
            self._log("WARN" if rejected else "API", f"响应: {result_preview}")
            self.manual_api_result.emit(not rejected, f"{method} {base}{path}", result)
        # 捕获异常并执行日志记录或安全降级。
        except Exception as exc:
            self._log("ERROR", f"手动接口请求失败: {method} :{port}{path}: {exc}")
            self.manual_api_result.emit(False, f"{method} :{port}{path}: {exc}", {})

    # 隐藏日志载荷中的敏感或体积较大的字段。
    @classmethod
    def _redact_payload(cls, value: Any) -> Any:
        """日志中隐藏密码和图传令牌，实际 HTTP 请求仍使用原值。"""
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(value, dict):
            redacted = {}
            # 逐项处理当前集合中的数据。
            for key, item in value.items():
                lowered = str(key).lower()
                # 根据当前状态或输入选择对应的处理路径。
                if lowered in {"passwd", "password", "publishertoken", "token"}:
                    redacted[key] = "***"
                # 其余情况进入默认的处理路径。
                else:
                    redacted[key] = cls._redact_payload(item)
            return redacted
        # 根据当前状态或输入选择对应的处理路径。
        if isinstance(value, list):
            return [cls._redact_payload(item) for item in value]
        return value

    # 按给定摇杆轴持续驱动指定时间。
    def _drive_once(
        self,
        client: MH4HttpClient,
        name: str,
        axes: dict[str, int],
        duration: float,
        rate_hz: float,
        cycle: int,
        total: int,
        *,
        boundary: dict[str, Any] | None = None,
        visualize_command: bool = False,
        visualization_target: list[float] | None = None,
    ) -> tuple[str, float]:
        started = time.monotonic()
        period = 1.0 / rate_hz
        next_tick = started
        center_error = float("inf")
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:  # 确保动作完成、越界、停止或异常时都会清除当前指令图层。
            # 在运行条件成立期间持续执行本段逻辑。
            while self._alive.is_set() and not self._stop_motion.is_set():
                pose = self._pose_snapshot() if boundary is not None or visualize_command else {}  # 围栏检查和可视化共用同一份实时姿态。
                # 必要条件或数据不满足时执行安全处理。
                if boundary is not None:
                    position = pose.get("pos")
                    # 根据当前状态或输入选择对应的处理路径。
                    if (
                        position is None
                        or len(position) < 3
                        or time.monotonic() - float(pose.get("pos_at", 0.0)) > 1.0
                        or not all(
                            math.isfinite(float(value)) for value in position[:3]
                        )
                    ):
                        self._safe_stop(client)
                        return "position_unavailable", center_error
                    center = boundary["center"]
                    center_error = math.hypot(
                        float(position[0]) - float(center[0]),
                        float(position[1]) - float(center[1]),
                    )
                    # 根据当前状态或输入选择对应的处理路径。
                    if self._boundary_outside(position, boundary):
                        self._safe_stop(client)
                        return "outside", center_error
                elapsed = time.monotonic() - started
                # 根据当前状态或输入选择对应的处理路径。
                if elapsed >= duration:
                    break
                # 根据当前状态或输入选择对应的处理路径。
                if visualize_command:  # 随机巡逻的每个控制周期都刷新当前指令图形。
                    command_view = self._joystick_command_visualization(pose, axes, target=visualization_target)  # 优先显示本段安全随机点。
                    # 必要条件或数据不满足时执行安全处理。
                    if command_view is not None:  # 位置或 IMU 暂不可用时保留上一帧，不发送错误图形。
                        self.recovery_command.emit(command_view)  # 将本周期指令发送给 3D 轨迹控件。
                client.joystick(**axes)
                next_tick += period
                # 根据当前状态或输入选择对应的处理路径。
                if next_tick < time.monotonic():  # HTTP 响应变慢时丢弃已经错过的发送周期。
                    next_tick = time.monotonic() + period  # 从当前时间重新排期，避免连续补发压垮控制器。
                wait = max(0.0, next_tick - time.monotonic())
                # 根据当前状态或输入选择对应的处理路径。
                if self._stop_motion.wait(wait):
                    break
        # 无论执行结果如何都完成必要的收尾处理。
        finally:  # 所有退出路径都必须移除已经完成的指令图形。
            # 根据当前状态或输入选择对应的处理路径。
            if visualize_command:  # 普通动作没有创建该图层，不需要重复刷新界面。
                self.recovery_command.emit(None)  # 清除紫色箭头、蓝色航向和黄色转向弧。
        self._safe_stop(client)
        # 必要条件或数据不满足时执行安全处理。
        if self._stop_motion.is_set() or not self._alive.is_set():
            return "stopped", center_error
        return "completed", center_error

    # 生成当前摇杆指令对应的可视化路径。
    @classmethod
    def _joystick_command_visualization(
        cls,
        pose: dict[str, Any],
        axes: dict[str, int],
        *,
        target: list[float] | None = None,
    ) -> dict[str, Any] | None:
        """把当前摇杆命令转换成 3D 视图使用的世界坐标指令。"""  # 开环动作没有真实目标点，因此只画方向和转向趋势。
        position = pose.get("pos")  # 读取当前世界坐标。
        rpy = pose.get("rpy")  # 读取当前 HTTP IMU 姿态。
        # 必要条件或数据不满足时执行安全处理。
        if not cls._valid_pose_vector(position) or not cls._valid_pose_vector(rpy):  # 缺少位置或航向时无法可靠绘制世界方向。
            return None  # 保留界面上一帧，等待姿态数据恢复。
        current = [float(value) for value in position[:3]]  # 复制当前坐标，避免修改共享采样数据。
        yaw = float(rpy[2])  # 读取当前世界偏航角。
        move_x = int(axes.get("move_x", 0))  # 读取右正左负的横移摇杆值。
        move_y = int(axes.get("move_y", 0))  # 读取前正后负的纵向摇杆值。
        turn_x = int(axes.get("turn_x", 0))  # 读取右正左负的转向摇杆值。
        current_yaw = math.degrees(yaw)  # 绘图接口使用角度而不是弧度。
        # 必要条件或数据不满足时执行安全处理。
        if target is not None and cls._valid_pose_vector(target):  # 随机巡逻提供安全目标点时优先画真实生成点。
            target_point = [float(value) for value in target[:3]]  # 复制目标坐标避免修改规划数据。
            target_yaw = math.degrees(math.atan2(target_point[1] - current[1], target_point[0] - current[0]))  # 计算当前位置指向目标点的航向。
            phase = "turn" if move_x == 0 and move_y == 0 and turn_x != 0 else "move"  # 选择黄色转向弧或紫色移动线。
            return {"current": current, "target": target_point, "current_yaw": current_yaw, "target_yaw": target_yaw, "phase": phase}  # 显示当前位置到安全随机点的指令。
        # 根据当前状态或输入选择对应的处理路径。
        if move_x == 0 and move_y == 0 and turn_x != 0:  # 纯转向动作使用黄色圆弧显示方向。
            turn_degrees = 90.0 if turn_x < 0 else -90.0  # 按实机标定把摇杆符号换算成左转或右转。
            return {"current": current, "target": list(current), "current_yaw": current_yaw, "target_yaw": current_yaw + turn_degrees, "phase": "turn"}  # 返回原地转向可视化参数。
        # 根据当前状态或输入选择对应的处理路径。
        if move_x == 0 and move_y == 0:  # 全零摇杆不对应任何运动方向。
            return None  # 不绘制无效箭头。
        body_forward = float(move_y)  # 机器人本体前向分量直接来自纵向摇杆。
        body_left = -float(move_x)  # 横移摇杆负值代表本体左向，因此转换符号。
        world_x = math.cos(yaw) * body_forward - math.sin(yaw) * body_left  # 把本体运动向量旋转到世界 X 方向。
        world_y = math.sin(yaw) * body_forward + math.cos(yaw) * body_left  # 把本体运动向量旋转到世界 Y 方向。
        magnitude = max(math.hypot(world_x, world_y), 1.0)  # 取得非零向量长度供归一化使用。
        arrow_length = 0.8  # 使用固定可视长度，表达指令方向而不伪装成距离目标。
        target = [current[0] + world_x / magnitude * arrow_length, current[1] + world_y / magnitude * arrow_length, current[2]]  # 生成随当前位置更新的方向目标点。
        return {"current": current, "target": target, "current_yaw": current_yaw, "target_yaw": current_yaw, "phase": "move"}  # 返回紫色移动箭头和蓝色当前航向。

    # 提取边界中心、尺寸和多边形几何信息。
    @staticmethod
    def _boundary_geometry(
        center: list[float], length: float, width: float, yaw: float
    ) -> dict[str, Any]:
        cx, cy = float(center[0]), float(center[1])
        cz = float(center[2]) if len(center) >= 3 else 0.0
        forward = (math.cos(yaw), math.sin(yaw))
        left = (-math.sin(yaw), math.cos(yaw))
        half_length = float(length) / 2.0
        half_width = float(width) / 2.0
        corners = []
        # 逐项处理当前集合中的数据。
        for forward_sign, left_sign in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
            corners.append([
                cx + forward_sign * forward[0] * half_length
                + left_sign * left[0] * half_width,
                cy + forward_sign * forward[1] * half_length
                + left_sign * left[1] * half_width,
                cz,
            ])
        return {
            "kind": "rectangle",
            "center": [cx, cy, cz],
            "corners": corners,
            "length": float(length),
            "width": float(width),
            "yaw": float(yaw),
        }

    # 按安全距离向内收缩巡逻目标区域。
    @classmethod
    def _inset_boundary(
        cls,
        boundary: dict[str, Any],
        margin: float,
    ) -> dict[str, Any]:
        """生成与原围栏各边至少保持指定距离的内部安全围栏。"""  # 该范围仅约束随机点生成和橙色可视化。
        margin = max(0.0, float(margin))  # 把安全距离规范为非负浮点数。
        center = [float(value) for value in boundary["center"][:3]]  # 复制围栏中心坐标。
        # 根据当前状态或输入选择对应的处理路径。
        if boundary.get("kind") != "polygon":  # 矩形可以精确地从四边各缩进指定距离。
            length = float(boundary["length"]) - margin * 2.0  # 同时缩进长边两端。
            width = float(boundary["width"]) - margin * 2.0  # 同时缩进宽边两端。
            # 根据当前状态或输入选择对应的处理路径。
            if length < 0.20 or width < 0.20:  # 保留最小可用巡逻区域，避免退化几何。
                maximum = max(0.0, min(float(boundary["length"]), float(boundary["width"])) / 2.0 - 0.10)  # 计算当前矩形允许的近似上限。
                raise ValueError(f"边界安全距离 {margin:.2f}m 过大；当前围栏最多约可设置 {maximum:.2f}m")  # 提示用户降低安全距离或扩大围栏。
            return cls._boundary_geometry(center, length, width, float(boundary["yaw"]))  # 返回同中心、同朝向的精确内缩矩形。

        # 准备本逻辑段使用的局部数据和中间状态。
        corners = boundary["corners"]  # 读取凸多边形边界点。
        minimum_center_distance = float("inf")  # 查找中心到最近边的垂直距离。
        # 逐项处理当前集合中的数据。
        for start, end in zip(corners, corners[1:] + corners[:1]):  # 逐边计算中心到直线的距离。
            edge_x = float(end[0]) - float(start[0])  # 计算边的 X 分量。
            edge_y = float(end[1]) - float(start[1])  # 计算边的 Y 分量。
            edge_length = math.hypot(edge_x, edge_y)  # 计算边长用于归一化。
            # 根据当前状态或输入选择对应的处理路径。
            if edge_length <= 1e-9:  # 重复顶点不能形成有效围栏边。
                raise ValueError("运动范围含重复边界点")  # 拒绝退化多边形。
            center_cross = abs(edge_x * (center[1] - float(start[1])) - edge_y * (center[0] - float(start[0])))  # 计算边与中心向量的叉积绝对值。
            minimum_center_distance = min(minimum_center_distance, center_cross / edge_length)  # 保存最近边距离。
        # 根据当前状态或输入选择对应的处理路径。
        if minimum_center_distance <= margin + 0.10:  # 内缩后必须给中心附近保留至少二十厘米直径。
            maximum = max(0.0, minimum_center_distance - 0.10)  # 计算当前多边形允许的近似上限。
            raise ValueError(f"边界安全距离 {margin:.2f}m 过大；当前多点围栏最多约可设置 {maximum:.2f}m")  # 提示用户修改参数。
        scale = 1.0 - margin / minimum_center_distance  # 计算以中心为基准的保守内缩比例。
        inset_corners = [[center[0] + (float(point[0]) - center[0]) * scale, center[1] + (float(point[1]) - center[1]) * scale, center[2]] for point in corners]  # 生成与每条原边至少相距 margin 的相似多边形。
        inset = cls._polygon_boundary_geometry(inset_corners)  # 重新计算内缩多边形跨度和几何中心。
        inset["center"] = center  # 保持回中心目标与外部围栏完全一致。
        return inset  # 返回内部安全围栏。

    # 在安全区域内随机生成一个巡逻目标。
    @staticmethod
    def _random_boundary_target(
        boundary: dict[str, Any],
        *,
        current_position: list[float] | None = None,
        rng: Any = random,
    ) -> list[float]:
        """在凸安全围栏内按面积随机生成巡逻点。"""  # 生成点已经通过内缩围栏保证边界安全距离。
        center = [float(value) for value in boundary["center"][:3]]  # 使用安全围栏中心拆分三角形。
        corners = boundary["corners"]  # 读取安全围栏顶点。
        triangles: list[tuple[list[float], list[float], float]] = []  # 保存三角形边点和累计面积。
        total_area = 0.0  # 初始化安全区域总面积。
        # 逐项处理当前集合中的数据。
        for start, end in zip(corners, corners[1:] + corners[:1]):  # 将凸围栏拆成中心到每条边的三角形。
            area = abs((float(start[0]) - center[0]) * (float(end[1]) - center[1]) - (float(start[1]) - center[1]) * (float(end[0]) - center[0])) / 2.0  # 计算当前三角形面积。
            # 根据当前状态或输入选择对应的处理路径。
            if area <= 1e-12:  # 跳过退化三角形。
                continue  # 继续处理下一条边。
            total_area += area  # 累加面积供加权选择。
            triangles.append((start, end, total_area))  # 保存当前三角形的累计面积上限。
        # 必要条件或数据不满足时执行安全处理。
        if not triangles:  # 没有有效面积时无法生成随机点。
            raise ValueError("边界安全距离内没有可用巡逻区域")  # 要求用户减小安全距离或扩大围栏。
        # 逐项处理当前集合中的数据。
        for _attempt in range(64):  # 尝试避开离当前位置过近的无效目标点。
            selected = rng.random() * total_area  # 按面积随机选择一个三角形。
            start, end, _limit = triangles[-1]  # 默认使用最后一个三角形以处理浮点边界。
            # 逐项处理当前集合中的数据。
            for candidate_start, candidate_end, limit in triangles:  # 查找随机面积落入的三角形。
                # 根据当前状态或输入选择对应的处理路径。
                if selected <= limit:  # 找到对应累计面积区间。
                    start, end = candidate_start, candidate_end  # 选择当前三角形。
                    break  # 停止查找。
            radial = math.sqrt(rng.random())  # 使用平方根保证三角形内面积均匀。
            along = rng.random()  # 随机选择两条外边顶点之间的比例。
            target = [(1.0 - radial) * center[0] + radial * ((1.0 - along) * float(start[0]) + along * float(end[0])), (1.0 - radial) * center[1] + radial * ((1.0 - along) * float(start[1]) + along * float(end[1])), center[2]]  # 生成三角形内的随机世界坐标。
            # 必要条件或数据不满足时执行安全处理。
            if current_position is None or math.hypot(target[0] - float(current_position[0]), target[1] - float(current_position[1])) >= 0.20:  # 避免生成几乎等于当前位置的点。
                return target  # 返回满足条件的安全随机点。
        return center  # 区域很小时回退到一定安全的围栏中心。

    # 计算平面点集的凸包多边形。
    @staticmethod
    def _convex_hull(points: list[list[float]]) -> list[list[float]]:
        """返回按逆时针排列的 XY 凸包，忽略相同 XY 的重复点。"""
        unique: dict[tuple[float, float], list[float]] = {}
        # 逐项处理当前集合中的数据。
        for point in points:
            unique[(float(point[0]), float(point[1]))] = [
                float(point[0]), float(point[1]), float(point[2])
            ]
        ordered = [unique[key] for key in sorted(unique)]
        # 根据当前状态或输入选择对应的处理路径。
        if len(ordered) < 3:
            raise ValueError("多点范围至少需要 3 个不同位置")

        # 封装 cross 对应的独立处理逻辑。
        def cross(
            origin: list[float], first: list[float], second: list[float]
        ) -> float:
            return (
                (first[0] - origin[0]) * (second[1] - origin[1])
                - (first[1] - origin[1]) * (second[0] - origin[0])
            )

        # 执行本逻辑段的数据处理、状态同步或界面更新。
        lower: list[list[float]] = []
        # 逐项处理当前集合中的数据。
        for point in ordered:
            # 在运行条件成立期间持续执行本段逻辑。
            while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
                lower.pop()
            lower.append(point)
        upper: list[list[float]] = []
        # 逐项处理当前集合中的数据。
        for point in reversed(ordered):
            # 在运行条件成立期间持续执行本段逻辑。
            while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
                upper.pop()
            upper.append(point)
        hull = lower[:-1] + upper[:-1]
        # 根据当前状态或输入选择对应的处理路径。
        if len(hull) < 3:
            raise ValueError("多点范围的标点不能全部位于同一直线")
        return hull

    # 计算多边形边界的中心和包围尺寸。
    @classmethod
    def _polygon_boundary_geometry(
        cls, points: list[list[float]]
    ) -> dict[str, Any]:
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(points, (list, tuple)) or not 3 <= len(points) <= 100:
            raise ValueError("多点范围需要 3～100 个位置点")
        values: list[list[float]] = []
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            # 逐项处理当前集合中的数据。
            for point in points:
                # 必要条件或数据不满足时执行安全处理。
                if not isinstance(point, (list, tuple)) or len(point) < 3:
                    raise ValueError("多点范围含无效位置点")
                value = [float(item) for item in point[:3]]
                # 必要条件或数据不满足时执行安全处理。
                if not all(math.isfinite(item) for item in value):
                    raise ValueError("多点范围含非有限数值")
                values.append(value)
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError) as exc:
            # 根据当前状态或输入选择对应的处理路径。
            if isinstance(exc, ValueError) and str(exc).startswith("多点范围"):
                raise
            raise ValueError("多点范围含无效位置点") from exc

        # 准备本逻辑段使用的局部数据和中间状态。
        hull = cls._convex_hull(values)
        twice_area = 0.0
        centroid_x = 0.0
        centroid_y = 0.0
        # 逐项处理当前集合中的数据。
        for start, end in zip(hull, hull[1:] + hull[:1]):
            edge_cross = start[0] * end[1] - end[0] * start[1]
            twice_area += edge_cross
            centroid_x += (start[0] + end[0]) * edge_cross
            centroid_y += (start[1] + end[1]) * edge_cross
        area = abs(twice_area) / 2.0
        # 根据当前状态或输入选择对应的处理路径。
        if area < 0.01:
            raise ValueError("多点范围面积过小，请扩大标点间距")
        centroid_x /= 3.0 * twice_area
        centroid_y /= 3.0 * twice_area
        center_z = sum(point[2] for point in hull) / len(hull)
        min_x = min(point[0] for point in hull)
        max_x = max(point[0] for point in hull)
        min_y = min(point[1] for point in hull)
        max_y = max(point[1] for point in hull)
        length = max_x - min_x
        width = max_y - min_y
        # 根据当前状态或输入选择对应的处理路径。
        if length > 50.0 or width > 50.0:
            raise ValueError("多点范围的 XY 跨度不能超过 50 m")
        return {
            "kind": "polygon",
            "center": [centroid_x, centroid_y, center_z],
            "corners": hull,
            # 保留跨度供回中心容差和超时估算使用。
            "length": length,
            "width": width,
            "yaw": 0.0,
        }

    # 校验并规范化外部传入的边界配置。
    @classmethod
    def _validated_boundary(cls, raw: Any) -> dict[str, Any] | None:
        # 必要条件或数据不满足时执行安全处理。
        if raw is None:
            return None
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(raw, dict):
            raise ValueError("运动范围参数格式错误")
        # 根据当前状态或输入选择对应的处理路径。
        if raw.get("kind") == "polygon":
            return cls._polygon_boundary_geometry(raw.get("corners"))
        center = raw.get("center")
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(center, (list, tuple)) or len(center) < 3:
            raise ValueError("运动范围缺少中心坐标")
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            center_values = [float(value) for value in center[:3]]
            length = float(raw.get("length"))
            width = float(raw.get("width"))
            yaw = float(raw.get("yaw"))
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError) as exc:
            raise ValueError("运动范围含无效数值") from exc
        # 必要条件或数据不满足时执行安全处理。
        if not all(math.isfinite(value) for value in (*center_values, length, width, yaw)):
            raise ValueError("运动范围含非有限数值")
        # 必要条件或数据不满足时执行安全处理。
        if not 0.4 <= length <= 50.0 or not 0.4 <= width <= 50.0:
            raise ValueError("运动范围长宽必须在 0.4～50 m 内")
        return cls._boundary_geometry(center_values, length, width, yaw)

    # 把世界坐标转换到边界局部坐标系。
    @staticmethod
    def _boundary_local_position(
        position: list[float], boundary: dict[str, Any]
    ) -> tuple[float, float]:
        center = boundary["center"]
        yaw = float(boundary["yaw"])
        dx = float(position[0]) - float(center[0])
        dy = float(position[1]) - float(center[1])
        return (
            math.cos(yaw) * dx + math.sin(yaw) * dy,
            -math.sin(yaw) * dx + math.cos(yaw) * dy,
        )

    # 判断当前位置是否越过蓝色实际边界。
    @classmethod
    def _boundary_outside(
        cls, position: list[float], boundary: dict[str, Any]
    ) -> bool:
        # 根据当前状态或输入选择对应的处理路径。
        if boundary.get("kind") == "polygon":
            x = float(position[0])
            y = float(position[1])
            corners = boundary["corners"]
            # 逐项处理当前集合中的数据。
            for start, end in zip(corners, corners[1:] + corners[:1]):
                edge_cross = (
                    (float(end[0]) - float(start[0]))
                    * (y - float(start[1]))
                    - (float(end[1]) - float(start[1]))
                    * (x - float(start[0]))
                )
                # 根据当前状态或输入选择对应的处理路径。
                if edge_cross < -1e-9:
                    return True
            return False
        forward, left = cls._boundary_local_position(position, boundary)
        return (
            abs(forward) > float(boundary["length"]) / 2.0
            or abs(left) > float(boundary["width"]) / 2.0
        )

    # 在越界后组织并执行回中心流程。
    def _return_to_boundary_center(
        self,
        client: MH4HttpClient,
        boundary: dict[str, Any],
        amplitude: int,
        turn_amplitude: int | None = None,
    ) -> tuple[str, float]:
        """让机器狗朝向围栏中心并前进，直到回到中心附近。"""  # 回中心是唯一使用位置和航向闭环的巡逻阶段。
        tolerance = max(0.05, min(0.15, min(boundary["length"], boundary["width"]) * 0.08))  # 按围栏尺寸设置到达容差。
        timeout = max(8.0, max(boundary["length"], boundary["width"]) * 12.0)  # 按围栏跨度设置最长回中心时间。
        recovery_amplitude = max(self._RETURN_START_AMPLITUDE, min(self._RETURN_MAX_AMPLITUDE, int(amplitude)))  # 使用能越过实机起步死区的回中心直行幅值。
        requested_turn = amplitude if turn_amplitude is None else turn_amplitude  # 未单独配置时兼容旧版共用速度。
        recovery_turn_amplitude = max(self._RETURN_START_AMPLITUDE, min(self._RETURN_MAX_AMPLITUDE, int(requested_turn)))  # 独立限制回中心旋转幅值。
        center = boundary["center"]  # 读取围栏中心世界坐标。
        self._log("BOUNDARY", f"开始回中心: 目标=({center[0]:.3f},{center[1]:.3f})m，前进摇杆={recovery_amplitude}，旋转摇杆={recovery_turn_amplitude}，容差={tolerance:.3f}m，超时={timeout:.1f}s")  # 明确报告独立的回中心速度。
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:  # 确保回中心结束后清除界面指令标记。
            result, error = self._drive_to_boundary_center(
                client, boundary, recovery_amplitude, tolerance, timeout,
                turn_amplitude=recovery_turn_amplitude,
            )  # 执行转向加前进的闭环回中心。
            relaxed_tolerance = min(0.20, max(tolerance + 0.03, tolerance * 1.25))  # 为定位小幅抖动保留缓冲区。
            # 根据当前状态或输入选择对应的处理路径。
            if result == "timeout" and error <= relaxed_tolerance:  # 超时但已经很靠近中心时视为完成。
                self._log(
                    "WARN",
                    f"回中心已进入近中心缓冲区: 误差={error:.4f}m，"
                    f"严格容差={tolerance:.4f}m，按完成处理",
                )  # 记录放宽容差的原因。
                return "reached", error  # 允许继续下一巡逻路段。
            self._log("BOUNDARY" if result == "reached" else "WARN", f"回中心结束: 状态={result}，中心误差={error:.4f}m")  # 始终报告回中心结束状态。
            return result, error  # 把实际状态交回巡逻主流程。
        # 无论执行结果如何都完成必要的收尾处理。
        finally:  # 无论成功、停止或异常都清理可视化状态。
            self.recovery_command.emit(None)  # 清除紫色回中心目标和指令。

    # 计算边界中心并驱动机器人返回。
    def _drive_to_boundary_center(
        self,
        client: MH4HttpClient,
        boundary: dict[str, Any],
        amplitude: int,
        tolerance: float,
        timeout: float,
        *,
        turn_amplitude: int | None = None,
    ) -> tuple[str, float]:
        return self._drive_to_world_target(
            client,
            boundary["center"],
            amplitude,
            tolerance,
            timeout,
            motion_label="回中心",
            turn_amplitude=turn_amplitude,
        )

    # 根据实时位置和航向闭环驶向世界坐标目标。
    def _drive_to_world_target(
        self,
        client: MH4HttpClient,
        target: list[float],
        amplitude: int,
        tolerance: float,
        timeout: float,
        *,
        motion_label: str,
        boundary: dict[str, Any] | None = None,
        turn_amplitude: int | None = None,
    ) -> tuple[str, float]:
        started = time.monotonic()
        next_progress_log = started  # 允许第一条回中心命令立即打印日志。
        last_error = float("inf")
        turn_progress_at = started  # 记录最近一次检测到有效转向的时刻。
        turn_progress_yaw: float | None = None  # 保存检测转向进展时的参考航向。
        was_turning_only = False  # 区分原地转向阶段和向前靠近阶段。
        # 在运行条件成立期间持续执行本段逻辑。
        while self._alive.is_set() and not self._stop_motion.is_set():
            pose = self._pose_snapshot()
            now = time.monotonic()
            position = pose.get("pos")
            # 根据当前状态或输入选择对应的处理路径。
            if self._valid_pose_vector(position):
                last_error = math.hypot(
                    float(target[0]) - float(position[0]),
                    float(target[1]) - float(position[1]),
                )

            # 准备本逻辑段使用的局部数据和中间状态。
            unavailable = self._return_pose_unavailable(pose, now)
            # 必要条件或数据不满足时执行安全处理。
            if unavailable is not None:
                status, detail = unavailable
                self._log(
                    "WARN",
                    f"{motion_label}暂停: {detail}；已归零并等待数据恢复"
                    f"（最多 {self._RETURN_POSE_RECOVERY_TIMEOUT:.1f}s）",
                )
                self._safe_stop(client)
                recovered_at = self._wait_for_pose_recovery(
                    self._RETURN_POSE_RECOVERY_TIMEOUT
                )
                # 必要条件或数据不满足时执行安全处理。
                if recovered_at is None:
                    # 必要条件或数据不满足时执行安全处理。
                    if self._stop_motion.is_set() or not self._alive.is_set():
                        return "stopped", last_error
                    return status, last_error
                self._log(
                    "INFO",
                    f"{motion_label}数据已恢复，"
                    f"暂停 {recovered_at - now:.2f}s 后继续",
                )
                continue

            # 准备本逻辑段使用的局部数据和中间状态。
            position = pose["pos"]
            rpy = pose["rpy"]
            dx = float(target[0]) - float(position[0])
            dy = float(target[1]) - float(position[1])
            last_error = math.hypot(dx, dy)
            # 必要条件或数据不满足时执行安全处理。
            if boundary is not None and self._boundary_outside(position, boundary):
                self._safe_stop(client)
                return "outside", last_error
            # 根据当前状态或输入选择对应的处理路径。
            if last_error <= tolerance:
                self._safe_stop(client)
                return "reached", last_error
            # 根据当前状态或输入选择对应的处理路径。
            if now - started >= timeout:
                self._safe_stop(client)
                return "timeout", last_error
            yaw = float(rpy[2])
            axes = self._axes_to_world_target(position, target, yaw, amplitude, tolerance, turn_amplitude=turn_amplitude)  # 使用独立旋转幅值计算回中心摇杆命令。
            target_yaw = math.atan2(dy, dx)  # 计算当前点指向中心的目标航向。
            yaw_error = self._normalise_radians(target_yaw - yaw)  # 计算正负一百八十度内的航向误差。
            turning_only = axes["move_y"] == 0 and axes["turn_x"] != 0  # 判断本周期是否处于原地转向阶段。
            # 必要条件或数据不满足时执行安全处理。
            if turning_only and not was_turning_only:  # 刚进入原地转向时建立无响应检测基线。
                turn_progress_at = now  # 从当前时刻开始计时。
                turn_progress_yaw = yaw  # 保存当前航向作为进展参考。
            # 前一条件不成立时继续检查下一种情况。
            elif turning_only and turn_progress_yaw is not None:  # 持续转向时检查 IMU 是否真的发生变化。
                yaw_progress = abs(self._normalise_radians(yaw - turn_progress_yaw))  # 计算参考点以来的实际转角。
                # 根据当前状态或输入选择对应的处理路径。
                if yaw_progress >= self._RETURN_TURN_PROGRESS:  # 航向累计变化达到三度说明机器狗正在响应。
                    turn_progress_at = now  # 重置无响应计时器。
                    turn_progress_yaw = yaw  # 使用新航向作为下一段进展参考。
                # 前一条件不成立时继续检查下一种情况。
                elif now - turn_progress_at >= self._RETURN_TURN_STALL_TIMEOUT:  # 连续三秒没有有效转向时停止等待。
                    self._safe_stop(client)  # 立即归零，避免持续发送无效命令。
                    self._log("ERROR", f"{motion_label}转向无响应: 已发送 turn_x={axes['turn_x']:+d} 持续 {now - turn_progress_at:.1f}s，实际航向变化小于 {math.degrees(self._RETURN_TURN_PROGRESS):.1f}°")  # 明确报告实机未响应。
                    return "turn_unresponsive", last_error  # 结束回中心并交由主流程报告失败。
            # 前一条件不成立时继续检查下一种情况。
            elif not turning_only:  # 已朝向中心并开始前进时清除转向检测基线。
                turn_progress_yaw = None  # 下一次原地转向时重新建立参考航向。
            was_turning_only = turning_only  # 保存当前控制阶段供下一周期比较。
            self.recovery_command.emit({
                "current": list(position[:3]),
                "target": list(target[:3]),
                "current_yaw": math.degrees(yaw),
                "target_yaw": math.degrees(target_yaw),
                "phase": "turn" if turning_only else "move",
            })
            # 根据当前状态或输入选择对应的处理路径。
            if now >= next_progress_log:  # 每秒输出一次，避免回中心过程看起来像卡死。
                self._log("BOUNDARY", f"回中心中: 当前位置=({position[0]:.3f},{position[1]:.3f})m，中心误差={last_error:.3f}m，航向={math.degrees(yaw):.1f}°，目标航向={math.degrees(target_yaw):.1f}°，航向误差={math.degrees(yaw_error):+.1f}°，摇杆=前后{axes['move_y']:+d}/转向{axes['turn_x']:+d}")  # 报告位置、航向误差和真实控制量。
                next_progress_log = now + 1.0  # 安排下一条进度日志。
            client.joystick(**axes)  # 向控制器发送本周期回中心命令。
            # 根据当前状态或输入选择对应的处理路径。
            if self._stop_motion.wait(0.1):
                break
        self._safe_stop(client)
        return "stopped", last_error

    # 校验姿态或位置向量是否完整有效。
    @staticmethod
    def _valid_pose_vector(value: Any) -> bool:
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            return False
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            return all(math.isfinite(float(item)) for item in value[:3])
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError):
            return False

    # 处理回中心期间姿态数据不可用的情况。
    @classmethod
    def _return_pose_unavailable(
        cls, pose: dict[str, Any], now: float
    ) -> tuple[str, str] | None:
        position = pose.get("pos")
        # 必要条件或数据不满足时执行安全处理。
        if not cls._valid_pose_vector(position):
            return "position_unavailable", "gRPC 位置不可用"
        position_age = max(0.0, now - float(pose.get("pos_at", 0.0)))
        # 根据当前状态或输入选择对应的处理路径。
        if position_age > cls._POSE_MAX_AGE:
            return (
                "position_unavailable",
                f"gRPC 位置已 {position_age:.2f}s 未更新",
            )

        # 准备本逻辑段使用的局部数据和中间状态。
        rpy = pose.get("rpy")
        # 必要条件或数据不满足时执行安全处理。
        if not cls._valid_pose_vector(rpy):
            return "imu_unavailable", "HTTP IMU 不可用"
        rpy_age = max(0.0, now - float(pose.get("rpy_at", 0.0)))
        # 根据当前状态或输入选择对应的处理路径。
        if rpy_age > cls._POSE_MAX_AGE:
            return "imu_unavailable", f"HTTP IMU 已 {rpy_age:.2f}s 未更新"
        return None

    # 等待新的有效姿态数据恢复。
    def _wait_for_pose_recovery(self, timeout: float) -> float | None:
        deadline = time.monotonic() + max(0.0, float(timeout))
        # 在运行条件成立期间持续执行本段逻辑。
        while self._alive.is_set() and not self._stop_motion.is_set():
            now = time.monotonic()
            # 必要条件或数据不满足时执行安全处理。
            if self._return_pose_unavailable(self._pose_snapshot(), now) is None:
                return now
            remaining = deadline - now
            # 根据当前状态或输入选择对应的处理路径。
            if remaining <= 0.0:
                break
            # 根据当前状态或输入选择对应的处理路径。
            if self._stop_motion.wait(
                min(self._RETURN_POSE_POLL_INTERVAL, remaining)
            ):
                break
        return None

    # 把局部摇杆动作换算为世界坐标目标。
    @staticmethod
    def _axes_to_world_target(
        position: list[float],
        target: list[float],
        yaw: float,
        amplitude: int,
        tolerance: float,
        *,
        turn_amplitude: int | None = None,
    ) -> dict[str, int]:
        """生成只含转向和前进的回中心摇杆命令。"""  # 避免依赖机器狗可能不稳定的横移或斜移能力。
        dx = float(target[0]) - float(position[0])  # 计算中心相对当前位置的世界 X 偏差。
        dy = float(target[1]) - float(position[1])  # 计算中心相对当前位置的世界 Y 偏差。
        distance = math.hypot(dx, dy)  # 计算当前中心误差。
        target_yaw = math.atan2(dy, dx)  # 计算机器狗面向中心所需的世界航向。
        yaw_error = HttpAutoMoveWorker._normalise_radians(target_yaw - float(yaw))  # 把航向误差归一化到正负一百八十度。
        slow_radius = max(HttpAutoMoveWorker._RETURN_SLOW_RADIUS, tolerance * 4.0)  # 设置靠近中心时的减速半径。
        speed_scale = min(1.0, distance / slow_radius)  # 根据中心距离逐渐降低输出。
        minimum = min(int(amplitude), HttpAutoMoveWorker._RETURN_MIN_AMPLITUDE)  # 保证低速命令仍足以克服起步死区。
        forward_output = max(minimum, int(int(amplitude) * speed_scale))  # 计算本周期向前幅值。
        requested_turn = amplitude if turn_amplitude is None else turn_amplitude  # 未单独指定时保持旧版共用幅值行为。
        turn_limit = max(HttpAutoMoveWorker._RETURN_MIN_AMPLITUDE, int(requested_turn))  # 使用独立完整旋转幅值越过实机转向死区。
        turn_scale = min(1.0, abs(yaw_error) / math.radians(45.0))  # 航向误差越大，转向命令越强。
        turn_output = max(minimum, int(turn_limit * turn_scale))  # 计算能越过起转死区的转向幅值。
        turn_x = -turn_output if yaw_error > 0.0 else turn_output  # 按实机标定选择左转或右转符号。
        # 根据当前状态或输入选择对应的处理路径。
        if abs(yaw_error) <= math.radians(3.0):  # 基本朝向中心时不再左右抖动。
            turn_x = 0  # 清除很小的转向命令。
        # 根据当前状态或输入选择对应的处理路径。
        if abs(yaw_error) >= math.radians(45.0):  # 中心位于侧后方时先原地转向。
            move_y = 0  # 暂停前进，防止朝错误方向继续越界。
        # 其余情况进入默认的处理路径。
        else:  # 面向中心后才允许向前靠近。
            alignment_scale = max(0.35, math.cos(yaw_error))  # 航向尚有偏差时适当降低前进幅值。
            move_y = max(minimum, int(forward_output * alignment_scale))  # 计算修正后的正向摇杆幅值。
        return {"move_x": 0, "move_y": move_y, "turn_x": turn_x, "turn_y": 0}  # 禁用横移，只返回转向和前进命令。

    # 保存 exchange 返回的最新 HTTP 姿态。
    def _remember_exchange(self, data: dict[str, Any]) -> None:
        """保存 HTTP IMU，供误差计算和指令可视化使用。"""
        imu = data.get("imu") if isinstance(data.get("imu"), dict) else {}
        rpy = imu.get("rpy")
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(rpy, (list, tuple)) or len(rpy) < 3:
            return
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            values = [float(value) for value in rpy[:3]]
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError):
            return
        # 必要条件或数据不满足时执行安全处理。
        if not all(math.isfinite(value) for value in values):
            return
        # 在受控上下文中安全访问共享资源。
        with self._pose_lock:
            self._latest_http_rpy = values
            self._latest_http_rpy_at = time.monotonic()

    # 线程安全地取得最新位置和姿态快照。
    def _pose_snapshot(self) -> dict[str, Any]:
        # 在受控上下文中安全访问共享资源。
        with self._pose_lock:
            return {
                "pos": (
                    list(self._latest_position)
                    if self._latest_position is not None else None
                ),
                "pos_at": self._latest_position_at,
                "rpy": (
                    list(self._latest_http_rpy)
                    if self._latest_http_rpy is not None else None
                ),
                "rpy_at": self._latest_http_rpy_at,
            }

    # 等待并取得指定时刻之后的新姿态。
    def _pose_after(self, after: float, timeout: float) -> dict[str, Any]:
        """动作归零后等候一帧新位置/IMU，避免使用动作前的旧采样。"""
        initial = self._pose_snapshot()
        need_pos = initial["pos"] is not None
        need_rpy = initial["rpy"] is not None
        # 必要条件或数据不满足时执行安全处理。
        if not need_pos and not need_rpy:
            return initial
        deadline = time.monotonic() + max(0.0, timeout)
        latest = initial
        # 在运行条件成立期间持续执行本段逻辑。
        while self._alive.is_set() and time.monotonic() < deadline:
            latest = self._pose_snapshot()
            pos_ready = not need_pos or latest["pos_at"] > after
            rpy_ready = not need_rpy or latest["rpy_at"] > after
            # 根据当前状态或输入选择对应的处理路径。
            if pos_ready and rpy_ready:
                break
            time.sleep(0.02)
        return latest

    # 生成摇杆方向的简短可视化符号。
    @staticmethod
    def _direction_symbol(axes: dict[str, int]) -> str:
        move_x = int(axes.get("move_x", 0))
        move_y = int(axes.get("move_y", 0))
        turn_x = int(axes.get("turn_x", 0))
        # 根据当前状态或输入选择对应的处理路径。
        if move_y > 0:
            return "↑"
        # 根据当前状态或输入选择对应的处理路径。
        if move_y < 0:
            return "↓"
        # 根据当前状态或输入选择对应的处理路径。
        if move_x < 0:
            return "←"
        # 根据当前状态或输入选择对应的处理路径。
        if move_x > 0:
            return "→"
        # 根据当前状态或输入选择对应的处理路径。
        if turn_x < 0:
            return "↺"
        # 根据当前状态或输入选择对应的处理路径。
        if turn_x > 0:
            return "↻"
        return "■"

    # 把角度规范到统一的度数区间。
    @staticmethod
    def _normalise_degrees(value: float) -> float:
        return (float(value) + 180.0) % 360.0 - 180.0

    # 把角度规范到统一的弧度区间。
    @staticmethod
    def _normalise_radians(value: float) -> float:
        return (float(value) + math.pi) % (2.0 * math.pi) - math.pi

    # 整理单个移动路段失败时的错误信息。
    @classmethod
    def _segment_error_text(
        cls,
        segment_name: str,
        axes: dict[str, int],
        start: dict[str, Any],
        end: dict[str, Any],
    ) -> str | None:
        start_pos, end_pos = start.get("pos"), end.get("pos")
        start_rpy, end_rpy = start.get("rpy"), end.get("rpy")
        yaw_change = None
        # 必要条件或数据不满足时执行安全处理。
        if start_rpy is not None and end_rpy is not None:
            yaw_change = cls._normalise_degrees(
                math.degrees(float(end_rpy[2]) - float(start_rpy[2]))
            )

        # 准备本逻辑段使用的局部数据和中间状态。
        turn_x = int(axes.get("turn_x", 0))
        # 根据当前状态或输入选择对应的处理路径。
        if turn_x:
            parts = []
            # 必要条件或数据不满足时执行安全处理。
            if yaw_change is not None:
                expected_sign = 1 if turn_x < 0 else -1
                direction_ok = yaw_change == 0 or math.copysign(1, yaw_change) == expected_sign
                parts.append(
                    f"实际转角={yaw_change:+.2f}°，方向={'符合' if direction_ok else '相反'}"
                )
            # 必要条件或数据不满足时执行安全处理。
            if start_pos is not None and end_pos is not None:
                dx = float(end_pos[0]) - float(start_pos[0])
                dy = float(end_pos[1]) - float(start_pos[1])
                dz = float(end_pos[2]) - float(start_pos[2])
                parts.append(
                    f"位置漂移误差={math.sqrt(dx * dx + dy * dy + dz * dz):.4f}m"
                )
            return f"{segment_name}: " + "，".join(parts) if parts else None

        # 必要条件或数据不满足时执行安全处理。
        if start_pos is None or end_pos is None:
            return None
        dx = float(end_pos[0]) - float(start_pos[0])
        dy = float(end_pos[1]) - float(start_pos[1])
        dz = float(end_pos[2]) - float(start_pos[2])
        yaw = float(start_rpy[2]) if start_rpy is not None else 0.0
        forward = (math.cos(yaw), math.sin(yaw))
        left = (-math.sin(yaw), math.cos(yaw))
        move_x = int(axes.get("move_x", 0))
        move_y = int(axes.get("move_y", 0))
        # 根据当前状态或输入选择对应的处理路径。
        if move_y:
            intended = forward if move_y > 0 else (-forward[0], -forward[1])
        # 其余情况进入默认的处理路径。
        else:
            intended = left if move_x < 0 else (-left[0], -left[1])
        along = dx * intended[0] + dy * intended[1]
        lateral = abs(-dx * intended[1] + dy * intended[0])
        text = (
            f"{segment_name}: 沿指令位移={along:+.4f}m，"
            f"侧向误差={lateral:.4f}m，高度漂移={dz:+.4f}m"
        )
        # 必要条件或数据不满足时执行安全处理。
        if yaw_change is not None:
            text += f"，偏航漂移={yaw_change:+.2f}°"
        return text

    # 整理动作组失败时的错误信息。
    @classmethod
    def _group_error_text(
        cls,
        cycle: int,
        name: str,
        start: dict[str, Any],
        end: dict[str, Any],
    ) -> str | None:
        parts = []
        start_pos, end_pos = start.get("pos"), end.get("pos")
        # 必要条件或数据不满足时执行安全处理。
        if start_pos is not None and end_pos is not None:
            dx = float(end_pos[0]) - float(start_pos[0])
            dy = float(end_pos[1]) - float(start_pos[1])
            dz = float(end_pos[2]) - float(start_pos[2])
            parts.append(f"平面={math.hypot(dx, dy):.4f}m")
            parts.append(f"3D={math.sqrt(dx * dx + dy * dy + dz * dz):.4f}m")
            parts.append(f"Δ=({dx:+.4f},{dy:+.4f},{dz:+.4f})m")
        start_rpy, end_rpy = start.get("rpy"), end.get("rpy")
        # 必要条件或数据不满足时执行安全处理。
        if start_rpy is not None and end_rpy is not None:
            yaw_error = abs(cls._normalise_degrees(
                math.degrees(float(end_rpy[2]) - float(start_rpy[2]))
            ))
            parts.append(f"偏航={yaw_error:.2f}°")
        # 必要条件或数据不满足时执行安全处理。
        if not parts:
            return None
        return f"第{cycle}组 {name} 回零误差: " + "，".join(parts)

    # 记录带有路段上下文的异常。
    def _log_segment_error(
        self,
        cycle: int,
        segment_name: str,
        axes: dict[str, int],
        start: dict[str, Any],
        end: dict[str, Any],
    ) -> None:
        text = self._segment_error_text(segment_name, axes, start, end)
        # 根据当前状态或输入选择对应的处理路径。
        if text:
            self._log("MEASURE", f"第{cycle}组 {text}")
        # 其余情况进入默认的处理路径。
        else:
            self._log("WARN", f"第{cycle}组 {segment_name}: 无位置/IMU采样，无法计算误差")

    # 记录带有动作组上下文的异常。
    def _log_group_error(
        self,
        cycle: int,
        name: str,
        start: dict[str, Any],
        end: dict[str, Any],
    ) -> None:
        text = self._group_error_text(cycle, name, start, end)
        # 根据当前状态或输入选择对应的处理路径。
        if text:
            self._log("MEASURE", text)
        # 其余情况进入默认的处理路径。
        else:
            self._log("WARN", f"第{cycle}组 {name}: 无位置/IMU采样，无法计算回零误差")

    # 重试发送摇杆归零指令以安全停车。
    def _safe_stop(self, client: MH4HttpClient, attempts: int = 3) -> None:
        """重复下发摇杆归零；失败只记日志，不遮盖原始异常。"""
        last_error: Exception | None = None
        # 逐项处理当前集合中的数据。
        for index in range(max(1, attempts)):
            # 尝试执行可能失败的操作并交由异常分支处理。
            try:
                client.stop_joystick()
                # 根据当前状态或输入选择对应的处理路径。
                if index + 1 < attempts:
                    time.sleep(0.04)
            # 捕获异常并执行日志记录或安全降级。
            except Exception as exc:
                last_error = exc
        # 必要条件或数据不满足时执行安全处理。
        if last_error is not None:
            self._log("ERROR", f"摇杆归零失败: {last_error}")

    # 统一格式化并发送后台日志。
    def _log(self, level: str, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_msg.emit(f"[{timestamp}] [{level}] {message}")
