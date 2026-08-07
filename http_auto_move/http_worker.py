"""MH4 HTTP 自动移动后台线程。"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

from PySide6.QtCore import QThread, Signal

try:
    from .http_client import MH4HttpClient
except ImportError:  # 支持 python3 http_auto_move/main.py
    from http_client import MH4HttpClient


class HttpAutoMoveWorker(QThread):
    """维持 exchange 心跳，并按固定频率重复发送摇杆时序。"""

    connected = Signal(bool, str)
    exchange_data = Signal(dict)
    log_msg = Signal(str)
    progress = Signal(int, int, str, int)
    command_preview = Signal(dict)
    finished_ok = Signal(str)
    emergency_result = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._address = "192.168.1.6:22000"
        self._client_name = "HTTP Auto Move"
        self._connection_type = "AP"
        self._current_client = 1
        self._timeout = 1.5
        self._client: MH4HttpClient | None = None
        self._commands: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._alive = threading.Event()
        self._stop_motion = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def configure(
        self,
        address: str,
        client_name: str,
        connection_type: str,
        timeout: float = 1.5,
    ) -> None:
        if self.isRunning():
            raise RuntimeError("运行中不能修改连接参数")
        self._address = address
        self._client_name = client_name.strip() or "HTTP Auto Move"
        self._connection_type = connection_type
        self._timeout = max(0.1, float(timeout))

    def start_move(self, command: dict[str, Any]) -> None:
        self._commands.put(dict(command))

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
            self._log("HTTP", f"POST {client.control_base}/connection/state")
            client.connect(
                client_name=self._client_name,
                connection_type=self._connection_type,
                current_client=self._current_client,
            )
            initial = client.exchange()
            self.exchange_data.emit(initial)
            self._alive.set()
            self.connected.emit(True, client.control_base)
            self._log("INFO", f"已连接 {client.control_base}，exchange 心跳已启动")
        except Exception as exc:
            self._log("ERROR", f"连接失败: {exc}")
            self.connected.emit(False, str(exc))
            self._client = None
            return

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="mh4-exchange", daemon=True
        )
        self._heartbeat_thread.start()

        try:
            while self._alive.is_set():
                try:
                    command = self._commands.get(timeout=0.2)
                except queue.Empty:
                    continue
                if command is None:
                    break
                self._stop_motion.clear()
                self._execute(command)
        finally:
            self._alive.clear()
            self._stop_motion.set()
            if self._client is not None:
                self._safe_stop(self._client)
            if self._heartbeat_thread is not None:
                self._heartbeat_thread.join(timeout=self._timeout + 0.5)
            self._client = None
            self.connected.emit(False, "连接已关闭")

    def _heartbeat_loop(self) -> None:
        failures = 0
        next_tick = time.monotonic()
        while self._alive.is_set():
            client = self._client
            if client is None:
                break
            try:
                state = client.exchange()
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

    def _execute(self, command: dict[str, Any]) -> None:
        client = self._client
        if client is None:
            self.finished_ok.emit("执行失败：HTTP 客户端未连接")
            return

        axes = {
            "move_x": int(command.get("move_x", 0)),
            "move_y": int(command.get("move_y", 0)),
            "turn_x": int(command.get("turn_x", 0)),
            "turn_y": int(command.get("turn_y", 0)),
        }
        duration = max(0.05, float(command.get("duration", 1.0)))
        repetitions = max(1, int(command.get("repetitions", 1)))
        infinite = bool(command.get("infinite", False))
        settle_time = max(0.0, float(command.get("settle_time", 0.3)))
        rate_hz = max(2.0, min(50.0, float(command.get("rate_hz", 20.0))))
        name = str(command.get("name", "摇杆时序"))

        try:
            if command.get("set_speed_ratio", False):
                ratio = int(command.get("speed_ratio", 50))
                self._log(
                    "HTTP",
                    f"POST {client.algorithm_base}/algs/settings/movement/speedRatio "
                    f"ratio={ratio}",
                )
                client.set_speed_ratio(ratio)

            self._log(
                "INFO",
                f"启动 {name}: {axes}，持续 {duration:.3f}s，"
                f"频率 {rate_hz:.1f}Hz，循环 {'无限' if infinite else repetitions}",
            )
            cycle = 0
            while self._alive.is_set() and not self._stop_motion.is_set():
                cycle += 1
                if not infinite and cycle > repetitions:
                    break
                total = 0 if infinite else repetitions
                self._drive_once(client, name, axes, duration, rate_hz, cycle, total)
                if self._stop_motion.is_set() or not self._alive.is_set():
                    break
                if settle_time and (infinite or cycle < repetitions):
                    self.progress.emit(cycle, total, "稳定等待", 100)
                    if self._stop_motion.wait(settle_time):
                        break

            stopped = self._stop_motion.is_set()
            message = "动作已停止" if stopped else "动作执行完成"
            self.finished_ok.emit(message)
            self._log("INFO", message)
        except Exception as exc:
            self._log("ERROR", f"动作执行失败: {exc}")
            self.finished_ok.emit(f"动作执行失败: {exc}")
        finally:
            self._safe_stop(client)
            self.command_preview.emit({})

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
            percent = min(99, int(elapsed / duration * 100))
            self.progress.emit(cycle, total, name, percent)
            self.command_preview.emit(
                {
                    **axes,
                    "duration": duration,
                    "elapsed": elapsed,
                    "remaining": max(0.0, duration - elapsed),
                }
            )
            next_tick += period
            wait = max(0.0, next_tick - time.monotonic())
            if self._stop_motion.wait(wait):
                break
        self._safe_stop(client)
        self.progress.emit(cycle, total, name, 100)

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
