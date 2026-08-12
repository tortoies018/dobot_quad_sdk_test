# 说明移动里程与运行时间统计模块的职责。
"""自动动作总里程与总用时统计。"""

# 导入本模块所需的库、类型和外部组件。
from __future__ import annotations

# 导入本模块所需的库、类型和外部组件。
import math
from collections.abc import Sequence


# 累计一次运行期间的移动距离和耗时。
class MotionTotals:
    """累计单次自动动作的实际平面里程和经过时间。"""

    # 初始化对象状态以及运行所需的资源。
    def __init__(self) -> None:
        self.distance_m = 0.0
        self.elapsed_s = 0.0
        self._started_at: float | None = None
        self._last_xy: tuple[float, float] | None = None

    # 返回当前是否正在累计移动统计。
    @property
    def running(self) -> bool:
        return self._started_at is not None

    # 开始一轮新的移动距离和耗时统计。
    def start(
        self,
        now: float,
        position: Sequence[float] | None = None,
    ) -> None:
        self.distance_m = 0.0
        self.elapsed_s = 0.0
        self._started_at = float(now)
        self._last_xy = self._xy(position)

    # 根据连续位置样本累计实际移动距离。
    def observe_position(self, position: Sequence[float]) -> None:
        """记录一个世界坐标点；首点作为里程基准，不产生距离。"""
        # 必要条件或数据不满足时执行安全处理。
        if not self.running:
            return
        current = self._xy(position)
        # 必要条件或数据不满足时执行安全处理。
        if current is None:
            return
        # 必要条件或数据不满足时执行安全处理。
        if self._last_xy is not None:
            self.distance_m += math.hypot(
                current[0] - self._last_xy[0],
                current[1] - self._last_xy[1],
            )
        self._last_xy = current

    # 计算当前统计周期已经经过的时间。
    def elapsed(self, now: float) -> float:
        # 必要条件或数据不满足时执行安全处理。
        if self._started_at is None:
            return self.elapsed_s
        return max(0.0, float(now) - self._started_at)

    # 结束统计并固定最终累计时间。
    def stop(self, now: float) -> None:
        # 必要条件或数据不满足时执行安全处理。
        if self._started_at is None:
            return
        self.elapsed_s = self.elapsed(now)
        self._started_at = None

    # 从位置向量中安全提取平面坐标。
    @staticmethod
    def _xy(position: Sequence[float] | None) -> tuple[float, float] | None:
        # 必要条件或数据不满足时执行安全处理。
        if position is None or len(position) < 2:
            return None
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            x, y = float(position[0]), float(position[1])
        # 捕获异常并执行日志记录或安全降级。
        except (TypeError, ValueError):
            return None
        # 必要条件或数据不满足时执行安全处理。
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        return x, y
