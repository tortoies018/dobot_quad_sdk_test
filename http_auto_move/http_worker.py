"""MH4 HTTP 自动移动后台线程。"""

from __future__ import annotations

import math
import json
import queue
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

    connected = Signal(bool, str)
    exchange_data = Signal(dict)
    odom_data = Signal(dict)       # gRPC 仅提供位置/速度；姿态始终来自 HTTP IMU
    trajectory_status = Signal(bool, str)
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

        try:
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
            cycle = 0
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
                    self._drive_once(
                        client,
                        stage,
                        segment["axes"],
                        segment["duration"],
                        rate_hz,
                        cycle,
                        total,
                    )
                    self._log(
                        "CMD", f"■ 第{cycle}组 {segment['name']}结束，摇杆已归零"
                    )
                    segment_end = self._pose_after(time.monotonic(), timeout=0.35)
                    self._log_segment_error(
                        cycle, segment["name"], segment["axes"],
                        segment_start, segment_end,
                    )
                    if self._stop_motion.is_set() or not self._alive.is_set():
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

                if not self._stop_motion.is_set() and self._alive.is_set():
                    group_end = self._pose_snapshot()
                    self._log_group_error(cycle, name, group_start, group_end)

            stopped = self._stop_motion.is_set()
            message = "动作已停止" if stopped else "动作执行完成"
            self.finished_ok.emit(message)
            self._log("INFO", message)
        except Exception as exc:
            self._log("ERROR", f"动作执行失败: {exc}")
            self.finished_ok.emit(f"动作执行失败: {exc}")
        finally:
            self._safe_stop(client)

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
    ) -> None:
        started = time.monotonic()
        period = 1.0 / rate_hz
        next_tick = started
        while self._alive.is_set() and not self._stop_motion.is_set():
            elapsed = time.monotonic() - started
            if elapsed >= duration:
                break
            client.joystick(**axes)
            next_tick += period
            wait = max(0.0, next_tick - time.monotonic())
            if self._stop_motion.wait(wait):
                break
        self._safe_stop(client)

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
