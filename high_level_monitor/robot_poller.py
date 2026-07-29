"""gRPC 数据轮询线程——定时调用 RobotClient 获取机器人状态"""

import time

from PySide6.QtCore import QThread, Signal

from dobot_quad import RobotClient


class RobotPoller(QThread):
    """
    后台线程，每隔一定间隔通过 gRPC 查询机器人状态，
    并通过 Qt 信号将数据发送到主线程更新 UI。
    """

    # 各数据类型的信号
    info_ready = Signal(str, str, int, bool)       # 类型, FSM, 速度比, 避障
    pose_ready = Signal(list, list, list, list, list)  # pos, vel, accel, omega, rpy
    joints_ready = Signal(list, list, list)         # jpos, jvel, jtau
    grf_ready = Signal(list, list, list)            # grf_left, grf_right, grf_filtered
    status_msg = Signal(str)                        # 状态栏消息
    connected = Signal(bool)                        # 连接状态变化

    def __init__(self, addr="192.168.5.2:50051", interval=0.2, parent=None):
        """
        :param addr:     gRPC 服务地址
        :param interval: 轮询间隔（秒）
        """
        super().__init__(parent)
        self._addr = addr
        self._interval = interval
        self._robot = None
        self._running = True

    def run(self):
        """线程主循环：连接并持续轮询"""
        self._robot = RobotClient(self._addr)
        self.connected.emit(True)
        self.status_msg.emit(f"已连接到 {self._addr}")

        while self._running:
            try:
                # 获取完整状态快照
                state_res = self._robot.get_state()
                robot_type = self._robot.get_robot_type()

                # 提取基本信息
                fsm = state_res.current_state
                speed = state_res.current_speed_ratio
                avoid = state_res.obstacle_avoidance_enabled
                self.info_ready.emit(robot_type, fsm, speed, avoid)

                # 提取机体数据
                rs = state_res.robot_state
                pos = list(rs.pos_body) if rs.pos_body else []
                vel = list(rs.vel_body) if rs.vel_body else []
                accel = list(rs.acc_body) if rs.acc_body else []
                omega = list(rs.omega_body) if rs.omega_body else []
                rpy = list(rs.ori_body) if rs.ori_body else []
                self.pose_ready.emit(pos, vel, accel, omega, rpy)

                # 提取关节数据
                jpos = list(rs.jpos_leg) if rs.jpos_leg else []
                jvel = list(rs.jvel_leg) if rs.jvel_leg else []
                jtau = list(rs.jtau_leg) if rs.jtau_leg else []
                self.joints_ready.emit(jpos, jvel, jtau)

                # 提取接触力
                grf_l = list(rs.grf_left) if rs.grf_left else []
                grf_r = list(rs.grf_right) if rs.grf_right else []
                grf_f = list(rs.grf_vertical_filtered) if rs.grf_vertical_filtered else []
                self.grf_ready.emit(grf_l, grf_r, grf_f)

            except Exception as e:
                self.status_msg.emit(f"轮询失败: {e}")
                self.connected.emit(False)

            time.sleep(self._interval)

    def stop(self):
        """停止轮询线程"""
        self._running = False
