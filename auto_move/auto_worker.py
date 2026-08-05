"""
自动前后移动工作线程——使用 gRPC 高层 API 驱动机器人往复运动。

线程常驻：连接后轨迹/IMU 采样一直工作，与移动指令独立；
移动指令通过命令队列逐条下发。
"""

import math
import queue
import threading
import time

from PySide6.QtCore import QThread, Signal

from dobot_quad import RobotClient


class AutoMoveWorker(QThread):
    """后台线程：连接机器狗；轨迹/IMU 常驻采样，移动指令排队执行"""

    # 进度信号：当前循环, 总循环, 阶段描述
    progress = Signal(int, int, str)
    pos_ready = Signal(float, float, float)  # 世界坐标位置 (x, y, z) m，用于 3D 轨迹绘制
    ideal_path = Signal(list)      # 理想轨迹点列表 [[x,y,z], ...]
    imu_data = Signal(dict)        # 完整 IMU 数据（位置、欧拉角）
    log_msg = Signal(str)          # 日志
    connected = Signal(bool)       # 连接状态
    finished_ok = Signal(str)      # 完成/中止消息

    def __init__(self, addr="10.30.12.154:50051", parent=None):
        super().__init__(parent)
        self._addr = addr
        self._robot = None
        self._is_wheel = False   # 是否为轮足机器人
        self._running = True     # 线程存活（直到 shutdown）
        self._move_running = False   # 当前是否有移动指令在运行
        self._pos_estimate = None    # vel_body 积分位置回退
        self._last_pos_time = None
        self._sampling = False       # 后台采样开关（常驻）
        self._initial_rpy = None     # 初始姿态基准（3D 坐标显示用）
        self._initial_yaw = 0.0      # 初始偏航角（航向矫正基准）
        self._cmd_queue = queue.Queue()   # 移动指令队列

        # 可配置参数（由 GUI 下发）
        self.mode = "back_and_forth"   # back_and_forth / forward_only / backward_only / square
        self.distance = 1.0            # 直线单次移动距离 (m)
        self.side_len = 1.0            # 正方形边长 (m)
        self.repetitions = 3           # 循环次数
        self.infinite = False          # 是否无限循环（直到手动停止）
        self.speed_ratio = 50          # 速度比 [10,100]（运行中可实时修改）
        self.settle_time = 0.5         # 移动/转向后姿态稳定等待时间 (秒)
        self.yaw_threshold = 3.0       # 航向矫正阈值 (度)

    # ─── 控制接口（主线程调用） ────────────────────

    def set_address(self, addr):
        """更新机器人连接地址（在 start() 前调用）"""
        self._addr = addr

    def start_move(self, params):
        """下发一条移动指令（连接后排队执行）"""
        self._move_running = True
        self._cmd_queue.put(params)

    def stop_move(self):
        """停止当前移动指令（轨迹/IMU 采样不受影响）"""
        self._move_running = False

    def stop(self):
        """兼容旧接口：停止当前移动"""
        self._move_running = False

    def shutdown(self):
        """完全关闭：结束线程并停止采样"""
        self._running = False
        self._move_running = False
        self._cmd_queue.put(None)   # 唤醒命令循环

    def _log(self, level, msg):
        """发送带时间戳和信息级别的日志： [HH:MM:SS] [级别] 消息"""
        ts = time.strftime("%H:%M:%S")
        self.log_msg.emit(f"[{ts}] [{level}] {msg}")

    def update_speed(self, ratio):
        """运行中实时修改速度比（下一次移动立即生效）"""
        self.speed_ratio = max(10, min(100, int(ratio)))
        if self._robot is not None:
            try:
                self._robot.set_speed_ratio(self.speed_ratio)
                self._log("INFO", f"速度比实时更新为 {self.speed_ratio}")
            except Exception as e:
                self._log("ERROR", f"实时更新速度比失败: {e}")

    # ─── 主流程：连接 + 常驻采样 + 指令循环 ────────

    def run(self):
        try:
            self._robot = RobotClient(self._addr)
            self._is_wheel = self._robot.is_quad_wheel()
            self.connected.emit(True)
            self._log("INFO", f"已连接 {self._addr}（{'轮足' if self._is_wheel else '点足'}）")
        except Exception as e:
            self._log("ERROR", f"连接失败: {e}")
            self.connected.emit(False)
            return

        try:
            self._robot.set_speed_ratio(self.speed_ratio)
            self._log("INFO", f"速度比已设为 {self.speed_ratio}")
        except Exception as e:
            self._log("ERROR", f"设置速度比失败: {e}")

        # 启动常驻采样线程：轨迹/IMU 一直工作，与移动指令独立
        self._sampling = True
        sampler = threading.Thread(target=self._sample_pos, daemon=True)
        sampler.start()

        # 等待并逐条执行移动指令
        while self._running:
            try:
                cmd = self._cmd_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if cmd is None:
                break
            self._execute_move(cmd)

        self._sampling = False   # 线程结束，停止采样

    def _execute_move(self, cmd):
        """执行一条移动指令（采样线程不中断）"""
        self.mode = cmd.get("mode", "back_and_forth")
        self.distance = cmd.get("distance", 1.0)
        self.side_len = cmd.get("side_len", 1.0)
        self.repetitions = cmd.get("repetitions", 3)
        self.infinite = cmd.get("infinite", False)
        self.speed_ratio = cmd.get("speed_ratio", 50)
        self.settle_time = cmd.get("settle_time", 0.5)

        try:
            self._robot.set_speed_ratio(self.speed_ratio)
            self._log("INFO", f"速度比已设为 {self.speed_ratio}")
        except Exception as e:
            self._log("ERROR", f"设置速度比失败: {e}")

        # 记录本次移动的姿态/偏航基准（3D 显示与航向矫正用）
        try:
            state = self._robot.get_state()
            ori = state.robot_state.ori_body
            self._initial_rpy = [float(v) for v in ori] if len(ori) >= 3 else [0.0, 0.0, 0.0]
            self._initial_yaw = math.degrees(self._initial_rpy[2])
            self._log(
                "INFO",
                f"姿态基准: roll={math.degrees(self._initial_rpy[0]):.1f}° "
                f"pitch={math.degrees(self._initial_rpy[1]):.1f}° "
                f"yaw={self._initial_yaw:.1f}°",
            )
        except Exception as e:
            self._log("ERROR", f"读取初始姿态失败: {e}")
            self._initial_rpy = [0.0, 0.0, 0.0]
            self._initial_yaw = 0.0

        # 记录轨迹起点
        self._emit_pos()

        # 正方形模式：先计算并发送理想轨迹
        if self.mode == "square":
            start = self._read_pos()
            pts = self._ideal_square_points(start, self._initial_yaw, self.side_len)
            self.ideal_path.emit(pts)
            self._log(
                "INFO",
                f"理想正方形: 起点({start[0]:.2f}, {start[1]:.2f}) "
                f"边长{self.side_len:.2f}m",
            )

        do_forward = self.mode in ("back_and_forth", "forward_only")
        do_backward = self.mode in ("back_and_forth", "backward_only")
        do_square = self.mode == "square"

        try:
            cycle = 0
            while self._running and self._move_running:
                cycle += 1
                # 有限循环：达到次数后退出；无限循环：直到手动停止
                if not self.infinite and cycle > self.repetitions:
                    break
                total = 0 if self.infinite else self.repetitions

                if do_square:
                    self.progress.emit(cycle, total, f"正方形 边长{self.side_len:.2f}m")
                    self._run_square(cycle, total)
                elif do_forward:
                    self.progress.emit(cycle, total, f"前进 {self.distance:.2f}m")
                    self._move("forward", self.distance)
                    if not self._move_running:
                        break
                    self._correct_heading_once()   # 移动完整距离后矫正一次航向

                if do_backward:
                    self.progress.emit(cycle, total, f"后退 {self.distance:.2f}m")
                    self._move("backward", self.distance)
                    if not self._move_running:
                        break
                    self._correct_heading_once()   # 移动完整距离后矫正一次航向

                self._log("INFO", f"第 {cycle} 次循环完成")

            if self._move_running and not self.infinite:
                self.finished_ok.emit(f"完成 {self.repetitions} 次循环")
            else:
                self.finished_ok.emit("已手动停止")
        except Exception as e:
            self._log("ERROR", f"执行出错: {e}")
            self.finished_ok.emit(f"出错: {e}")
        finally:
            self._move_running = False   # 移动指令结束

    # ─── 移动 ─────────────────────────────────────

    def _move(self, direction, distance):
        """执行一次移动——使用通用移动 API（line_walk 系），不改变机器人状态"""
        try:
            if direction == "forward":
                self._robot.walk_forward(distance, self.speed_ratio, show_progress=False)
            else:
                self._robot.walk_backward(distance, self.speed_ratio, show_progress=False)
        except Exception as e:
            self._log("ERROR", f"移动失败({direction}): {e}")
            raise
        time.sleep(self.settle_time)  # 等待姿态稳定
        self._emit_pos()              # 移动后记录轨迹点

    def _get_yaw(self):
        """从 IMU 融合位姿中读取偏航角（度）"""
        state = self._robot.get_state()
        rpy = state.robot_state.ori_body  # [roll, pitch, yaw] 弧度
        return math.degrees(rpy[2])

    def _correct_heading_once(self):
        """移动完一段完整距离后，按当前偏航误差做一次转向矫正

        不做闭环反复修正：只转一次（误差超出阈值时转误差角），
        误差在阈值内则不动。
        """
        try:
            yaw = self._get_yaw()
            err = self._normalize_angle(yaw - self._initial_yaw)
            if abs(err) <= self.yaw_threshold:
                self._log(
                    "INFO",
                    f"航向: 偏航 {yaw:.2f}°，误差 {err:.2f}°（在阈值内，无需转向）",
                )
                return
            self._log(
                "INFO",
                f"航向矫正: 偏航 {yaw:.2f}°，误差 {err:.2f}°，"
                f"{'右转' if err > 0 else '左转'} {abs(err):.2f}°",
            )
            if err > 0:
                self._robot.rotate_right(abs(err), show_progress=False)
            else:
                self._robot.rotate_left(abs(err), show_progress=False)
            time.sleep(self.settle_time)
            self._emit_pos()   # 转向后记录轨迹点
        except Exception as e:
            self._log("ERROR", f"航向矫正失败: {e}")

    # ─── 正方形运动 ────────────────────────────────

    def _run_square(self, cycle, total):
        """正方形运动：前进一条边 → 右转90° → 前进 → ... 共 4 条边，最后转回初始方向"""
        for i in range(4):
            if not (self._running and self._move_running):
                return
            self.progress.emit(cycle, total, f"正方形 第{i + 1}/4 边")
            self._move("forward", self.side_len)      # 走一条边
            if not (self._running and self._move_running):
                return
            if i < 3:
                self._robot.rotate_right(90, show_progress=False)   # 右转90°（转角）
                time.sleep(self.settle_time)
                self._emit_pos()

        # 正方形走完，转回初始方向（按 IMU 偏航一次转向纠正累计漂移）
        if self._running and self._move_running:
            self.progress.emit(cycle, total, "正方形完成，转回初始方向")
            self._correct_heading_once()

    def _read_pos(self):
        """读取当前世界坐标 [x, y, z]（m）；pos_body 为空则回退 vel_body 积分估算"""
        try:
            state = self._robot.get_state()
            rs = state.robot_state
            pos = rs.pos_body
            if len(pos) >= 2:
                z = float(pos[2]) if len(pos) >= 3 else 0.0
                return [float(pos[0]), float(pos[1]), z]
            vel = rs.vel_body
            if len(vel) >= 2:
                now = time.monotonic()
                if self._pos_estimate is None:
                    self._pos_estimate = [0.0, 0.0, 0.0]
                dt = (now - self._last_pos_time) if self._last_pos_time else 0.0
                self._last_pos_time = now
                self._pos_estimate[0] += vel[0] * dt
                self._pos_estimate[1] += vel[1] * dt
                if len(vel) >= 3:
                    self._pos_estimate[2] += vel[2] * dt
                return self._pos_estimate.copy()
        except Exception:
            pass
        return [0.0, 0.0, 0.0]

    @staticmethod
    def _ideal_square_points(start, yaw_deg, side):
        """理想正方形轨迹顶点（世界坐标，右转90°，闭合）

        以 start 为起点、初始偏航为朝向，按“前进一边 → 右转90°”推算：
        u 为前进方向，v 为 u 顺时针转90°（对应右转）后的方向。
        """
        h = math.radians(yaw_deg)
        u = (math.cos(h), math.sin(h))
        v = (math.sin(h), -math.cos(h))
        sx, sy = float(start[0]), float(start[1])
        return [
            [sx, sy, 0.0],
            [sx + side * u[0], sy + side * u[1], 0.0],
            [sx + side * u[0] + side * v[0], sy + side * u[1] + side * v[1], 0.0],
            [sx + side * v[0], sy + side * v[1], 0.0],
            [sx, sy, 0.0],
        ]

    def _sample_pos(self):
        """后台线程：以 10Hz 连续读取位置并发送轨迹点（常驻，与指令独立）

        优先 pos_body（世界坐标）；为空则用 vel_body 积分估算。
        """
        last = time.monotonic()
        diag_done = False
        while self._sampling and self._running:
            try:
                state = self._robot.get_state()
                rs = state.robot_state
                pos = rs.pos_body
                vel = rs.vel_body
                # 组装完整 IMU 数据字典
                imu = {}
                if len(pos) >= 2:
                    if not diag_done:
                        self._log("INFO", "轨迹数据源: pos_body（世界坐标）")
                        diag_done = True
                    z = float(pos[2]) if len(pos) >= 3 else 0.0
                    self.pos_ready.emit(float(pos[0]), float(pos[1]), z)
                    imu["pos"] = [float(pos[0]), float(pos[1]), z]
                elif len(vel) >= 2:
                    if not diag_done:
                        self._log("INFO", "轨迹数据源: vel_body 积分")
                        diag_done = True
                    now = time.monotonic()
                    dt = now - last
                    last = now
                    if self._pos_estimate is None:
                        self._pos_estimate = [0.0, 0.0, 0.0]
                    self._pos_estimate[0] += vel[0] * dt
                    self._pos_estimate[1] += vel[1] * dt
                    if len(vel) >= 3:
                        self._pos_estimate[2] += vel[2] * dt
                    self.pos_ready.emit(
                        self._pos_estimate[0],
                        self._pos_estimate[1],
                        self._pos_estimate[2],
                    )
                    imu["pos"] = self._pos_estimate.copy()
                else:
                    if not diag_done:
                        self._log("ERROR", "pos_body 和 vel_body 均为空，高层 API 不提供位置，轨迹无法绘制")
                        diag_done = True
                    imu["pos"] = [0.0, 0.0, 0.0]

                # 读取姿态（相对初始姿态，站平时本体坐标轴竖直）
                try:
                    ori = rs.ori_body  # [roll, pitch, yaw] rad
                    rpy_abs = [float(v) for v in ori] if len(ori) >= 3 else [0.0, 0.0, 0.0]
                    ref = self._initial_rpy or [0.0, 0.0, 0.0]
                    imu["rpy"] = [
                        self._normalize_rad(rpy_abs[0] - ref[0]),
                        self._normalize_rad(rpy_abs[1] - ref[1]),
                        self._normalize_rad(rpy_abs[2] - ref[2]),
                    ]
                    imu["rpy_abs"] = rpy_abs
                except Exception:
                    imu["rpy"] = [0.0, 0.0, 0.0]
                    imu["rpy_abs"] = [0.0, 0.0, 0.0]

                self.imu_data.emit(imu)
            except Exception:
                pass
            time.sleep(0.1)  # 10Hz

    # ─── 位置读取 ─────────────────────────────────

    def _emit_pos(self):
        """读取世界坐标位置并发送轨迹点 (x, y, z) m

        优先使用 pos_body（IMU/里程计融合定位）；
        若为空则回退用 vel_body 积分估算位置。
        """
        try:
            state = self._robot.get_state()
            rs = state.robot_state
            pos = rs.pos_body

            if len(pos) >= 2:
                if len(pos) >= 3:
                    self.pos_ready.emit(float(pos[0]), float(pos[1]), float(pos[2]))
                    self._log("INFO", f"位置: x={pos[0]:.3f} y={pos[1]:.3f} z={pos[2]:.3f}")
                else:
                    self.pos_ready.emit(float(pos[0]), float(pos[1]), 0.0)
                    self._log("INFO", f"位置: x={pos[0]:.3f} y={pos[1]:.3f}")
                return

            # 回退：vel_body 积分
            vel = rs.vel_body
            if len(vel) >= 2:
                now = time.monotonic()
                if self._pos_estimate is None:
                    self._pos_estimate = [0.0, 0.0, 0.0]
                dt = (now - self._last_pos_time) if self._last_pos_time else 0.0
                self._last_pos_time = now
                self._pos_estimate[0] += vel[0] * dt
                self._pos_estimate[1] += vel[1] * dt
                if len(vel) >= 3:
                    self._pos_estimate[2] += vel[2] * dt
                self.pos_ready.emit(
                    self._pos_estimate[0],
                    self._pos_estimate[1],
                    self._pos_estimate[2],
                )
                self._log(
                    "INFO",
                    f"位置(积分): x={self._pos_estimate[0]:.3f} "
                    f"y={self._pos_estimate[1]:.3f} z={self._pos_estimate[2]:.3f}",
                )
            else:
                self._log("WARN", "pos_body 和 vel_body 均为空，无法绘制轨迹")
        except Exception as e:
            self._log("ERROR", f"读取位置失败: {e}")

    @staticmethod
    def _normalize_rad(rad):
        """将弧度归一化到 [-π, π]"""
        while rad > math.pi:
            rad -= 2 * math.pi
        while rad < -math.pi:
            rad += 2 * math.pi
        return rad

    @staticmethod
    def _normalize_angle(deg):
        """将角度归一化到 [-180, 180]"""
        while deg > 180:
            deg -= 360
        while deg < -180:
            deg += 360
        return deg
