"""gRPC 指令工作线程——连接机器狗并执行命令"""

import time
from PySide6.QtCore import QThread, Signal

from dobot_quad import RobotClient


class RobotWorker(QThread):
    """后台线程：维护 RobotClient 连接，执行指令并轮询状态"""

    status_updated = Signal(str, str, int, bool, str, dict)  # robot_type, fsm, speed, avoid, info, telemetry
    command_result = Signal(str)
    connected = Signal(bool)
    log = Signal(str)

    def __init__(self, addr="192.168.1.6:50051", parent=None):
        super().__init__(parent)
        self._addr = addr
        self._robot = None
        self._running = True
        self._cmd_queue = []

    def run(self):
        try:
            self._robot = RobotClient(self._addr)
            self.connected.emit(True)
            self.log.emit(f"已连接 {self._addr}")
        except Exception as e:
            self.log.emit(f"连接失败: {e}")
            self.connected.emit(False)
            return

        while self._running:
            try:
                state = self._robot.get_state()
                rt = self._robot.get_robot_type()

                rs = state.robot_state
                pos = list(rs.pos_body) if rs.pos_body else []
                tele = f"位置:[{pos[0]:.2f},{pos[1]:.2f},{pos[2]:.2f}]" if len(pos)>=3 else ""

                self.status_updated.emit(
                    rt, state.current_state, state.current_speed_ratio,
                    state.obstacle_avoidance_enabled, f"轮询 OK", tele
                )
            except Exception as e:
                self.log.emit(f"轮询失败: {e}")

            time.sleep(0.5)

    def _exec(self, cmd, *args, **kwargs):
        """执行单条指令"""
        try:
            method = getattr(self._robot, cmd)
            result = method(*args, **kwargs)
            if result is not None:
                return str(result)
            return "OK"
        except Exception as e:
            return f"失败: {e}"

    def send(self, cmd, *args, **kwargs):
        """发送指令（阻塞，直接返回结果）"""
        res = self._exec(cmd, *args, **kwargs)
        self.command_result.emit(f"{cmd} → {res}")
        return res

    def stop(self):
        self._running = False
