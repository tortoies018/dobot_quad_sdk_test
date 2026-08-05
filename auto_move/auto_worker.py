"""
自动前后移动工作线程——使用 gRPC 高层 API 驱动机器人往复运动，
并用 IMU 数据（机体偏航角）实时矫正航向漂移。
"""

import math
import threading
import time

from PySide6.QtCore import QThread, Signal

from dobot_quad import RobotClient


class AutoMoveWorker(QThread):
    """后台线程：连接机器狗，循环前进/后退，并用 IMU 偏航角矫正方向"""

    # 进度信号：当前循环, 总循环, 阶段描述, 当前偏航角(度), 矫正量(度)
    progress = Signal(int, int, str, float, float)
    pos_ready = Signal(float, float, float)  # 世界坐标位置 (x, y, z) m，用于 3D 轨迹绘制
    imu_data = Signal(dict)        # 完整 IMU 数据（位置、四元数、陀螺仪、加速度、欧拉角）
    log_msg = Signal(str)          # 日志
    connected = Signal(bool)       # 连接状态
    finished_ok = Signal(str)      # 完成/中止消息

    def __init__(self, addr="10.30.12.154:50051", parent=None):
        super().__init__(parent)
        self._addr = addr
        self._robot = None
        self._is_wheel = False   # 是否为轮足机器人
        self._running = True
        self._pos_estimate = None    # vel_body 积分位置回退
        self._last_pos_time = None
        self._sampling = False       # 后台位置采样开关
        self._initial_rpy = None     # 初始姿态基准（3D 坐标显示用）

        # 可配置参数（由 GUI 设置）
        self.mode = "back_and_forth"   # back_and_forth / forward_only / backward_only
        self.distance = 1.0            # 单次移动距离 (m)
        self.segment = 0.3             # 分段长度 (m)：每移动一小段即用 IMU 实时矫正
        self.repetitions = 3           # 循环次数
        self.infinite = False          # 是否无限循环（直到手动停止）
        self.speed_ratio = 50          # 速度比 [10,100]（运行中可实时修改）
        self.use_imu = True            # 是否使用 IMU 矫正
        self.yaw_threshold = 3.0       # 矫正阈值 (度)
        self.turn_gain = 0.7           # 转向增益：每次转向纠正误差的比例 (0~1)
        self.settle_time = 0.5         # 每小段移动后姿态稳定等待时间 (秒)

    def stop(self):
        """请求停止"""
        self._running = False

    def set_address(self, addr):
        """更新机器人连接地址（在 start() 前调用）"""
        self._addr = addr

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

    # ─── 主流程 ─────────────────────────────────────

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

        # 记录初始偏航角作为矫正基准
        try:
            self._initial_yaw = self._get_yaw()
            self._log("INFO", f"初始偏航角: {self._initial_yaw:.2f}°")
        except Exception as e:
            self._log("ERROR", f"读取初始偏航角失败: {e}")
            self._initial_yaw = 0.0

        # 记录初始姿态作为 3D 坐标显示基准（站平时本体 Z 轴竖直）
        try:
            state = self._robot.get_state()
            ori = state.robot_state.ori_body
            self._initial_rpy = [float(v) for v in ori] if len(ori) >= 3 else [0.0, 0.0, 0.0]
            self._log(
                "INFO",
                f"姿态基准: roll={math.degrees(self._initial_rpy[0]):.1f}° "
                f"pitch={math.degrees(self._initial_rpy[1]):.1f}° "
                f"yaw={math.degrees(self._initial_rpy[2]):.1f}°",
            )
        except Exception as e:
            self._log("ERROR", f"读取初始姿态失败: {e}")
            self._initial_rpy = [0.0, 0.0, 0.0]

        # 记录初始位置（轨迹起点）
        self._emit_pos()

        # 启动后台连续位置采样线程（平滑绘制轨迹）
        self._sampling = True
        sampler = threading.Thread(target=self._sample_pos, daemon=True)
        sampler.start()

        do_forward = self.mode in ("back_and_forth", "forward_only")
        do_backward = self.mode in ("back_and_forth", "backward_only")

        try:
            cycle = 0
            while self._running:
                cycle += 1
                # 有限循环：达到次数后退出；无限循环：直到手动停止
                if not self.infinite and cycle > self.repetitions:
                    break
                total = 0 if self.infinite else self.repetitions

                if do_forward:
                    self.progress.emit(cycle, total, f"前进 {self.distance:.2f}m", 0, 0)
                    self._move_with_imu("forward", self.distance)
                    if not self._running:
                        break

                if do_backward:
                    self.progress.emit(cycle, total, f"后退 {self.distance:.2f}m", 0, 0)
                    self._move_with_imu("backward", self.distance)
                    if not self._running:
                        break

                self._log("INFO", f"第 {cycle} 次循环完成")

            if self._running and not self.infinite:
                self.finished_ok.emit(f"完成 {self.repetitions} 次循环")
            else:
                self.finished_ok.emit("已手动停止")
        except Exception as e:
            self._log("ERROR", f"执行出错: {e}")
            self.finished_ok.emit(f"出错: {e}")
        finally:
            self._sampling = False   # 停止后台位置采样

    # ─── 分段移动 + IMU 实时闭环控制 ────────────────

    def _move_with_imu(self, direction, distance):
        """将总移动距离拆分为小段，每移动一小段立即读取 IMU 偏航并实时矫正

        这是实时闭环控制：而非一次移动一大段后再矫正。
        每小段流程：移动 segment → 读取 IMU 偏航 → 若漂移则反向旋转矫正 → 继续下一段。
        """
        remaining = distance
        while remaining > 0.01 and self._running:
            step = min(self.segment, remaining)   # 本次小段长度
            self._do_move(direction, step)        # 移动一小段
            if not self._running:
                break
            if self.use_imu:
                self._correct_heading()           # 立即用 IMU 实时矫正
            remaining -= step

    def _do_move(self, direction, distance):
        """执行一次小段移动——使用通用移动 API（line_walk 系），不改变机器人状态"""
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

    def _sample_pos(self):
        """后台线程：以 10Hz 连续读取位置并发送轨迹点

        优先 pos_body（世界坐标）；为空则用 vel_body 积分估算。
        这样无论 pos_body 是否可用，都能绘制连续平滑轨迹。
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

                # 读取姿态与传感器数据
                try:
                    ori = rs.ori_body  # [roll, pitch, yaw] rad
                    rpy_abs = [float(v) for v in ori] if len(ori) >= 3 else [0.0, 0.0, 0.0]
                    ref = self._initial_rpy or [0.0, 0.0, 0.0]
                    # 相对初始姿态的欧拉角：站平时本体坐标轴保持竖直
                    imu["rpy"] = [
                        self._normalize_rad(rpy_abs[0] - ref[0]),
                        self._normalize_rad(rpy_abs[1] - ref[1]),
                        self._normalize_rad(rpy_abs[2] - ref[2]),
                    ]
                    imu["rpy_abs"] = rpy_abs
                except Exception:
                    imu["rpy"] = [0.0, 0.0, 0.0]
                    imu["rpy_abs"] = [0.0, 0.0, 0.0]
                try:
                    q = rs.quat_body  # [w, x, y, z]
                    imu["quat"] = [float(v) for v in q] if len(q) >= 4 else [1.0, 0.0, 0.0, 0.0]
                except Exception:
                    imu["quat"] = [1.0, 0.0, 0.0, 0.0]
                try:
                    g = rs.gyro_body  # [wx, wy, wz] rad/s
                    imu["gyro"] = [float(v) for v in g] if len(g) >= 3 else [0.0, 0.0, 0.0]
                except Exception:
                    imu["gyro"] = [0.0, 0.0, 0.0]
                try:
                    a = rs.accel_body  # [ax, ay, az] m/s²
                    imu["accel"] = [float(v) for v in a] if len(a) >= 3 else [0.0, 0.0, 0.0]
                except Exception:
                    imu["accel"] = [0.0, 0.0, 0.0]

                self.imu_data.emit(imu)
            except Exception:
                pass
            time.sleep(0.1)  # 10Hz

    def _get_yaw(self):
        """从 IMU 融合位姿中读取偏航角（度）"""
        state = self._robot.get_state()
        rpy = state.robot_state.ori_body  # [roll, pitch, yaw] 弧度
        yaw_deg = math.degrees(rpy[2])
        return yaw_deg

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

    def _correct_heading(self):
        """使用 IMU 偏航角矫正航向漂移"""
        if not self.use_imu:
            return
        try:
            yaw = self._get_yaw()
            # 偏航误差 = 当前偏航 - 初始偏航（归一化到 [-180, 180]）
            err = self._normalize_angle(yaw - self._initial_yaw)

            self.progress.emit(0, 0, "读取IMU", yaw, err)

            if abs(err) <= self.yaw_threshold:
                self._log("INFO", f"IMU矫正: 偏航 {yaw:.2f}°，误差 {err:.2f}°（在阈值内，无需矫正）")
                return

            # ── 闭环分段转向 ──
            # 不一次转满误差角（实际旋转存在误差），而是：
            # 每次转误差的一部分 → 实时读 IMU → 再转 → 直到误差收敛
            attempts = 0
            max_attempts = 12
            while abs(err) > self.yaw_threshold and self._running and attempts < max_attempts:
                attempts += 1
                # 每次转向 = 当前误差 × 增益（留余量避免过冲），最小转角 1°
                turn = max(abs(err) * self.turn_gain, 1.0)
                # 若误差 > 0（相对初始左偏），向右转纠正；反之向左转
                self._log(
                    "INFO",
                    f"IMU矫正[{attempts}]: 偏航 {yaw:.2f}°，误差 {err:.2f}°，"
                    f"{'右转' if err > 0 else '左转'} {turn:.2f}°"
                )
                if err > 0:
                    self._robot.rotate_right(turn, show_progress=False)
                else:
                    self._robot.rotate_left(turn, show_progress=False)
                time.sleep(self.settle_time)

                # 实时读取 IMU 校验残差
                yaw = self._get_yaw()
                err = self._normalize_angle(yaw - self._initial_yaw)
                self.progress.emit(0, 0, f"矫正中({attempts}/{max_attempts})", yaw, err)

            # 矫正后校验
            self.progress.emit(0, 0, "矫正完成", yaw, err)
            self._log("INFO", f"矫正后偏航: {yaw:.2f}°，残差 {err:.2f}°（{attempts} 次迭代）")
            self._emit_pos()   # 矫正后记录轨迹点
        except Exception as e:
            self._log("ERROR", f"IMU矫正失败: {e}")

    @staticmethod
    def _normalize_angle(deg):
        """将角度归一化到 [-180, 180]"""
        while deg > 180:
            deg -= 360
        while deg < -180:
            deg += 360
        return deg

    @staticmethod
    def _normalize_rad(rad):
        """将弧度归一化到 [-π, π]"""
        while rad > math.pi:
            rad -= 2 * math.pi
        while rad < -math.pi:
            rad += 2 * math.pi
        return rad
