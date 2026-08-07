"""摇杆方向映射与开环时间换算。"""

from __future__ import annotations


STICK_MAX = 32767


def direction_axes(direction: str, amplitude: int) -> dict[str, int]:
    """按常见手柄坐标生成 MH4 摇杆字段。

    文档没有声明正负方向；这里采用“前/左为负，后/右为正”的常见
    屏幕摇杆坐标。GUI 和 README 会要求首次低幅值验证。
    """
    value = max(1, min(STICK_MAX, abs(int(amplitude))))
    axes = {"move_x": 0, "move_y": 0, "turn_x": 0, "turn_y": 0}
    mapping = {
        "forward": ("move_y", -value),
        "backward": ("move_y", value),
        "left": ("move_x", -value),
        "right": ("move_x", value),
        "rotate_left": ("turn_x", -value),
        "rotate_right": ("turn_x", value),
    }
    try:
        axis, axis_value = mapping[direction]
    except KeyError as exc:
        raise ValueError(f"未知方向: {direction}") from exc
    axes[axis] = axis_value
    return axes


def scaled_duration(target: float, full_stick_rate: float, amplitude: int) -> float:
    """按线性摇杆假设，把距离或角度换算成开环持续时间。"""
    target = abs(float(target))
    full_stick_rate = abs(float(full_stick_rate))
    fraction = min(STICK_MAX, max(1, abs(int(amplitude)))) / STICK_MAX
    if target <= 0:
        raise ValueError("目标值必须大于 0")
    if full_stick_rate <= 0:
        raise ValueError("标定速度必须大于 0")
    return target / (full_stick_rate * fraction)

