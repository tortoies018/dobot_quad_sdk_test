"""MH4 HTTP 自动移动后台线程。"""

from __future__ import annotations

import math
import json
import queue
import random
import threading
import time
from typing import Any
from urllib.parse import urlsplit

from PySide6.QtCore import QThread, Signal

try:
    from .http_client import MH4HttpClient
except ImportError:  # 支持 python3 http_auto_move/main.py
    from http_client import MH4HttpClient


class HttpAutoMoveWorker(QThread):
    """维持 exchange 心跳，并按固定频率重复发送摇杆时序。"""

    _POSE_MAX_AGE = 1.0
    _RETURN_POSE_RECOVERY_TIMEOUT = 3.0
    _RETURN_POSE_POLL_INTERVAL = 0.05
    _RETURN_MAX_AMPLITUDE = 8000
    _RETURN_MIN_AMPLITUDE = 500
    _RETURN_SLOW_RADIUS = 0.75

    connected = Signal(bool, str)
    exchange_data = Signal(dict)
    odom_data = Signal(dict)       # gRPC 仅提供位置/速度；姿态始终来自 HTTP IMU
    trajectory_status = Signal(bool, str)
    recovery_command = Signal(object)
    log_msg = Signal(str)
    finished_ok = Signal(str)
    emergency_result = Signal(bool, str)
    manual_api_result = Signal(bool, str, object)

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

    def configure(
        self,
        address: str,
        client_name: str,
        connection_type: str,
        grpc_port: int = 50051,
        timeout: float = 1.5,
    ) -> None:
        if self.isRunning():
            raise RuntimeError("运行中不能修改连接参数")
        self._address = address
        self._client_name = client_name.strip() or "HTTP Auto Move"
        self._connection_type = connection_type
        self._grpc_port = max(1, min(65535, int(grpc_port)))
        self._timeout = max(0.1, float(timeout))
        with self._pose_lock:
            self._latest_position = None
            self._latest_position_at = 0.0
            self._latest_http_rpy = None
            self._latest_http_rpy_at = 0.0

    def start_move(self, command: dict[str, Any]) -> None:
        self._commands.put(dict(command))

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

    def stop_move(self) -> None:
        self._stop_motion.set()

    def shutdown(self) -> None:
        self._alive.clear()
        self._stop_motion.set()
        self._commands.put(None)

    def set_emergency_stop(self, enabled: bool) -> None:
        """独立请求急停，避免长动作阻塞 UI 中的急停操作。"""
        if enabled:
            self._stop_motion.set()

        def send() -> None:
            client = self._client
            if client is None:
                self.emergency_result.emit(False, "尚未连接机器人")
                return
            try:
                if enabled:
                    self._safe_stop(client, attempts=1)
                client.emergency_stop(enabled)
                text = "软急停已触发" if enabled else "软急停已解除"
                self._log("WARN" if enabled else "INFO", text)
                self.emergency_result.emit(True, text)
            except Exception as exc:
                text = f"软急停请求失败: {exc}"
                self._log("ERROR", text)
                self.emergency_result.emit(False, text)

        threading.Thread(target=send, name="mh4-emergency", daemon=True).start()

    def run(self) -> None:
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
        except Exception as exc:
            self._log("ERROR", f"连接失败: {exc}")
            self.connected.emit(False, str(exc))
            self._client = None
            return

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="mh4-exchange", daemon=True
        )
        self._odom_thread = threading.Thread(
            target=self._odom_loop, name="mh4-odom", daemon=True
        )
        self._heartbeat_thread.start()
        self._odom_thread.start()

        try:
            while self._alive.is_set():
                try:
                    command = self._commands.get(timeout=0.2)
                except queue.Empty:
                    continue
                if command is None:
                    break
                if command.get("_kind") == "manual_api":
                    self._execute_manual_api(command)
                    continue
                self._stop_motion.clear()
                self._execute(command)
        finally:
            self._alive.clear()
            self._stop_motion.set()
            if self._client is not None:
                self._safe_stop(self._client)
            if self._heartbeat_thread is not None:
                self._heartbeat_thread.join(timeout=self._timeout + 0.5)
            if self._odom_thread is not None:
                self._odom_thread.join(timeout=2.0)
            self._client = None
            self.connected.emit(False, "连接已关闭")

    def _resolve_connection_type(self, client: MH4HttpClient) -> str:
        """优先采用控制器报告的 AP/Station，避免网线连接被登记为 AP。"""
        requested = self._connection_type
        detected = None
        try:
            detected = client.connection_type()
            self._log("INFO", f"控制器报告连接方式: {detected}")
        except Exception as exc:
            self._log("WARN", f"自动读取连接方式失败: {exc}")

        if detected in ("AP", "Station"):
            if requested not in ("Auto", detected, "4G"):
                self._log(
                    "WARN",
                    f"界面选择 {requested}，控制器实际为 {detected}；自动改用 {detected}",
                )
            if requested != "4G":
                return detected
        if requested in ("AP", "Station", "4G"):
            return requested
        # 无法探测时，根据文档中的固定网口地址回退。
        return "Station" if "192.168.5.2" in self._address else "AP"

    def _heartbeat_loop(self) -> None:
        failures = 0
        next_tick = time.monotonic()
        while self._alive.is_set():
            client = self._client
            if client is None:
                break
            try:
                state = client.exchange()
                self._remember_exchange(state)
                self.exchange_data.emit(state)
                if failures:
                    self._log("INFO", "exchange 心跳已恢复")
                failures = 0
            except Exception as exc:
                failures += 1
                if failures in (1, 3) or failures % 10 == 0:
                    self._log("ERROR", f"exchange 心跳失败({failures}): {exc}")
            next_tick += 0.2  # 5 Hz，远小于文档中的 3 秒占用超时
            # 请求偶尔变慢时不要连续补发积欠的 exchange，避免与摇杆请求争抢
            # 控制器的 HTTP 处理能力，形成“越慢越密集”的反馈循环。
            if next_tick < time.monotonic():
                next_tick = time.monotonic() + 0.2
            wait = max(0.0, next_tick - time.monotonic())
            time.sleep(wait)

    def _odom_loop(self) -> None:
        """以 10 Hz 读取 gRPC 世界坐标；不使用其中的 IMU 姿态。"""
        host = urlsplit(self._client.control_base).hostname if self._client else None
        if not host:
            self.trajectory_status.emit(False, "无法从 HTTP 地址解析 gRPC 主机")
            return
        address = f"{host}:{self._grpc_port}"
        robot = None
        failures = 0
        available = False
        try:
            from dobot_quad import RobotClient
        except Exception as exc:
            self.trajectory_status.emit(False, f"dobot_quad 不可用: {exc}")
            self._log("WARN", f"轨迹采样未启动: {exc}")
            return

        try:
            while self._alive.is_set():
                try:
                    if robot is None:
                        robot = RobotClient(address)
                    state = robot.get_state()
                    if not state or not getattr(state, "success", True):
                        raise RuntimeError("get_state 返回失败")
                    rs = state.robot_state
                    pos = [float(value) for value in rs.pos_body]
                    if len(pos) < 2:
                        raise RuntimeError("pos_body 缺少 x/y")
                    while len(pos) < 3:
                        pos.append(0.0)
                    if not all(math.isfinite(value) for value in pos[:3]):
                        raise RuntimeError("pos_body 含非有限值")
                    vel = [float(value) for value in rs.vel_body]
                    while len(vel) < 3:
                        vel.append(0.0)
                    with self._pose_lock:
                        self._latest_position = pos[:3]
                        self._latest_position_at = time.monotonic()
                    self.odom_data.emit({"pos": pos[:3], "vel": vel[:3]})
                    failures = 0
                    if not available:
                        available = True
                        self.trajectory_status.emit(True, f"gRPC {address} @ 10 Hz")
                        self._log("INFO", f"实际轨迹采样已启动: gRPC {address} @ 10 Hz")
                except Exception as exc:
                    failures += 1
                    if failures in (1, 10) or failures % 50 == 0:
                        self._log("WARN", f"gRPC 轨迹采样失败({failures}): {exc}")
                    if available and failures >= 10:
                        available = False
                        self.trajectory_status.emit(False, f"gRPC 轨迹中断: {exc}")
                    if failures >= 10:
                        robot = None
                time.sleep(0.1)
        finally:
            close = getattr(robot, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            self.trajectory_status.emit(False, "gRPC 轨迹采样已停止")

    def _execute(self, command: dict[str, Any]) -> None:
        if command.get("mode") == "random_patrol":
            self._execute_random_patrol(command)
            return
        client = self._client
        if client is None:
            self.finished_ok.emit("执行失败：HTTP 客户端未连接")
            return

        segments = []
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
        if not segments:
            self.finished_ok.emit("执行失败：动作组为空")
            return
        repetitions = max(1, int(command.get("repetitions", 1)))
        infinite = bool(command.get("infinite", False))
        settle_time = max(0.0, float(command.get("settle_time", 0.3)))
        rate_hz = max(2.0, min(50.0, float(command.get("rate_hz", 10.0))))
        name = str(command.get("name", "摇杆时序"))
        boundary = None

        try:
            boundary = self._validated_boundary(command.get("boundary"))
            prepare_action_id = command.get("prepare_action_id")
            if prepare_action_id is not None:
                self._log(
                    "HTTP",
                    f"POST {client.control_base}/settings/movement/action "
                    f"id={int(prepare_action_id)}",
                )
                client.movement_action(int(prepare_action_id))
                if self._stop_motion.wait(1.0):
                    self.finished_ok.emit("动作已停止")
                    return
            self._log(
                "INFO",
                f"启动 {name}: 每组 {len(segments)} 个方向，频率 {rate_hz:.1f}Hz，"
                f"组数 {'无限' if infinite else repetitions}",
            )
            if boundary is not None:
                center = boundary["center"]
                if boundary.get("kind") == "polygon":
                    self._log(
                        "BOUNDARY",
                        f"多点范围限制已启用: {len(boundary['corners'])} 个边界点，"
                        f"中心=({center[0]:.3f},{center[1]:.3f})m",
                    )
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
            while self._alive.is_set() and not self._stop_motion.is_set():
                cycle += 1
                if not infinite and cycle > repetitions:
                    break
                total = 0 if infinite else repetitions
                group_start = self._pose_snapshot()
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
                    if drive_result == "outside":
                        segment_end = self._pose_snapshot()
                    else:
                        segment_end = self._pose_after(
                            time.monotonic(), timeout=0.35
                        )
                    self._log_segment_error(
                        cycle, segment["name"], segment["axes"],
                        segment_start, segment_end,
                    )
                    if self._stop_motion.is_set() or not self._alive.is_set():
                        break
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
                        if returned != "reached":
                            self._log(
                                "MEASURE",
                                f"第{cycle}组 越界回中心中止: 状态={returned}，"
                                f"中心误差={error_text}",
                            )
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
                    elif drive_result != "completed":
                        if drive_result != "stopped":
                            failure = f"范围限制停止动作（{drive_result}）"
                            self._log("ERROR", failure)
                        break
                    has_more = (
                        index + 1 < len(segments)
                        or infinite
                        or cycle < repetitions
                    )
                    if settle_time and has_more:
                        self._log("CMD", f"… 动作间隔 {settle_time:.1f}s")
                        if self._stop_motion.wait(settle_time):
                            break

                if (
                    not failure
                    and not self._stop_motion.is_set()
                    and self._alive.is_set()
                ):
                    group_end = self._pose_snapshot()
                    self._log_group_error(cycle, name, group_start, group_end)
                if failure:
                    break

            stopped = self._stop_motion.is_set()
            if failure:
                message = f"动作执行失败：{failure}"
            else:
                message = "动作已停止" if stopped else "动作执行完成"
            self.finished_ok.emit(message)
            self._log("ERROR" if failure else "INFO", message)
        except Exception as exc:
            self._log("ERROR", f"动作执行失败: {exc}")
            self.finished_ok.emit(f"动作执行失败: {exc}")
        finally:
            self._safe_stop(client)
            self.recovery_command.emit(None)

    def _execute_random_patrol(self, command: dict[str, Any]) -> None:
        client = self._client
        if client is None:
            self.finished_ok.emit("执行失败：HTTP 客户端未连接")
            return

        failure = ""
        try:
            boundary = self._validated_boundary(command.get("boundary"))
            if boundary is None:
                raise ValueError("随机巡逻必须先设置并启用运动范围")
            speed = max(500, min(32767, int(command.get("speed", 5000))))
            segment_length = max(
                0.1, min(20.0, float(command.get("segment_length", 1.0)))
            )
            yaw_deadband_degrees = max(
                1.0, min(30.0, float(command.get("yaw_deadband", 5.0)))
            )
            repetitions = max(1, int(command.get("repetitions", 1)))
            infinite = bool(command.get("infinite", False))
            settle_time = max(0.0, float(command.get("settle_time", 0.3)))
            safety_margin = 0.15
            position_tolerance = max(0.02, min(0.08, segment_length * 0.10))
            yaw_tolerance = math.radians(yaw_deadband_degrees)

            # 在下发任何动作前验证围栏能否容纳所选安全边距。
            self._inset_boundary_vertices(boundary, safety_margin)
            prepare_action_id = command.get("prepare_action_id")
            if prepare_action_id is not None:
                self._log(
                    "HTTP",
                    f"POST {client.control_base}/settings/movement/action "
                    f"id={int(prepare_action_id)}",
                )
                client.movement_action(int(prepare_action_id))
                if self._stop_motion.wait(1.0):
                    self.finished_ok.emit("动作已停止")
                    return

            self._log(
                "INFO",
                f"启动范围内分段随机巡逻: 路段数="
                f"{'无限' if infinite else repetitions}，速度={speed}，"
                f"每段长度={segment_length:.2f}m，"
                f"偏航死区=±{yaw_deadband_degrees:.1f}°",
            )
            segment = 0
            while self._alive.is_set() and not self._stop_motion.is_set():
                segment += 1
                if not infinite and segment > repetitions:
                    break

                pose_status, pose = self._motion_pose(
                    client, "随机巡逻规划"
                )
                if pose_status != "ready":
                    if pose_status != "stopped":
                        failure = f"随机巡逻规划失败（{pose_status}）"
                    break
                current = pose["pos"]
                if self._boundary_outside(current, boundary):
                    self._log(
                        "WARN",
                        "规划巡逻路段前检测到越界；已归零，插入回中心指令",
                    )
                    returned, center_error = self._return_to_boundary_center(
                        client, boundary, speed
                    )
                    if returned != "reached":
                        if returned != "stopped":
                            failure = (
                                f"随机巡逻越界回中心失败（{returned}，"
                                f"中心误差={center_error:.4f}m）"
                            )
                        break
                    segment -= 1
                    continue

                far_target, far_distance = self._distant_boundary_target(
                    boundary,
                    safety_margin,
                    current_position=current,
                    rng=self._random,
                )
                if far_distance <= position_tolerance:
                    failure = (
                        "安全内缩后的巡逻区域过小，无法生成有效路段；"
                        "请扩大围栏"
                    )
                    break
                total_text = "∞" if infinite else str(repetitions)
                target_yaw = math.atan2(
                    far_target[1] - float(current[1]),
                    far_target[0] - float(current[0]),
                )
                self._log(
                    "PATROL",
                    f"▶ 巡逻路段 {segment}/{total_text}: 远目标="
                    f"({far_target[0]:.3f},{far_target[1]:.3f})m，"
                    f"候选距离={far_distance:.3f}m，"
                    f"目标航向={math.degrees(target_yaw):.1f}°",
                )

                turn_result, yaw_error = self._turn_to_patrol_target(
                    client,
                    boundary,
                    far_target,
                    speed,
                    yaw_tolerance,
                    timeout=20.0,
                )
                self.recovery_command.emit(None)
                if (
                    turn_result == "timeout"
                    and math.isfinite(yaw_error)
                    and abs(yaw_error) > yaw_deadband_degrees
                    and self._alive.is_set()
                    and not self._stop_motion.is_set()
                ):
                    self._log(
                        "WARN",
                        f"巡逻路段 {segment}: 首次转向残差 "
                        f"{yaw_error:+.2f}°，超过死区 "
                        f"±{yaw_deadband_degrees:.1f}°；归零后补转一次",
                    )
                    if self._stop_motion.wait(0.2):
                        break
                    turn_result, yaw_error = self._turn_to_patrol_target(
                        client,
                        boundary,
                        far_target,
                        speed,
                        yaw_tolerance,
                        timeout=20.0,
                    )
                    self.recovery_command.emit(None)
                    if turn_result == "reached":
                        self._log(
                            "MEASURE",
                            f"巡逻路段 {segment} 补转完成: "
                            f"偏航误差={yaw_error:+.2f}°",
                        )
                if turn_result == "outside":
                    self._log(
                        "WARN",
                        "巡逻转向时检测到越界；已归零，插入回中心指令",
                    )
                    returned, center_error = self._return_to_boundary_center(
                        client, boundary, speed
                    )
                    if returned != "reached":
                        if returned != "stopped":
                            failure = (
                                f"随机巡逻越界回中心失败（{returned}，"
                                f"中心误差={center_error:.4f}m）"
                            )
                        break
                    segment -= 1
                    continue
                if turn_result == "stopped":
                    break
                if turn_result != "reached":
                    failure = (
                        f"巡逻路段 {segment} 转向失败"
                        f"（{turn_result}，偏航误差={yaw_error:.2f}°）"
                    )
                    break

                pose_status, pose = self._motion_pose(
                    client, "巡逻路段起点采样"
                )
                if pose_status != "ready":
                    if pose_status != "stopped":
                        failure = f"巡逻路段起点采样失败（{pose_status}）"
                    break
                move_start = pose["pos"]
                dx = far_target[0] - float(move_start[0])
                dy = far_target[1] - float(move_start[1])
                available_distance = math.hypot(dx, dy)
                if available_distance <= position_tolerance:
                    self._log("WARN", "转向后已接近远目标，重新规划本路段")
                    segment -= 1
                    continue
                move_length = min(segment_length, available_distance)
                heading = math.atan2(dy, dx)
                endpoint = [
                    float(move_start[0]) + math.cos(heading) * move_length,
                    float(move_start[1]) + math.sin(heading) * move_length,
                    float(move_start[2]),
                ]
                if move_length + 1e-6 < segment_length:
                    self._log(
                        "WARN",
                        f"巡逻路段 {segment}: 围栏内可用直线距离仅 "
                        f"{move_length:.3f}m，本段由 {segment_length:.3f}m "
                        "安全缩短",
                    )
                move_timeout = min(
                    600.0,
                    max(10.0, move_length * 60000.0 / float(speed)),
                )
                move_result, traveled, endpoint_error = self._drive_patrol_segment(
                    client,
                    boundary,
                    move_start,
                    endpoint,
                    speed,
                    position_tolerance,
                    move_timeout,
                )
                if move_result == "outside":
                    self._log(
                        "WARN",
                        "巡逻前进时检测到越界；已归零，插入回中心指令",
                    )
                    returned, center_error = self._return_to_boundary_center(
                        client, boundary, speed
                    )
                    if returned != "reached":
                        if returned != "stopped":
                            failure = (
                                f"随机巡逻越界回中心失败（{returned}，"
                                f"中心误差={center_error:.4f}m）"
                            )
                        break
                    segment -= 1
                    continue
                if move_result == "stopped":
                    break
                if move_result != "reached":
                    failure = (
                        f"巡逻路段 {segment} 前进失败（{move_result}，"
                        f"已移动={traveled:.3f}m）"
                    )
                    break
                self._log(
                    "MEASURE",
                    f"巡逻路段 {segment} 完成: 设定={move_length:.3f}m，"
                    f"实际平移={traveled:.3f}m，终点误差={endpoint_error:.3f}m",
                )

                has_more = infinite or segment < repetitions
                if settle_time and has_more:
                    self._log("PATROL", f"… 路段间停留 {settle_time:.1f}s")
                    if self._stop_motion.wait(settle_time):
                        break

            stopped = self._stop_motion.is_set() or not self._alive.is_set()
            if failure:
                message = f"动作执行失败：{failure}"
            else:
                message = "动作已停止" if stopped else "随机巡逻完成"
            self.finished_ok.emit(message)
            self._log("ERROR" if failure else "INFO", message)
        except Exception as exc:
            self._log("ERROR", f"随机巡逻失败: {exc}")
            self.finished_ok.emit(f"随机巡逻失败: {exc}")
        finally:
            self._safe_stop(client)
            self.recovery_command.emit(None)

    def _execute_manual_api(self, command: dict[str, Any]) -> None:
        """在后台执行控制台请求，避免 HTTP 超时阻塞 Qt 界面。"""
        current = self._client
        if current is None:
            self.manual_api_result.emit(False, "尚未连接机器人", {})
            return
        method = str(command.get("method", "GET")).upper()
        path = str(command.get("path", "/"))
        port = max(1, min(65535, int(command.get("port", 22000))))
        payload = command.get("payload")
        try:
            parsed = urlsplit(current.control_base)
            host = parsed.hostname
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
            if (
                method == "POST"
                and path.split("?", 1)[0]
                == "/settings/movement/joystickControl"
                and isinstance(payload, dict)
            ):
                payload = dict(payload)
                payload["timestamp"] = int(time.time() * 1000)

            safe_payload = self._redact_payload(payload)
            payload_text = (
                ""
                if payload is None
                else " body=" + json.dumps(safe_payload, ensure_ascii=False)
            )
            self._log("API", f"{method} {base}{path}{payload_text}")
            if (
                method == "POST"
                and path.split("?", 1)[0] == "/upload/formdata/audio"
            ):
                if not isinstance(payload, dict):
                    raise ValueError("音频上传缺少表单参数")
                result = client.upload_audio_file(payload)
            else:
                result = client.raw_request(method, path, payload)
            rejected = isinstance(result, dict) and result.get("status") is False
            result_preview = json.dumps(
                self._redact_payload(result), ensure_ascii=False, default=str
            )
            if len(result_preview) > 1200:
                result_preview = result_preview[:1200] + "…"
            self._log("WARN" if rejected else "API", f"响应: {result_preview}")
            self.manual_api_result.emit(not rejected, f"{method} {base}{path}", result)
        except Exception as exc:
            self._log("ERROR", f"手动接口请求失败: {method} :{port}{path}: {exc}")
            self.manual_api_result.emit(False, f"{method} :{port}{path}: {exc}", {})

    @classmethod
    def _redact_payload(cls, value: Any) -> Any:
        """日志中隐藏密码和图传令牌，实际 HTTP 请求仍使用原值。"""
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {"passwd", "password", "publishertoken", "token"}:
                    redacted[key] = "***"
                else:
                    redacted[key] = cls._redact_payload(item)
            return redacted
        if isinstance(value, list):
            return [cls._redact_payload(item) for item in value]
        return value

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
    ) -> tuple[str, float]:
        started = time.monotonic()
        period = 1.0 / rate_hz
        next_tick = started
        center_error = float("inf")
        while self._alive.is_set() and not self._stop_motion.is_set():
            if boundary is not None:
                pose = self._pose_snapshot()
                position = pose.get("pos")
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
                if self._boundary_outside(position, boundary):
                    self._safe_stop(client)
                    return "outside", center_error
            elapsed = time.monotonic() - started
            if elapsed >= duration:
                break
            client.joystick(**axes)
            next_tick += period
            wait = max(0.0, next_tick - time.monotonic())
            if self._stop_motion.wait(wait):
                break
        self._safe_stop(client)
        if self._stop_motion.is_set() or not self._alive.is_set():
            return "stopped", center_error
        return "completed", center_error

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

    @staticmethod
    def _convex_hull(points: list[list[float]]) -> list[list[float]]:
        """返回按逆时针排列的 XY 凸包，忽略相同 XY 的重复点。"""
        unique: dict[tuple[float, float], list[float]] = {}
        for point in points:
            unique[(float(point[0]), float(point[1]))] = [
                float(point[0]), float(point[1]), float(point[2])
            ]
        ordered = [unique[key] for key in sorted(unique)]
        if len(ordered) < 3:
            raise ValueError("多点范围至少需要 3 个不同位置")

        def cross(
            origin: list[float], first: list[float], second: list[float]
        ) -> float:
            return (
                (first[0] - origin[0]) * (second[1] - origin[1])
                - (first[1] - origin[1]) * (second[0] - origin[0])
            )

        lower: list[list[float]] = []
        for point in ordered:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
                lower.pop()
            lower.append(point)
        upper: list[list[float]] = []
        for point in reversed(ordered):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
                upper.pop()
            upper.append(point)
        hull = lower[:-1] + upper[:-1]
        if len(hull) < 3:
            raise ValueError("多点范围的标点不能全部位于同一直线")
        return hull

    @classmethod
    def _polygon_boundary_geometry(
        cls, points: list[list[float]]
    ) -> dict[str, Any]:
        if not isinstance(points, (list, tuple)) or not 3 <= len(points) <= 100:
            raise ValueError("多点范围需要 3～100 个位置点")
        values: list[list[float]] = []
        try:
            for point in points:
                if not isinstance(point, (list, tuple)) or len(point) < 3:
                    raise ValueError("多点范围含无效位置点")
                value = [float(item) for item in point[:3]]
                if not all(math.isfinite(item) for item in value):
                    raise ValueError("多点范围含非有限数值")
                values.append(value)
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("多点范围"):
                raise
            raise ValueError("多点范围含无效位置点") from exc

        hull = cls._convex_hull(values)
        twice_area = 0.0
        centroid_x = 0.0
        centroid_y = 0.0
        for start, end in zip(hull, hull[1:] + hull[:1]):
            edge_cross = start[0] * end[1] - end[0] * start[1]
            twice_area += edge_cross
            centroid_x += (start[0] + end[0]) * edge_cross
            centroid_y += (start[1] + end[1]) * edge_cross
        area = abs(twice_area) / 2.0
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

    @staticmethod
    def _inset_boundary_vertices(
        boundary: dict[str, Any], margin: float
    ) -> list[list[float]]:
        """按中心等比内缩凸围栏，使每条边至少留出指定距离。"""
        center = boundary["center"]
        corners = boundary["corners"]
        if len(corners) < 3:
            raise ValueError("运动范围至少需要 3 个边界点")
        minimum_edge_distance = float("inf")
        for start, end in zip(corners, corners[1:] + corners[:1]):
            edge_x = float(end[0]) - float(start[0])
            edge_y = float(end[1]) - float(start[1])
            edge_length = math.hypot(edge_x, edge_y)
            if edge_length <= 1e-9:
                raise ValueError("运动范围含重复边界点")
            center_cross = abs(
                edge_x * (float(center[1]) - float(start[1]))
                - edge_y * (float(center[0]) - float(start[0]))
            )
            minimum_edge_distance = min(
                minimum_edge_distance, center_cross / edge_length
            )
        margin = max(0.0, float(margin))
        if minimum_edge_distance <= margin + 1e-6:
            raise ValueError(
                f"巡逻安全边距 {margin:.2f}m 过大；当前范围中心到最近边界"
                f"仅 {minimum_edge_distance:.2f}m"
            )
        scale = 1.0 - margin / minimum_edge_distance
        return [[
            float(center[0]) + (float(point[0]) - float(center[0])) * scale,
            float(center[1]) + (float(point[1]) - float(center[1])) * scale,
            float(center[2]),
        ] for point in corners]

    @classmethod
    def _random_boundary_target(
        cls,
        boundary: dict[str, Any],
        margin: float,
        *,
        current_position: list[float] | tuple[float, ...] | None = None,
        minimum_distance: float = 0.0,
        rng: Any = random,
    ) -> list[float]:
        """在内缩后的凸围栏中按面积均匀抽取随机目标点。"""
        vertices = cls._inset_boundary_vertices(boundary, margin)
        center = [float(value) for value in boundary["center"][:3]]
        triangles: list[tuple[list[float], list[float], float]] = []
        total_area = 0.0
        for start, end in zip(vertices, vertices[1:] + vertices[:1]):
            area = abs(
                (start[0] - center[0]) * (end[1] - center[1])
                - (start[1] - center[1]) * (end[0] - center[0])
            ) / 2.0
            if area <= 1e-12:
                continue
            total_area += area
            triangles.append((start, end, total_area))
        if not triangles or total_area <= 1e-12:
            raise ValueError("巡逻范围内缩后没有可用面积")

        target = center
        for _attempt in range(20):
            selected = rng.random() * total_area
            start, end, _limit = triangles[-1]
            for candidate_start, candidate_end, limit in triangles:
                if selected <= limit:
                    start, end = candidate_start, candidate_end
                    break
            radial = math.sqrt(rng.random())
            along = rng.random()
            target = [
                (1.0 - radial) * center[0]
                + radial * (1.0 - along) * start[0]
                + radial * along * end[0],
                (1.0 - radial) * center[1]
                + radial * (1.0 - along) * start[1]
                + radial * along * end[1],
                center[2],
            ]
            if (
                current_position is None
                or math.hypot(
                    target[0] - float(current_position[0]),
                    target[1] - float(current_position[1]),
                ) >= max(0.0, float(minimum_distance))
            ):
                break
        return target

    @classmethod
    def _distant_boundary_target(
        cls,
        boundary: dict[str, Any],
        margin: float,
        *,
        current_position: list[float] | tuple[float, ...],
        rng: Any = random,
        candidate_count: int = 64,
    ) -> tuple[list[float], float]:
        """从多组随机候选中选择距当前位置最远的围栏内目标。"""
        count = max(8, min(256, int(candidate_count)))
        best_target: list[float] | None = None
        best_distance = -1.0
        for _index in range(count):
            target = cls._random_boundary_target(boundary, margin, rng=rng)
            distance = math.hypot(
                target[0] - float(current_position[0]),
                target[1] - float(current_position[1]),
            )
            if distance > best_distance:
                best_target = target
                best_distance = distance
        if best_target is None:
            raise ValueError("无法生成巡逻远目标")
        return best_target, best_distance

    @classmethod
    def _validated_boundary(cls, raw: Any) -> dict[str, Any] | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("运动范围参数格式错误")
        if raw.get("kind") == "polygon":
            return cls._polygon_boundary_geometry(raw.get("corners"))
        center = raw.get("center")
        if not isinstance(center, (list, tuple)) or len(center) < 3:
            raise ValueError("运动范围缺少中心坐标")
        try:
            center_values = [float(value) for value in center[:3]]
            length = float(raw.get("length"))
            width = float(raw.get("width"))
            yaw = float(raw.get("yaw"))
        except (TypeError, ValueError) as exc:
            raise ValueError("运动范围含无效数值") from exc
        if not all(math.isfinite(value) for value in (*center_values, length, width, yaw)):
            raise ValueError("运动范围含非有限数值")
        if not 0.4 <= length <= 50.0 or not 0.4 <= width <= 50.0:
            raise ValueError("运动范围长宽必须在 0.4～50 m 内")
        return cls._boundary_geometry(center_values, length, width, yaw)

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

    @classmethod
    def _boundary_outside(
        cls, position: list[float], boundary: dict[str, Any]
    ) -> bool:
        if boundary.get("kind") == "polygon":
            x = float(position[0])
            y = float(position[1])
            corners = boundary["corners"]
            for start, end in zip(corners, corners[1:] + corners[:1]):
                edge_cross = (
                    (float(end[0]) - float(start[0]))
                    * (y - float(start[1]))
                    - (float(end[1]) - float(start[1]))
                    * (x - float(start[0]))
                )
                if edge_cross < -1e-9:
                    return True
            return False
        forward, left = cls._boundary_local_position(position, boundary)
        return (
            abs(forward) > float(boundary["length"]) / 2.0
            or abs(left) > float(boundary["width"]) / 2.0
        )

    def _return_to_boundary_center(
        self,
        client: MH4HttpClient,
        boundary: dict[str, Any],
        amplitude: int,
    ) -> tuple[str, float]:
        tolerance = max(
            0.05,
            min(0.15, min(boundary["length"], boundary["width"]) * 0.08),
        )
        timeout = max(8.0, max(boundary["length"], boundary["width"]) * 12.0)
        recovery_amplitude = max(
            self._RETURN_MIN_AMPLITUDE,
            min(self._RETURN_MAX_AMPLITUDE, int(amplitude)),
        )
        try:
            result, error = self._drive_to_boundary_center(
                client, boundary, recovery_amplitude, tolerance, timeout
            )
            relaxed_tolerance = min(
                0.20, max(tolerance + 0.03, tolerance * 1.25)
            )
            if result == "timeout" and error <= relaxed_tolerance:
                self._log(
                    "WARN",
                    f"回中心已进入近中心缓冲区: 误差={error:.4f}m，"
                    f"严格容差={tolerance:.4f}m，按完成处理",
                )
                return "reached", error
            return result, error
        finally:
            self.recovery_command.emit(None)

    def _drive_to_boundary_center(
        self,
        client: MH4HttpClient,
        boundary: dict[str, Any],
        amplitude: int,
        tolerance: float,
        timeout: float,
    ) -> tuple[str, float]:
        return self._drive_to_world_target(
            client,
            boundary["center"],
            amplitude,
            tolerance,
            timeout,
            motion_label="回中心",
        )

    def _motion_pose(
        self,
        client: MH4HttpClient,
        motion_label: str,
    ) -> tuple[str, dict[str, Any]]:
        pose = self._pose_snapshot()
        now = time.monotonic()
        unavailable = self._return_pose_unavailable(pose, now)
        if unavailable is None:
            return "ready", pose
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
        if recovered_at is None:
            if self._stop_motion.is_set() or not self._alive.is_set():
                return "stopped", pose
            return status, pose
        self._log(
            "INFO",
            f"{motion_label}数据已恢复，暂停 {recovered_at - now:.2f}s 后继续",
        )
        return "ready", self._pose_snapshot()

    def _turn_to_patrol_target(
        self,
        client: MH4HttpClient,
        boundary: dict[str, Any],
        target: list[float],
        speed: int,
        tolerance: float,
        timeout: float,
    ) -> tuple[str, float]:
        started = time.monotonic()
        last_error = float("inf")
        while self._alive.is_set() and not self._stop_motion.is_set():
            pose_status, pose = self._motion_pose(client, "巡逻转向")
            if pose_status != "ready":
                return pose_status, last_error
            position = pose["pos"]
            if self._boundary_outside(position, boundary):
                self._safe_stop(client)
                return "outside", last_error
            dx = float(target[0]) - float(position[0])
            dy = float(target[1]) - float(position[1])
            if math.hypot(dx, dy) <= 1e-6:
                self._safe_stop(client)
                return "reached", 0.0
            target_yaw = math.atan2(dy, dx)
            current_yaw = float(pose["rpy"][2])
            yaw_error = self._normalise_radians(target_yaw - current_yaw)
            last_error = math.degrees(yaw_error)
            self.recovery_command.emit({
                "current": list(position[:3]),
                "target": list(target[:3]),
                "current_yaw": math.degrees(current_yaw),
                "target_yaw": math.degrees(target_yaw),
                "phase": "turn",
            })
            if abs(yaw_error) <= tolerance:
                self._safe_stop(client)
                return "reached", last_error
            if time.monotonic() - started >= timeout:
                self._safe_stop(client)
                return "timeout", last_error
            speed_scale = min(1.0, abs(yaw_error) / math.radians(30.0))
            minimum = min(int(speed), 800)
            output = max(minimum, int(int(speed) * speed_scale))
            # 实机标定：turn_x 负值左转（yaw 增大），正值右转。
            turn_x = -output if yaw_error > 0.0 else output
            client.joystick(
                move_x=0, move_y=0, turn_x=turn_x, turn_y=0
            )
            if self._stop_motion.wait(0.1):
                break
        self._safe_stop(client)
        return "stopped", last_error

    def _drive_patrol_segment(
        self,
        client: MH4HttpClient,
        boundary: dict[str, Any],
        start: list[float],
        endpoint: list[float],
        speed: int,
        tolerance: float,
        timeout: float,
    ) -> tuple[str, float, float]:
        dx = float(endpoint[0]) - float(start[0])
        dy = float(endpoint[1]) - float(start[1])
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return "reached", 0.0, 0.0
        unit_x = dx / length
        unit_y = dy / length
        target_yaw = math.atan2(dy, dx)
        started = time.monotonic()
        traveled = 0.0
        endpoint_error = length
        try:
            while self._alive.is_set() and not self._stop_motion.is_set():
                pose_status, pose = self._motion_pose(client, "巡逻前进")
                if pose_status != "ready":
                    return pose_status, traveled, endpoint_error
                position = pose["pos"]
                if self._boundary_outside(position, boundary):
                    self._safe_stop(client)
                    return "outside", traveled, endpoint_error
                from_start_x = float(position[0]) - float(start[0])
                from_start_y = float(position[1]) - float(start[1])
                traveled = math.hypot(from_start_x, from_start_y)
                forward_progress = from_start_x * unit_x + from_start_y * unit_y
                endpoint_error = math.hypot(
                    float(endpoint[0]) - float(position[0]),
                    float(endpoint[1]) - float(position[1]),
                )
                if (
                    endpoint_error <= tolerance
                    or forward_progress >= length - tolerance
                ):
                    self._safe_stop(client)
                    return "reached", traveled, endpoint_error
                if time.monotonic() - started >= timeout:
                    self._safe_stop(client)
                    return "timeout", traveled, endpoint_error

                current_yaw = float(pose["rpy"][2])
                yaw_error = self._normalise_radians(target_yaw - current_yaw)
                remaining = max(0.0, length - forward_progress)
                move_scale = min(1.0, remaining / 0.30)
                move_minimum = min(int(speed), 1000)
                move_y = max(move_minimum, int(int(speed) * move_scale))
                turn_x = 0
                if abs(yaw_error) > math.radians(2.0):
                    turn_limit = max(500, min(4000, int(speed) // 2))
                    turn_scale = min(1.0, abs(yaw_error) / math.radians(20.0))
                    correction = max(300, int(turn_limit * turn_scale))
                    turn_x = -correction if yaw_error > 0.0 else correction
                self.recovery_command.emit({
                    "current": list(position[:3]),
                    "target": list(endpoint[:3]),
                    "current_yaw": math.degrees(current_yaw),
                    "target_yaw": math.degrees(target_yaw),
                    "phase": "move",
                })
                client.joystick(
                    move_x=0,
                    move_y=move_y,
                    turn_x=turn_x,
                    turn_y=0,
                )
                if self._stop_motion.wait(0.1):
                    break
            self._safe_stop(client)
            return "stopped", traveled, endpoint_error
        finally:
            self.recovery_command.emit(None)

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
    ) -> tuple[str, float]:
        started = time.monotonic()
        last_error = float("inf")
        while self._alive.is_set() and not self._stop_motion.is_set():
            pose = self._pose_snapshot()
            now = time.monotonic()
            position = pose.get("pos")
            if self._valid_pose_vector(position):
                last_error = math.hypot(
                    float(target[0]) - float(position[0]),
                    float(target[1]) - float(position[1]),
                )

            unavailable = self._return_pose_unavailable(pose, now)
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
                if recovered_at is None:
                    if self._stop_motion.is_set() or not self._alive.is_set():
                        return "stopped", last_error
                    return status, last_error
                self._log(
                    "INFO",
                    f"{motion_label}数据已恢复，"
                    f"暂停 {recovered_at - now:.2f}s 后继续",
                )
                continue

            position = pose["pos"]
            rpy = pose["rpy"]
            dx = float(target[0]) - float(position[0])
            dy = float(target[1]) - float(position[1])
            last_error = math.hypot(dx, dy)
            if boundary is not None and self._boundary_outside(position, boundary):
                self._safe_stop(client)
                return "outside", last_error
            if last_error <= tolerance:
                self._safe_stop(client)
                return "reached", last_error
            if now - started >= timeout:
                self._safe_stop(client)
                return "timeout", last_error
            yaw = float(rpy[2])
            self.recovery_command.emit({
                "current": list(position[:3]),
                "target": list(target[:3]),
                "current_yaw": math.degrees(yaw),
                "target_yaw": math.degrees(yaw),
                "phase": "move",
            })
            client.joystick(**self._axes_to_world_target(
                position, target, yaw, amplitude, tolerance
            ))
            if self._stop_motion.wait(0.1):
                break
        self._safe_stop(client)
        return "stopped", last_error

    @staticmethod
    def _valid_pose_vector(value: Any) -> bool:
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            return False
        try:
            return all(math.isfinite(float(item)) for item in value[:3])
        except (TypeError, ValueError):
            return False

    @classmethod
    def _return_pose_unavailable(
        cls, pose: dict[str, Any], now: float
    ) -> tuple[str, str] | None:
        position = pose.get("pos")
        if not cls._valid_pose_vector(position):
            return "position_unavailable", "gRPC 位置不可用"
        position_age = max(0.0, now - float(pose.get("pos_at", 0.0)))
        if position_age > cls._POSE_MAX_AGE:
            return (
                "position_unavailable",
                f"gRPC 位置已 {position_age:.2f}s 未更新",
            )

        rpy = pose.get("rpy")
        if not cls._valid_pose_vector(rpy):
            return "imu_unavailable", "HTTP IMU 不可用"
        rpy_age = max(0.0, now - float(pose.get("rpy_at", 0.0)))
        if rpy_age > cls._POSE_MAX_AGE:
            return "imu_unavailable", f"HTTP IMU 已 {rpy_age:.2f}s 未更新"
        return None

    def _wait_for_pose_recovery(self, timeout: float) -> float | None:
        deadline = time.monotonic() + max(0.0, float(timeout))
        while self._alive.is_set() and not self._stop_motion.is_set():
            now = time.monotonic()
            if self._return_pose_unavailable(self._pose_snapshot(), now) is None:
                return now
            remaining = deadline - now
            if remaining <= 0.0:
                break
            if self._stop_motion.wait(
                min(self._RETURN_POSE_POLL_INTERVAL, remaining)
            ):
                break
        return None

    @staticmethod
    def _axes_to_world_target(
        position: list[float],
        target: list[float],
        yaw: float,
        amplitude: int,
        tolerance: float,
    ) -> dict[str, int]:
        dx = float(target[0]) - float(position[0])
        dy = float(target[1]) - float(position[1])
        forward_error = math.cos(yaw) * dx + math.sin(yaw) * dy
        left_error = -math.sin(yaw) * dx + math.cos(yaw) * dy
        scale = max(abs(forward_error), abs(left_error), 1e-9)
        distance = math.hypot(dx, dy)
        slow_radius = max(
            HttpAutoMoveWorker._RETURN_SLOW_RADIUS, tolerance * 4.0
        )
        speed_scale = min(1.0, distance / slow_radius)
        minimum = min(
            int(amplitude), HttpAutoMoveWorker._RETURN_MIN_AMPLITUDE
        )
        output = max(minimum, int(int(amplitude) * speed_scale))
        return {
            "move_x": int(round(-output * left_error / scale)),
            "move_y": int(round(output * forward_error / scale)),
            "turn_x": 0,
            "turn_y": 0,
        }

    def _remember_exchange(self, data: dict[str, Any]) -> None:
        """保存 HTTP IMU，供误差计算和指令可视化使用。"""
        imu = data.get("imu") if isinstance(data.get("imu"), dict) else {}
        rpy = imu.get("rpy")
        if not isinstance(rpy, (list, tuple)) or len(rpy) < 3:
            return
        try:
            values = [float(value) for value in rpy[:3]]
        except (TypeError, ValueError):
            return
        if not all(math.isfinite(value) for value in values):
            return
        with self._pose_lock:
            self._latest_http_rpy = values
            self._latest_http_rpy_at = time.monotonic()

    def _pose_snapshot(self) -> dict[str, Any]:
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

    def _pose_after(self, after: float, timeout: float) -> dict[str, Any]:
        """动作归零后等候一帧新位置/IMU，避免使用动作前的旧采样。"""
        initial = self._pose_snapshot()
        need_pos = initial["pos"] is not None
        need_rpy = initial["rpy"] is not None
        if not need_pos and not need_rpy:
            return initial
        deadline = time.monotonic() + max(0.0, timeout)
        latest = initial
        while self._alive.is_set() and time.monotonic() < deadline:
            latest = self._pose_snapshot()
            pos_ready = not need_pos or latest["pos_at"] > after
            rpy_ready = not need_rpy or latest["rpy_at"] > after
            if pos_ready and rpy_ready:
                break
            time.sleep(0.02)
        return latest

    @staticmethod
    def _direction_symbol(axes: dict[str, int]) -> str:
        move_x = int(axes.get("move_x", 0))
        move_y = int(axes.get("move_y", 0))
        turn_x = int(axes.get("turn_x", 0))
        if move_y > 0:
            return "↑"
        if move_y < 0:
            return "↓"
        if move_x < 0:
            return "←"
        if move_x > 0:
            return "→"
        if turn_x < 0:
            return "↺"
        if turn_x > 0:
            return "↻"
        return "■"

    @staticmethod
    def _normalise_degrees(value: float) -> float:
        return (float(value) + 180.0) % 360.0 - 180.0

    @staticmethod
    def _normalise_radians(value: float) -> float:
        return (float(value) + math.pi) % (2.0 * math.pi) - math.pi

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
        if start_rpy is not None and end_rpy is not None:
            yaw_change = cls._normalise_degrees(
                math.degrees(float(end_rpy[2]) - float(start_rpy[2]))
            )

        turn_x = int(axes.get("turn_x", 0))
        if turn_x:
            parts = []
            if yaw_change is not None:
                expected_sign = 1 if turn_x < 0 else -1
                direction_ok = yaw_change == 0 or math.copysign(1, yaw_change) == expected_sign
                parts.append(
                    f"实际转角={yaw_change:+.2f}°，方向={'符合' if direction_ok else '相反'}"
                )
            if start_pos is not None and end_pos is not None:
                dx = float(end_pos[0]) - float(start_pos[0])
                dy = float(end_pos[1]) - float(start_pos[1])
                dz = float(end_pos[2]) - float(start_pos[2])
                parts.append(
                    f"位置漂移误差={math.sqrt(dx * dx + dy * dy + dz * dz):.4f}m"
                )
            return f"{segment_name}: " + "，".join(parts) if parts else None

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
        if move_y:
            intended = forward if move_y > 0 else (-forward[0], -forward[1])
        else:
            intended = left if move_x < 0 else (-left[0], -left[1])
        along = dx * intended[0] + dy * intended[1]
        lateral = abs(-dx * intended[1] + dy * intended[0])
        text = (
            f"{segment_name}: 沿指令位移={along:+.4f}m，"
            f"侧向误差={lateral:.4f}m，高度漂移={dz:+.4f}m"
        )
        if yaw_change is not None:
            text += f"，偏航漂移={yaw_change:+.2f}°"
        return text

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
        if start_pos is not None and end_pos is not None:
            dx = float(end_pos[0]) - float(start_pos[0])
            dy = float(end_pos[1]) - float(start_pos[1])
            dz = float(end_pos[2]) - float(start_pos[2])
            parts.append(f"平面={math.hypot(dx, dy):.4f}m")
            parts.append(f"3D={math.sqrt(dx * dx + dy * dy + dz * dz):.4f}m")
            parts.append(f"Δ=({dx:+.4f},{dy:+.4f},{dz:+.4f})m")
        start_rpy, end_rpy = start.get("rpy"), end.get("rpy")
        if start_rpy is not None and end_rpy is not None:
            yaw_error = abs(cls._normalise_degrees(
                math.degrees(float(end_rpy[2]) - float(start_rpy[2]))
            ))
            parts.append(f"偏航={yaw_error:.2f}°")
        if not parts:
            return None
        return f"第{cycle}组 {name} 回零误差: " + "，".join(parts)

    def _log_segment_error(
        self,
        cycle: int,
        segment_name: str,
        axes: dict[str, int],
        start: dict[str, Any],
        end: dict[str, Any],
    ) -> None:
        text = self._segment_error_text(segment_name, axes, start, end)
        if text:
            self._log("MEASURE", f"第{cycle}组 {text}")
        else:
            self._log("WARN", f"第{cycle}组 {segment_name}: 无位置/IMU采样，无法计算误差")

    def _log_group_error(
        self,
        cycle: int,
        name: str,
        start: dict[str, Any],
        end: dict[str, Any],
    ) -> None:
        text = self._group_error_text(cycle, name, start, end)
        if text:
            self._log("MEASURE", text)
        else:
            self._log("WARN", f"第{cycle}组 {name}: 无位置/IMU采样，无法计算回零误差")

    def _safe_stop(self, client: MH4HttpClient, attempts: int = 3) -> None:
        """重复下发摇杆归零；失败只记日志，不遮盖原始异常。"""
        last_error: Exception | None = None
        for index in range(max(1, attempts)):
            try:
                client.stop_joystick()
                if index + 1 < attempts:
                    time.sleep(0.04)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            self._log("ERROR", f"摇杆归零失败: {last_error}")

    def _log(self, level: str, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_msg.emit(f"[{timestamp}] [{level}] {message}")
