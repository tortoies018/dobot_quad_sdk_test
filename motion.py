# 说明移动方向到摇杆轴的映射职责。
"""HTTP 摇杆方向映射。"""

# 导入本模块所需的库、类型和外部组件。
from __future__ import annotations


# 定义本模块后续逻辑使用的常量或默认配置。
STICK_MAX = 32767


# 把方向名称转换为对应的摇杆轴数值。
def direction_axes(direction: str, amplitude: int) -> dict[str, int]:
    """按常见手柄坐标生成 MH4 摇杆字段。

    方向来自点足 miniQuad 实机标定：move_y 正值前进、负值后退；
    move_x 负值左移；turn_x 负值使 yaw 增大（左转）。
    """
    value = max(1, min(STICK_MAX, abs(int(amplitude))))
    axes = {"move_x": 0, "move_y": 0, "turn_x": 0, "turn_y": 0}
    mapping = {
        "forward": ("move_y", value),
        "backward": ("move_y", -value),
        "left": ("move_x", -value),
        "right": ("move_x", value),
        "rotate_left": ("turn_x", -value),
        "rotate_right": ("turn_x", value),
    }
    # 尝试执行可能失败的操作并交由异常分支处理。
    try:
        axis, axis_value = mapping[direction]
    # 捕获异常并执行日志记录或安全降级。
    except KeyError as exc:
        raise ValueError(f"未知方向: {direction}") from exc
    axes[axis] = axis_value
    return axes
