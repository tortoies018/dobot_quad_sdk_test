"""
自动前后移动工作线程——使用 gRPC 高层 API 驱动机器人往复运动。

线程常驻：连接后轨迹/IMU 采样一直工作，与移动指令独立；
移动指令通过命令队列逐条下发。
"""

import csv
import math
import os
import queue
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from dobot_quad import RobotClient


class AutoMoveWorker(QThread):
    """后台线程：连接机器狗；轨迹/IMU 常驻采样，移动指令排队执行"""

    # 进度信号：当前循环, 总循环, 阶段描述
    progress = Signal(int, int, str)
    pos_ready = Signal(float, float, float)  # 世界坐标位置 (x, y, z) m，用于 3D 轨迹绘制
    ideal_path = Signal(list)      # 理想轨迹点列表 [[x,y,z], ...]
    command_preview = Signal(dict)  # 当前指令的实时位置、目标、航向和阶段
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
        self._active_target = None
        self._active_target_yaw = 0.0
        self._active_phase = ""
        self._active_segment = 0
        self._measurement_lock = threading.Lock()
        self._measurement_active = False
        self._measurement_yaws = []
        self.precision_groups = 100
        self.last_result_path = None
        self.result_dir = Path(__file__).resolve().parent / "results"

        # 可配置参数（由 GUI 下发）
        self.mode = "back_and_forth"   # back_and_forth / forward_only / backward_only / square
        self.control_api = "line_walk"  # line_walk / velocity_sequence
        self.distance = 1.0            # 直线单次移动距离 (m)
        self.side_len = 1.0            # 正方形边长 (m)
        self.repetitions = 3           # 循环次数
        self.infinite = False          # 是否无限循环（直到手动停止）
        self.speed_ratio = 50          # 速度比 [10,100]（运行中可实时修改）
        self.linear_velocity = 0.3     # velocity_sequence: |vx| (m/s)
        self.yaw_velocity = 0.3        # velocity_sequence: |vyaw| (rad/s)
        self.settle_time = 0.5         # 移动/转向后姿态稳定等待时间 (秒)
        self.yaw_threshold = 3.0       # 航向矫正阈值 (度)
        self.position_threshold = 0.02  # 到达目标点判定阈值 (m)

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
                self._log("API", f"set_speed_ratio(ratio={self.speed_ratio})")
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
            self._log("API", f"set_speed_ratio(ratio={self.speed_ratio})")
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
        self.control_api = cmd.get("control_api", "line_walk")
        self.distance = cmd.get("distance", 1.0)
        self.side_len = cmd.get("side_len", 1.0)
        self.repetitions = cmd.get("repetitions", 3)
        self.infinite = cmd.get("infinite", False)
        self.speed_ratio = cmd.get("speed_ratio", 50)
        self.linear_velocity = max(0.1, float(cmd.get("linear_velocity", 0.3)))
        self.yaw_velocity = max(0.1, float(cmd.get("yaw_velocity", 0.3)))
        self.settle_time = cmd.get("settle_time", 0.5)

        try:
            self._robot.set_speed_ratio(self.speed_ratio)
            self._log("API", f"set_speed_ratio(ratio={self.speed_ratio})")
        except Exception as e:
            self._log("ERROR", f"设置速度比失败: {e}")

        if self.control_api == "velocity_sequence":
            try:
                if self._is_wheel:
                    self._log("API", "wheel_loco(show_progress=False)")
                    self._robot.wheel_loco(show_progress=False)
                else:
                    self._log("API", "balance_stand(show_progress=False)")
                    self._robot.balance_stand(show_progress=False)
            except Exception as e:
                self._log("ERROR", f"velocity_sequence 准备运动状态失败: {e}")
                self.finished_ok.emit(f"出错: {e}")
                self._move_running = False
                return

        if self.mode == "precision_test":
            self._execute_precision_suite()
            return

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

        # 计算并发送理想轨迹（指令移动效果：起点 → 目的地线段 / 正方形）
        start = self._read_pos()
        sx, sy = float(start[0]), float(start[1])
        square_targets = []
        if self.mode == "square":
            pts = self._ideal_square_points(start, self._initial_yaw, self.side_len)
            square_targets = pts[1:]
            self.ideal_path.emit(pts)
            self._log(
                "INFO",
                f"指令轨迹: 正方形，边长 {self.side_len:.2f}m；"
                "每条边按实时位置转向目标点并计算剩余距离",
            )
        else:
            h = math.radians(self._initial_yaw)
            u = (math.cos(h), math.sin(h))
            if self.mode == "backward_only":
                ex, ey = sx - self.distance * u[0], sy - self.distance * u[1]
            else:   # forward_only / back_and_forth
                ex, ey = sx + self.distance * u[0], sy + self.distance * u[1]
            if self.mode == "back_and_forth":
                pts = [[sx, sy, 0.0], [ex, ey, 0.0], [sx, sy, 0.0]]
            else:
                pts = [[sx, sy, 0.0], [ex, ey, 0.0]]
            self.ideal_path.emit(pts)
            self._log(
                "INFO",
                f"理想轨迹: 起点({sx:.2f}, {sy:.2f}) 终点({ex:.2f}, {ey:.2f}) "
                f"距离 {self.distance:.2f}m",
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
                    self._run_square(cycle, total, square_targets)
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
            self._clear_command_preview()
            self._move_running = False   # 移动指令结束

    # ─── SDK 指令精度自动测试 ─────────────────────

    @staticmethod
    def _precision_case_pairs():
        """按相反方向配对，保证每组测试后尽量回到开始位置/朝向。"""
        pairs = []
        for distance in (1.0, 2.0, 3.0):
            pairs.append((
                "前后移动",
                (("forward", "前进", distance, "m"), ("backward", "后退", distance, "m")),
            ))
        for distance in (1.0, 2.0, 3.0):
            pairs.append((
                "左右平移",
                (("left", "左平移", distance, "m"), ("right", "右平移", distance, "m")),
            ))
        for angle in (90.0, 180.0, 360.0):
            pairs.append((
                "左右旋转",
                (("left", "左旋转", angle, "deg"), ("right", "右旋转", angle, "deg")),
            ))
        return pairs

    @staticmethod
    def _precision_fields():
        return [
            "run_id", "timestamp", "result_index", "speed_ratio", "control_api",
            "pair_type", "direction", "target_value", "target_unit", "group_index",
            "status", "error", "duration_s", "imu_sample_count",
            "start_x_m", "start_y_m", "start_z_m", "start_yaw_deg",
            "end_x_m", "end_y_m", "end_z_m", "end_yaw_deg",
            "delta_x_m", "delta_y_m", "delta_z_m",
            "expected_distance_m", "actual_distance_m", "distance_error_m",
            "abs_distance_error_m", "lateral_error_m", "vertical_error_m",
            "yaw_drift_deg", "expected_angle_deg", "actual_angle_deg",
            "angle_error_deg", "abs_angle_error_deg", "position_drift_m",
        ]

    def _execute_precision_suite(self):
        """自动执行规范中的全部测试，并在每条指令后立即持久化 IMU 误差。"""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        result_dir = Path(self.result_dir)
        result_dir.mkdir(parents=True, exist_ok=True)
        result_path = result_dir / f"sdk_precision_{run_id}.csv"
        summary_path = result_dir / f"sdk_precision_{run_id}_summary.csv"
        self.last_result_path = str(result_path)

        cases = self._precision_case_pairs()
        total = 2 * len(cases) * self.precision_groups * 2
        completed = 0
        records = []
        failure = None
        self._log(
            "INFO",
            f"SDK 指令精度测试开始: 每个单项 {self.precision_groups} 组，"
            f"共 {total} 条结果，文件 {result_path}",
        )

        try:
            with result_path.open("w", newline="", encoding="utf-8-sig") as file_obj:
                writer = csv.DictWriter(file_obj, fieldnames=self._precision_fields())
                writer.writeheader()
                file_obj.flush()

                for speed_ratio in (100, 50):
                    if not (self._running and self._move_running):
                        break
                    self.speed_ratio = speed_ratio
                    self._robot.set_speed_ratio(speed_ratio)
                    self._log("API", f"set_speed_ratio(ratio={speed_ratio})")

                    for pair_type, commands in cases:
                        if not (self._running and self._move_running):
                            break
                        for group_index in range(1, self.precision_groups + 1):
                            if not (self._running and self._move_running):
                                break
                            for direction, direction_label, target, unit in commands:
                                if not (self._running and self._move_running):
                                    break
                                result_index = completed + 1
                                stage = (
                                    f"精度测试 {speed_ratio}% {direction_label}{target:g}{unit} "
                                    f"第{group_index}/{self.precision_groups}组"
                                )
                                self.progress.emit(result_index, total, stage)
                                row, command_error = self._measure_precision_command(
                                    run_id=run_id,
                                    result_index=result_index,
                                    speed_ratio=speed_ratio,
                                    pair_type=pair_type,
                                    direction=direction,
                                    direction_label=direction_label,
                                    target=target,
                                    unit=unit,
                                    group_index=group_index,
                                )
                                writer.writerow(row)
                                file_obj.flush()
                                os.fsync(file_obj.fileno())
                                records.append(row)
                                completed += 1
                                self._log_precision_result(row, completed, total)
                                if command_error is not None:
                                    failure = command_error
                                    raise command_error
        except Exception as exc:
            failure = failure or exc
            self._log("ERROR", f"精度测试中止: {exc}")
        finally:
            try:
                self._write_precision_summary(records, summary_path)
            except Exception as exc:
                self._log("ERROR", f"写入汇总文件失败: {exc}")
            self._clear_command_preview()
            self._move_running = False

        if failure is not None:
            self.finished_ok.emit(
                f"出错: 已记录 {completed}/{total} 条，结果 {result_path}，原因: {failure}"
            )
        elif completed < total:
            self.finished_ok.emit(
                f"已手动停止，已记录 {completed}/{total} 条，结果 {result_path}"
            )
        else:
            self.finished_ok.emit(
                f"完成精度测试，共 {completed} 条，结果 {result_path}，汇总 {summary_path}"
            )

    def _measure_precision_command(
        self,
        run_id,
        result_index,
        speed_ratio,
        pair_type,
        direction,
        direction_label,
        target,
        unit,
        group_index,
    ):
        """执行一条测试指令，返回可立即写入 CSV 的结果和可能的异常。"""
        started = time.monotonic()
        try:
            before = self._read_imu_pose()
        except Exception as exc:
            before = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw_rad": 0.0}
            row = self._calculate_precision_result(
                before, before, [0.0], pair_type, direction, float(target))
            row.update({
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                "result_index": result_index,
                "speed_ratio": speed_ratio,
                "control_api": self.control_api,
                "pair_type": pair_type,
                "direction": direction_label,
                "target_value": target,
                "target_unit": unit,
                "group_index": group_index,
                "status": "error",
                "error": f"读取指令前 IMU 失败: {exc}",
                "duration_s": round(time.monotonic() - started, 6),
                "imu_sample_count": 0,
            })
            return row, exc

        with self._measurement_lock:
            self._measurement_yaws = [before["yaw_rad"]]
            self._measurement_active = True

        command_error = None
        try:
            if pair_type == "前后移动":
                self._move(direction, target)
            elif pair_type == "左右平移":
                self._move_lateral(direction, target)
            else:
                self._rotate_relative(direction, target)
        except Exception as exc:
            command_error = exc
        finally:
            try:
                after = self._read_imu_pose()
            except Exception as exc:
                after = before.copy()
                command_error = command_error or exc
            with self._measurement_lock:
                self._measurement_yaws.append(after["yaw_rad"])
                yaw_samples = self._measurement_yaws.copy()
                self._measurement_active = False

        row = self._calculate_precision_result(
            before=before,
            after=after,
            yaw_samples=yaw_samples,
            pair_type=pair_type,
            direction=direction,
            target=float(target),
        )
        row.update({
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "result_index": result_index,
            "speed_ratio": speed_ratio,
            "control_api": self.control_api,
            "pair_type": pair_type,
            "direction": direction_label,
            "target_value": target,
            "target_unit": unit,
            "group_index": group_index,
            "status": ("error" if command_error else
                       "stopped" if not self._move_running else "success"),
            "error": str(command_error) if command_error else "",
            "duration_s": round(time.monotonic() - started, 6),
            "imu_sample_count": len(yaw_samples),
        })
        return row, command_error

    def _read_imu_pose(self):
        state = self._robot.get_state()
        rs = state.robot_state
        pos = rs.pos_body
        if len(pos) >= 2:
            xyz = [float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) >= 3 else 0.0]
        else:
            xyz = self._read_pos()
        ori = rs.ori_body
        yaw = float(ori[2]) if len(ori) >= 3 else 0.0
        return {"x": xyz[0], "y": xyz[1], "z": xyz[2], "yaw_rad": yaw}

    @classmethod
    def _calculate_precision_result(cls, before, after, yaw_samples, pair_type, direction, target):
        dx = after["x"] - before["x"]
        dy = after["y"] - before["y"]
        dz = after["z"] - before["z"]
        start_yaw = before["yaw_rad"]
        end_yaw = after["yaw_rad"]
        yaw_change = 0.0
        for previous, current in zip(yaw_samples[:-1], yaw_samples[1:]):
            yaw_change += cls._normalize_rad(current - previous)
        yaw_change_deg = math.degrees(yaw_change)

        result = {
            "start_x_m": round(before["x"], 6),
            "start_y_m": round(before["y"], 6),
            "start_z_m": round(before["z"], 6),
            "start_yaw_deg": round(math.degrees(start_yaw), 6),
            "end_x_m": round(after["x"], 6),
            "end_y_m": round(after["y"], 6),
            "end_z_m": round(after["z"], 6),
            "end_yaw_deg": round(math.degrees(end_yaw), 6),
            "delta_x_m": round(dx, 6),
            "delta_y_m": round(dy, 6),
            "delta_z_m": round(dz, 6),
            "expected_distance_m": "", "actual_distance_m": "", "distance_error_m": "",
            "abs_distance_error_m": "", "lateral_error_m": "", "vertical_error_m": "",
            "yaw_drift_deg": "", "expected_angle_deg": "", "actual_angle_deg": "",
            "angle_error_deg": "", "abs_angle_error_deg": "",
            "position_drift_m": round(math.hypot(dx, dy), 6),
        }

        if pair_type in ("前后移动", "左右平移"):
            forward = (math.cos(start_yaw), math.sin(start_yaw))
            left = (-math.sin(start_yaw), math.cos(start_yaw))
            desired = {
                "forward": forward,
                "backward": (-forward[0], -forward[1]),
                "left": left,
                "right": (-left[0], -left[1]),
            }[direction]
            actual = dx * desired[0] + dy * desired[1]
            lateral = dx * (-desired[1]) + dy * desired[0]
            error = actual - target
            result.update({
                "expected_distance_m": round(target, 6),
                "actual_distance_m": round(actual, 6),
                "distance_error_m": round(error, 6),
                "abs_distance_error_m": round(abs(error), 6),
                "lateral_error_m": round(lateral, 6),
                "vertical_error_m": round(dz, 6),
                "yaw_drift_deg": round(cls._normalize_angle(math.degrees(end_yaw - start_yaw)), 6),
            })
        else:
            direction_sign = 1.0 if direction == "left" else -1.0
            actual = direction_sign * yaw_change_deg
            error = actual - target
            result.update({
                "expected_angle_deg": round(target, 6),
                "actual_angle_deg": round(actual, 6),
                "angle_error_deg": round(error, 6),
                "abs_angle_error_deg": round(abs(error), 6),
            })
        return result

    def _log_precision_result(self, row, completed, total):
        if row["pair_type"] == "左右旋转":
            detail = (
                f"目标={row['expected_angle_deg']}° 实际={row['actual_angle_deg']}° "
                f"误差={row['angle_error_deg']}° 位移漂移={row['position_drift_m']}m"
            )
        else:
            detail = (
                f"目标={row['expected_distance_m']}m 实际={row['actual_distance_m']}m "
                f"误差={row['distance_error_m']}m 侧向={row['lateral_error_m']}m "
                f"航向漂移={row['yaw_drift_deg']}°"
            )
        self._log(
            "RESULT",
            f"[{completed}/{total}] {row['speed_ratio']}% {row['direction']} "
            f"第{row['group_index']}组 {detail} 状态={row['status']}",
        )

    @staticmethod
    def _write_precision_summary(records, summary_path):
        grouped = {}
        for row in records:
            key = (
                row["speed_ratio"], row["control_api"], row["pair_type"],
                row["direction"], row["target_value"], row["target_unit"],
            )
            grouped.setdefault(key, []).append(row)
        fields = [
            "speed_ratio", "control_api", "pair_type", "direction", "target_value",
            "target_unit", "record_count", "success_count", "error_count", "error_metric",
            "mean_error", "mean_abs_error", "std_error", "max_abs_error",
        ]
        with summary_path.open("w", newline="", encoding="utf-8-sig") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=fields)
            writer.writeheader()
            for key, rows in grouped.items():
                metric = "angle_error_deg" if key[2] == "左右旋转" else "distance_error_m"
                values = [float(row[metric]) for row in rows if row["status"] == "success"]
                writer.writerow({
                    "speed_ratio": key[0], "control_api": key[1], "pair_type": key[2],
                    "direction": key[3], "target_value": key[4], "target_unit": key[5],
                    "record_count": len(rows), "success_count": len(values),
                    "error_count": len(rows) - len(values), "error_metric": metric,
                    "mean_error": round(statistics.mean(values), 6) if values else "",
                    "mean_abs_error": round(statistics.mean(abs(v) for v in values), 6) if values else "",
                    "std_error": round(statistics.pstdev(values), 6) if values else "",
                    "max_abs_error": round(max(abs(v) for v in values), 6) if values else "",
                })

    # ─── 移动 ─────────────────────────────────────

    def _move(self, direction, distance):
        """按当前选择使用 line_walk 或 velocity_sequence 执行直线移动。"""
        try:
            if self.control_api == "velocity_sequence":
                self._move_by_velocity(direction, distance)
            else:
                # SDK 单条 line_walk 距离上限为 3m；较长距离拆成连续指令。
                remaining = max(0.0, float(distance))
                while remaining > 1e-6 and self._running and self._move_running:
                    chunk = min(remaining, 3.0)
                    if direction == "forward":
                        self._log("API", f"walk_forward(distance={chunk:.2f}m, speed_ratio={self.speed_ratio})")
                        self._robot.walk_forward(chunk, self.speed_ratio, show_progress=False)
                    else:
                        self._log("API", f"walk_backward(distance={chunk:.2f}m, speed_ratio={self.speed_ratio})")
                        self._robot.walk_backward(chunk, self.speed_ratio, show_progress=False)
                    remaining -= chunk
                    self._emit_pos()
        except Exception as e:
            self._log("ERROR", f"移动失败({direction}): {e}")
            raise
        time.sleep(self.settle_time)  # 等待姿态稳定
        self._emit_pos()              # 移动后记录轨迹点

    def _move_by_velocity(self, direction, distance):
        """用 SDK velocity_sequence 的 vx×duration 实现目标移动距离。"""
        distance = max(0.0, float(distance))
        if distance <= 1e-6 or not (self._running and self._move_running):
            return
        vx = self.linear_velocity if direction == "forward" else -self.linear_velocity
        duration = distance / self.linear_velocity
        steps = self._velocity_steps(vx=vx, vy=0.0, vyaw=0.0, duration=duration)
        gait = "wheel_loco" if self._is_wheel else "walk"
        self._log(
            "API",
            f"velocity_sequence(vel_seq=[vx={vx:.2f}, vy=0, vyaw=0, "
            f"duration={duration:.3f}s; stop], gait='{gait}', "
            f"speed_ratio={self.speed_ratio}, stand_down_after=False)",
        )
        self._robot.velocity_sequence(
            steps,
            gait=gait,
            speed_ratio=self.speed_ratio,
            stand_down_after=False,
            show_progress=False,
        )

    def _move_lateral(self, direction, distance):
        """执行左/右平移精度测试，支持 line_walk 和 velocity_sequence。"""
        try:
            if self.control_api == "velocity_sequence":
                distance = max(0.0, float(distance))
                vy = self.linear_velocity if direction == "left" else -self.linear_velocity
                duration = distance / self.linear_velocity
                steps = self._velocity_steps(vx=0.0, vy=vy, vyaw=0.0, duration=duration)
                gait = "wheel_loco" if self._is_wheel else "walk"
                self._log(
                    "API",
                    f"velocity_sequence(vel_seq=[vx=0, vy={vy:.2f}, vyaw=0, "
                    f"duration={duration:.3f}s; stop], gait='{gait}', "
                    f"speed_ratio={self.speed_ratio}, stand_down_after=False)",
                )
                self._robot.velocity_sequence(
                    steps,
                    gait=gait,
                    speed_ratio=self.speed_ratio,
                    stand_down_after=False,
                    show_progress=False,
                )
            else:
                remaining = max(0.0, float(distance))
                while remaining > 1e-6 and self._running and self._move_running:
                    chunk = min(remaining, 3.0)
                    if direction == "left":
                        self._log("API", f"move_left(distance={chunk:.2f}m, speed_ratio={self.speed_ratio})")
                        self._robot.move_left(chunk, self.speed_ratio, show_progress=False)
                    else:
                        self._log("API", f"move_right(distance={chunk:.2f}m, speed_ratio={self.speed_ratio})")
                        self._robot.move_right(chunk, self.speed_ratio, show_progress=False)
                    remaining -= chunk
                    self._emit_pos()
        except Exception as e:
            self._log("ERROR", f"平移失败({direction}): {e}")
            raise
        time.sleep(self.settle_time)
        self._emit_pos()

    def _rotate_relative(self, direction, angle):
        """执行指定方向/角度的相对旋转精度测试，不附加航向矫正。"""
        try:
            if self.control_api == "velocity_sequence":
                vyaw = self.yaw_velocity if direction == "left" else -self.yaw_velocity
                duration = math.radians(float(angle)) / self.yaw_velocity
                steps = self._velocity_steps(vx=0.0, vy=0.0, vyaw=vyaw, duration=duration)
                gait = "wheel_loco" if self._is_wheel else "walk"
                self._log(
                    "API",
                    f"velocity_sequence(vel_seq=[vx=0, vy=0, vyaw={vyaw:.2f}, "
                    f"duration={duration:.3f}s; stop], gait='{gait}', "
                    f"speed_ratio={self.speed_ratio}, stand_down_after=False)",
                )
                self._robot.velocity_sequence(
                    steps,
                    gait=gait,
                    speed_ratio=self.speed_ratio,
                    stand_down_after=False,
                    show_progress=False,
                )
            elif direction == "left":
                self._log("API", f"rotate_left(angle={angle:.2f}°)")
                self._robot.rotate_left(angle, show_progress=False)
            else:
                self._log("API", f"rotate_right(angle={angle:.2f}°)")
                self._robot.rotate_right(angle, show_progress=False)
        except Exception as e:
            self._log("ERROR", f"旋转失败({direction}): {e}")
            raise
        time.sleep(self.settle_time)
        self._emit_pos()

    @staticmethod
    def _velocity_steps(vx, vyaw, duration, vy=0.0):
        """生成最长 3 秒一段并以零速度结尾的速度序列。"""
        steps = []
        remaining = max(0.0, float(duration))
        while remaining > 1e-6:
            chunk = min(remaining, 3.0)
            steps.append((float(vx), float(vy), float(vyaw), chunk))
            remaining -= chunk
        steps.append((0.0, 0.0, 0.0, 0.3))
        return steps

    def _get_yaw(self):
        """从 IMU 融合位姿中读取偏航角（度）"""
        state = self._robot.get_state()
        rpy = state.robot_state.ori_body  # [roll, pitch, yaw] 弧度
        return math.degrees(rpy[2])

    def _set_active_command(self, target, target_yaw, phase, segment):
        """设置当前指令，并立即发布一次；采样线程随后持续刷新当前位置。"""
        self._active_target = tuple(float(v) for v in target[:3])
        self._active_target_yaw = float(target_yaw)
        self._active_phase = phase
        self._active_segment = int(segment)
        self._publish_command_preview()

    def _publish_command_preview(self, current=None, current_yaw=None):
        target = self._active_target
        if target is None:
            return
        try:
            current = self._read_pos() if current is None else current
            current_yaw = self._get_yaw() if current_yaw is None else current_yaw
            dx = target[0] - float(current[0])
            dy = target[1] - float(current[1])
            self.command_preview.emit({
                "current": [float(current[0]), float(current[1]), 0.0],
                "target": [target[0], target[1], 0.0],
                "current_yaw": float(current_yaw),
                "target_yaw": self._active_target_yaw,
                "phase": self._active_phase,
                "segment": self._active_segment,
                "remaining": math.hypot(dx, dy),
                "turn": self._normalize_angle(self._active_target_yaw - float(current_yaw)),
            })
        except Exception:
            pass

    def _clear_command_preview(self):
        self._active_target = None
        self._active_phase = ""
        self.command_preview.emit({})

    def _correct_heading_once(self):
        """移动完一段完整距离后，按当前偏航误差做一次转向矫正

        不做闭环反复修正：只转一次（误差超出阈值时转误差角），
        误差在阈值内则不动。
        """
        try:
            self._turn_to_heading(self._initial_yaw, "航向矫正")
        except Exception as e:
            self._log("ERROR", f"航向矫正失败: {e}")

    def _turn_to_heading(self, target_yaw, context="转向"):
        """按当前 IMU 偏航转到世界坐标目标航向，只执行一次实际误差角。"""
        current_yaw = self._get_yaw()
        turn = self._normalize_angle(float(target_yaw) - current_yaw)
        if abs(turn) <= self.yaw_threshold:
            self._log(
                "INFO",
                f"{context}: 当前 {current_yaw:.2f}°，目标 {target_yaw:.2f}°，"
                f"误差 {turn:.2f}°（在阈值内）",
            )
            return

        direction = "左转" if turn > 0 else "右转"
        self._log(
            "INFO",
            f"{context}: 当前 {current_yaw:.2f}°，目标 {target_yaw:.2f}°，"
            f"{direction} {abs(turn):.2f}°",
        )
        if self.control_api == "velocity_sequence":
            # SDK 速度序列采用标准角速度符号：+vyaw 左转，-vyaw 右转。
            vyaw = self.yaw_velocity if turn > 0 else -self.yaw_velocity
            duration = math.radians(abs(turn)) / self.yaw_velocity
            steps = self._velocity_steps(vx=0.0, vy=0.0, vyaw=vyaw, duration=duration)
            gait = "wheel_loco" if self._is_wheel else "walk"
            self._log(
                "API",
                f"velocity_sequence(vel_seq=[vx=0, vy=0, vyaw={vyaw:.2f}, "
                f"duration={duration:.3f}s; stop], gait='{gait}', "
                f"speed_ratio={self.speed_ratio}, stand_down_after=False)",
            )
            self._robot.velocity_sequence(
                steps,
                gait=gait,
                speed_ratio=self.speed_ratio,
                stand_down_after=False,
                show_progress=False,
            )
        elif turn > 0:
            self._log("API", f"rotate_left(angle={abs(turn):.2f}°)")
            self._robot.rotate_left(abs(turn), show_progress=False)
        else:
            self._log("API", f"rotate_right(angle={abs(turn):.2f}°)")
            self._robot.rotate_right(abs(turn), show_progress=False)
        time.sleep(self.settle_time)
        self._emit_pos()

    # ─── 正方形运动 ────────────────────────────────

    def _run_square(self, cycle, total, targets):
        """逐个追踪正方形顶点：转向目标点，再移动当前位置到目标点的距离。"""
        for i, target in enumerate(targets):
            if not (self._running and self._move_running):
                return
            current = self._read_pos()
            dx = float(target[0]) - float(current[0])
            dy = float(target[1]) - float(current[1])
            remaining = math.hypot(dx, dy)
            self.progress.emit(
                cycle,
                total,
                f"正方形 第{i + 1}/4 边 → 目标({target[0]:.2f}, {target[1]:.2f})",
            )
            if remaining <= self.position_threshold:
                self._log(
                    "INFO",
                    f"目标点 {i + 1}: 已在目标范围内，剩余 {remaining:.3f}m",
                )
                continue

            target_yaw = math.degrees(math.atan2(dy, dx))
            self._set_active_command(target, target_yaw, "turn", i + 1)
            self._log(
                "INFO",
                f"目标点 {i + 1}: ({target[0]:.3f}, {target[1]:.3f})，"
                f"当前位置 ({current[0]:.3f}, {current[1]:.3f})，"
                f"目标航向 {target_yaw:.2f}°",
            )
            self._turn_to_heading(target_yaw, f"转向目标点 {i + 1}")
            if not (self._running and self._move_running):
                return

            # 转向可能带来轻微位移，移动前重新计算到同一目标点的距离。
            current = self._read_pos()
            remaining = math.hypot(
                float(target[0]) - float(current[0]),
                float(target[1]) - float(current[1]),
            )
            if remaining > self.position_threshold:
                self._set_active_command(target, target_yaw, "move", i + 1)
                self._log("INFO", f"移动到目标点 {i + 1}: 剩余距离 {remaining:.3f}m")
                self._move("forward", remaining)

        # 回到起点后恢复初始朝向，下一循环仍追踪同一组世界坐标顶点。
        if self._running and self._move_running:
            self.progress.emit(cycle, total, "正方形完成，转回初始方向")
            current = self._read_pos()
            self._set_active_command(current, self._initial_yaw, "turn", 0)
            self._correct_heading_once()
            self._clear_command_preview()

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
                rpy_valid = True
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
                    rpy_valid = False
                    imu["rpy"] = [0.0, 0.0, 0.0]
                    imu["rpy_abs"] = [0.0, 0.0, 0.0]

                with self._measurement_lock:
                    if self._measurement_active and rpy_valid:
                        self._measurement_yaws.append(float(imu["rpy_abs"][2]))

                self.imu_data.emit(imu)
                if self._active_target is not None:
                    self._publish_command_preview(
                        current=imu["pos"],
                        current_yaw=math.degrees(imu["rpy_abs"][2]),
                    )
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
