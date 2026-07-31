"""
gRPC 指令工作线程——连接机器狗并执行命令

该线程负责维护与机器人的 gRPC 连接，周期轮询机器人状态，
并通过 Qt 信号将状态和指令结果发送到主线程更新 UI。
"""

import time
from PySide6.QtCore import QThread, Signal

from dobot_quad import RobotClient


class RobotWorker(QThread):
    """后台线程：维护 RobotClient 连接，执行指令并轮询状态"""

    # 状态更新信号：(机器人类型, FSM状态, 速度比, 避障开关, 附加信息, 遥测文本)
    status_updated = Signal(str, str, int, bool, str, dict)
    command_result = Signal(str)   # 指令执行结果
    connected = Signal(bool)       # 连接状态变化
    log = Signal(str)              # 日志消息

    def __init__(self, addr="192.168.1.6:50051", parent=None):
        """
        初始化工作线程

        :param addr: 机器人的 gRPC 服务地址（WiFi 连接 192.168.1.6:50051）
        """
        super().__init__(parent)
        self._addr = addr
        self._robot = None
        self._running = True

    def run(self):
        """线程主循环：连接机器人并周期轮询状态"""
        try:
            self._robot = RobotClient(self._addr)  # 创建 gRPC 客户端
            self.connected.emit(True)              # 通知 UI 连接成功
            self.log.emit(f"已连接 {self._addr}")
        except Exception as e:
            self.log.emit(f"连接失败: {e}")
            self.connected.emit(False)
            return

        while self._running:
            try:
                # 获取机器人完整状态
                state = self._robot.get_state()
                rt = self._robot.get_robot_type()  # 机器人类型

                # 提取机体位置用于遥测显示
                rs = state.robot_state
                pos = list(rs.pos_body) if rs.pos_body else []
                tele = f"位置:[{pos[0]:.2f},{pos[1]:.2f},{pos[2]:.2f}]" if len(pos) >= 3 else ""

                # 发送状态更新信号
                self.status_updated.emit(
                    rt, state.current_state, state.current_speed_ratio,
                    state.obstacle_avoidance_enabled, "轮询 OK", tele
                )
            except Exception as e:
                self.log.emit(f"轮询失败: {e}")

            time.sleep(0.5)  # 轮询间隔 500ms

    def _exec(self, cmd, *args, **kwargs):
        """执行单条指令并返回结果字符串"""
        try:
            method = getattr(self._robot, cmd)  # 动态获取方法
            result = method(*args, **kwargs)    # 调用方法
            if result is not None:
                return str(result)              # 有返回值则转字符串
            return "OK"                         # 无返回值视为成功
        except Exception as e:
            return f"失败: {e}"                 # 异常返回错误信息

    def send(self, cmd, *args, **kwargs):
        """发送指令（阻塞调用，直接返回结果）"""
        res = self._exec(cmd, *args, **kwargs)
        self.command_result.emit(f"{cmd} → {res}")  # 通知 UI 记录日志
        return res

    def stop(self):
        """停止线程"""
        self._running = False
