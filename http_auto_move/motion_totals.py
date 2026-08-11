"""自动动作总里程与总用时统计。"""

from __future__ import annotations

import math
from collections.abc import Sequence


class MotionTotals:
    """累计单次自动动作的实际平面里程和经过时间。"""

    def __init__(self) -> None:
        self.distance_m = 0.0
        self.elapsed_s = 0.0
        self._started_at: float | None = None
        self._last_xy: tuple[float, float] | None = None

    @property
    def running(self) -> bool:
        return self._started_at is not None

    def start(
        self,
        now: float,
        position: Sequence[float] | None = None,
    ) -> None:
        self.distance_m = 0.0
        self.elapsed_s = 0.0
        self._started_at = float(now)
        self._last_xy = self._xy(position)

    def observe_position(self, position: Sequence[float]) -> None:
        """记录一个世界坐标点；首点作为里程基准，不产生距离。"""
        if not self.running:
            return
        current = self._xy(position)
        if current is None:
            return
        if self._last_xy is not None:
            self.distance_m += math.hypot(
                current[0] - self._last_xy[0],
                current[1] - self._last_xy[1],
            )
        self._last_xy = current

    def elapsed(self, now: float) -> float:
        if self._started_at is None:
            return self.elapsed_s
        return max(0.0, float(now) - self._started_at)

    def stop(self, now: float) -> None:
        if self._started_at is None:
            return
        self.elapsed_s = self.elapsed(now)
        self._started_at = None

    @staticmethod
    def _xy(position: Sequence[float] | None) -> tuple[float, float] | None:
        if position is None or len(position) < 2:
            return None
        try:
            x, y = float(position[0]), float(position[1])
        except (TypeError, ValueError):
            return None
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        return x, y
