# Dobot Quad SDK Python API 参考

## 一、高层控制（gRPC）

### 1.1 初始化

```python
from dobot_quad import RobotClient

robot = RobotClient(addr="192.168.5.2:50051")
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `addr` | string | `"192.168.5.2:50051"` | gRPC 服务地址 |

**上下文管理器（推荐）：**
```python
with RobotClient("192.168.5.2:50051") as robot:
    robot.balance_stand()
```

### 1.2 查询接口

| API | 返回 | 说明 |
|-----|------|------|
| `get_state()` | `StateResponse` | 完整遥测状态快照（FSM 状态、速度比、避障状态、关节/机体/接触力遥测） |
| `get_motions()` | `GetMotionsResponse` | 服务端注册的动作库列表 |
| `get_current_state_name()` | `string` | 当前 FSM 状态名 |
| `get_speed_ratio()` | `int` | 当前速度比 [10, 100] |
| `get_obstacle_avoidance()` | `bool` | 避障是否激活 |
| `get_robot_type()` | `string` | 机器人类型：`"miniQuad"`(点足) / `"miniQuadW"`(轮足) |
| `is_quad()` | `bool` | 是否点足机器人 |
| `is_quad_wheel()` | `bool` | 是否轮足机器人 |

**`get_state()` 返回的 `RobotState` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `jpos_leg / jpos_leg_des` | float[] | 腿部关节位置/期望位置 (rad) |
| `jvel_leg / jvel_leg_des` | float[] | 腿部关节速度/期望速度 (rad/s) |
| `jtau_leg / jtau_leg_des` | float[] | 腿部关节力矩/期望力矩 (Nm) |
| `pos_body` | float[3] | 机体位置 [x, y, z] (m) |
| `vel_body` | float[3] | 机体线速度 (m/s) |
| `acc_body` | float[3] | 机体线加速度 (m/s²) |
| `omega_body` | float[3] | 机体角速度 (rad/s) |
| `ori_body` | float[3] | 机体姿态 [roll, pitch, yaw] (rad) |
| `grf_left / grf_right` | float[3] | 左/右脚地面反力 (N) |
| `grf_vertical_filtered` | float[2] | 滤波后垂直接触力 (N) |

### 1.3 配置接口

| API | 参数 | 说明 |
|-----|------|------|
| `set_speed_ratio(ratio)` | `ratio: int` [10, 100] | 设置速度比，自动钳位 |
| `set_obstacle_avoidance(enable)` | `enable: bool / "on" / "off"` | 启用/禁用避障 |

### 1.4 状态切换（点足 & 轮足通用）

| API | 说明 |
|-----|------|
| `passive()` | 被动模式（电机断电） |
| `emergency()` | 紧急停止（`passive()` 别名） |
| `ready()` | 缓慢趴下（安全停止） |
| `stand_down()` | 趴下 |
| `balance_stand()` | 平衡站立 |
| `walk()` | 切换到行走模式 |
| `flying_trot()` | 切换到奔跑模式 |
| `rl()` | 切换到 RL 模式 |
| `choreo()` | 切换到编舞状态 |
| `change_mode()` | 切换腿部构型（平行 ↔ X 型） |
| `dance()` / `dance0()` | 跳舞 |
| `jump()` | 跳跃 |
| `wave_hand(duration=5.0)` / `wave()` | 打招呼 |
| `backflip()` | 后空翻 |
| `recovery()` | 恢复/自救 |
| `climb()` | 爬行 |
| `set_target_state(state_name)` | 按名称切换状态（大小写不敏感） |

### 1.5 状态切换（轮足专用）

| API | 说明 |
|-----|------|
| `wheel_loco()` | 轮式运动 |
| `drift()` | 漂移模式 |
| `handstand()` | 倒立 |

### 1.6 动作执行

```python
robot.execute("motion_id")                     # 单个动作
robot.execute(("motion_id", {"key": val}))      # 带参数
robot.execute("m1", "m2", loop=True)            # 序列 + 循环
```

### 1.7 速度序列

```python
robot.velocity_sequence(
    vel_seq,                                    # 列表: [(vx, vy, vyaw, dur), ...]
    gait="walk",                                # walk / flying_trot / rl / wheel_loco
    speed_ratio=None,                           # 可选 [10, 100]
    stand_down_after=True,                      # 执行后是否趴下
)
```

### 1.8 直线行走

| API | 等价调用 | 说明 |
|-----|----------|------|
| `line_walk(direction, distance, speed_ratio=None)` | - | direction: 0=forward, 1=backward, 2=left, 3=right |
| `walk_forward(distance, speed_ratio=None)` | `line_walk(0, distance)` | 向前走，distance: [0, 3] m |
| `walk_backward(distance, speed_ratio=None)` | `line_walk(1, distance)` | 向后走 |
| `move_left(distance, speed_ratio=None)` | `line_walk(2, distance)` | 向左移动 |
| `move_right(distance, speed_ratio=None)` | `line_walk(3, distance)` | 向右移动 |

### 1.9 旋转控制

| API | 参数 | 说明 |
|-----|------|------|
| `rotate(direction, angle)` | direction: "left"/"right" 或 0/1, angle: [0, 360]° | 原地旋转 |
| `rotate_left(angle)` | angle: [0, 360]° | 左转 |
| `rotate_right(angle)` | angle: [0, 360]° | 右转 |
| `circle(direction, turns)` | turns: [1, 10] | 旋转指定圈数 |
| `rotate_walk(angle, distance)` | angle: [-180, 180]°, distance: [0, 3] m | 朝指定方向行走 |

### 1.10 平衡控制（仅点足）

| API | 参数范围 | 说明 |
|-----|----------|------|
| `balance_pitch(value, duration=2.0, mode="dynamic")` | value: [-15, 15]° | 俯仰（>0 前倾） |
| `balance_yaw(value, duration=2.0, mode="dynamic")` | value: [-20, 20]° | 偏航（>0 右看） |
| `balance_roll(value, duration=2.0, mode="dynamic")` | value: [-30, 30]° | 横滚（>0 左倾） |
| `balance_height(value, duration=2.0, mode="dynamic")` | value: [-0.12, 0] m | 高度（<0 下蹲） |
| `balance_neutral(duration=2.0)` | - | 回到中位 |
| `balance_sequence(motions)` | - | 批量执行平衡动作 |
| `dynamic_pose(duration, roll_deg, pitch_deg, yaw_deg, height_m)` | duration: [1, 5] s | 复合姿势（正弦扫描） |
| `static_pose(duration, roll_deg, pitch_deg, yaw_deg, height_m)` | duration: [1, 5] s | 复合姿势（斜坡 → 保持 → 回中） |

**`mode` 参数：** `"dynamic"` — 正弦扫描到目标值后保持；`"static"` — 斜坡到目标值，保持，斜坡回中。

### 1.11 安全接口

| API | 说明 |
|-----|------|
| `enable_safety_ready()` | 注册 Ctrl+C 处理器，退出前自动切到 ready 状态 |

---

## 二、底层控制（DDS）

### 2.1 初始化

```python
import dds_middleware_python as dds

middleware = dds.PyDDSMiddleware("config/dds_config.yaml")   # YAML 配置文件
middleware = dds.PyDDSMiddleware(0)                           # Domain ID
```

### 2.2 QoS 配置

| 参数 | 可选值 | 说明 |
|------|--------|------|
| `reliability` | `reliable` / `best_effort` | reliable 保证到达，best_effort 允许丢包 |
| `history_kind` | `keep_last` / `keep_all` | 保留策略 |
| `history_depth` | 整数 | 保留的历史消息数 |
| `durability` | `volatile` / `transient_local` | 持久性策略 |

**推荐配置：**

| 场景 | reliability | history_depth |
|------|-------------|---------------|
| 传感器数据 | best_effort | 1-5 |
| 控制指令 | reliable | 1-5 |
| 图像数据 | best_effort | 1-5 |

### 2.3 发布者 API

| API | 话题 | 说明 |
|-----|------|------|
| `createLedsCmdWriter(topic, qos)` | `rt/leds/cmd` | 创建 LED 控制发布者 |
| `createLowerCmdWriter(topic, qos)` | `rt/lower/cmd` | 创建电机指令发布者 |
| `createVoiceCmdWriter(topic, qos)` | `rt/voice/cmd` | 创建语音指令发布者 |
| `publishLedsCmd(cmd)` | - | 发布 LED 控制指令 |
| `publishLowerCmd(cmd)` | - | 发布电机控制指令 |
| `publishVoiceCmd(cmd)` | - | 发布语音指令 |

### 2.4 订阅者 API

| API | 话题 | 回调参数 | 说明 |
|-----|------|----------|------|
| `subscribeCompressedImage(topic, callback)` | `rt/camera/camera2/image_compressed`<br>`rt/camera/camera3/image_compressed` | `CompressedImage` | 订阅 RGB 压缩图像 |
| `subscribeImage(topic, callback, qos)` | `rt/camera/camera2/image_depth`<br>`rt/camera/camera3/image_depth` | `Image` | 订阅深度图像 |
| `subscribeLowerState(topic, callback)` | `rt/lower/state` | `LowerState` | 订阅底层状态（IMU/电机/BMS） |
| `subscribeVoiceState(topic, callback, qos)` | `rt/voice/state` | `VoiceState` | 订阅语音状态 |

### 2.5 数据结构

| 类 | 字段/方法 | 说明 |
|-----|-----------|------|
| `dds.Header` | `stamp()`, `frame_id()` | 消息头 |
| `dds.Time` | `sec()`, `nanosec()` | 时间戳 |
| `dds.LedsCmd` | `leds(list)` | LED 控制指令集合 |
| `dds.LEDControl` | `name()`, `mode()`, `brightness()`, `r()`, `g()`, `b()`, `priority()` | 单 LED 控制 |
| `dds.LowerCmd` | `[hw].mode()`, `[hw].q()`, `[hw].dq()`, `[hw].tau()`, `[hw].kp()`, `[hw].kd()` | 电机控制指令（索引访问 16 个电机） |
| `dds.VoiceCmd` | `header()`, `priority()`, `task_id()`, `type()`, `path()`, `data()`, `flag()` | 语音指令 |
| `dds.VoicePriority` | `.kNormal` | 语音优先级 |

### 2.6 话题总览

| 话题 | 类型 | 方向 | 频率 | 说明 |
|------|------|------|------|------|
| `rt/camera/camera2/image_compressed` | `CompressedImage` | 订阅 | - | 前置 RGB 相机 |
| `rt/camera/camera3/image_compressed` | `CompressedImage` | 订阅 | - | 后置 RGB 相机 |
| `rt/camera/camera2/image_depth` | `Image` | 订阅 | - | 前置深度相机（16UC1） |
| `rt/camera/camera3/image_depth` | `Image` | 订阅 | - | 后置深度相机（16UC1） |
| `rt/lower/state` | `LowerState` | 订阅 | ~1kHz | 底层状态（IMU、16 电机、BMS） |
| `rt/voice/state` | `VoiceState` | 订阅 | - | 语音采集流 |
| `rt/leds/cmd` | `LedsCmd` | 发布 | - | LED 控制指令 |
| `rt/lower/cmd` | `LowerCmd` | 发布 | - | 电机控制指令 |
| `rt/voice/cmd` | `VoiceCmd` | 发布 | - | 语音播放指令 |

### 2.7 IMU 数据字段

`imu_state` 对象：

| 方法 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `quaternion()` | float[4] | - | 姿态四元数 [w, x, y, z] |
| `gyroscope()` | float[3] | rad/s | 角速度 [x, y, z] |
| `accelerometer()` | float[3] | m/s² | 加速度 [x, y, z] |
| `rpy()` | float[3] | rad | 欧拉角 [roll, pitch, yaw] |

### 2.8 电机数据字段

`motor_state[i]` 对象（i=0..15）：

| 方法 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `mode()` | uint8 | - | 0=失能, 1=报错, 2=掉线, 3=使能, 4=受控, 5=回零 |
| `q()` | float | rad | 角位置 |
| `dq()` | float | rad/s | 角速度 |
| `ddq()` | float | rad/s² | 角加速度 |
| `tau_est()` | float | Nm | 估计力矩 |
| `q_raw()` | float | rad | 原始角位置 |
| `dq_raw()` | float | rad/s | 原始角速度 |
| `ddq_raw()` | float | rad/s² | 原始角加速度 |
| `motor_temp()` | uint8 | °C | 电机温度 |

**电机编号：**

| 腿部 | 电机 ID |
|------|---------|
| 前左腿 | 0, 1, 2, 3 |
| 前右腿 | 4, 5, 6, 7 |
| 后左腿 | 8, 9, 10, 11 |
| 后右腿 | 12, 13, 14, 15 |

### 2.9 电机指令字段

`LowerCmd[hw]` 对象（hw=0..15）：

| 方法 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `mode()` | uint8 | - | 控制模式 |
| `q(val)` | float | rad | 目标位置 |
| `dq(val)` | float | rad/s | 目标速度 |
| `tau(val)` | float | Nm | 前馈力矩 |
| `kp(val)` | float | - | 位置增益 |
| `kd(val)` | float | - | 速度增益 |

**控制公式：** `τ = kp × (q_des - q) + kd × (dq_des - dq) + τ_ff`

### 2.10 LED 名称

| LED 名称 | 位置 | 说明 |
|----------|------|------|
| `leg_light1` ~ `leg_light4` | 腿部 | RGB 灯 |
| `fill_light1` | 前方 | 前照灯 |
| `fill_light3` | 后方 | 后照灯 |
| `fill_light2` | - | 暂未开放 |

---

## 三、参数范围速查

| 参数 | 范围 | 涉及函数 |
|------|------|----------|
| `speed_ratio` | [10, 100] | `set_speed_ratio`, `line_walk`, `velocity_sequence`, `rotate_walk` |
| `distance` | **[0, 3]** m | `walk_forward/backward`, `move_left/right`, `rotate_walk` |
| `rotate angle` | [0, 360]° | `rotate`, `rotate_left/right` |
| `rotate_walk angle` | **[-180, 180]**° | `rotate_walk` |
| `turns` | **[1, 10]** | `circle` |
| balance rpy | roll: [-30, 30]°, pitch: [-15, 15]°, yaw: [-20, 20]° | `balance_pitch/yaw/roll`, `balance_sequence`, `dynamic_pose`, `static_pose` |
| balance height | [-0.12, 0] m | `balance_height`, `balance_sequence`, `dynamic_pose`, `static_pose` |
| balance duration | [0.5, 5] s | 所有 `balance_*` 函数 |
| pose duration | [1, 5] s | `dynamic_pose`, `static_pose` |
| `obstacle_avoidance` | bool / "on" / "off" | `set_obstacle_avoidance` |

---

## 四、运行示例

### 高层控制

```bash
cd dobot_quad_sdk/high_level/python

# E1: 获取可用动作
python3 examples/e1_get_available_motions.py

# E3: 自动状态切换
python3 examples/e3_auto_state_switch.py

# E4: 速度序列
python3 examples/e4_velocity_sequence.py

# E7: 直线行走
python3 examples/e7_line_walk.py

# E10: 配置演示（速度比/避障）
python3 examples/e10_config_demo.py

# kill_robot: 安全停止主控程序
python3 examples/kill_robot.py 192.168.5.2:50051
```

### 底层控制

```bash
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds.xml
cd dobot_quad_sdk/low_level/python

# E1: RGB 图像订阅
python3 e1_rgb_image_sub.py

# E4: IMU 数据
python3 e4_imu_state_sub.py

# E5: 电机状态
python3 e5_motor_state_sub.py

# E6: 电池状态
python3 e6_bms_state_sub.py

# E7: 语音播放（file/streaming 模式）
python3 e7_voice_pub.py file
python3 e7_voice_pub.py streaming

# E8: 语音采集
python3 e8_voice_sub.py
```

---

## 五、网络连接

| 方式 | 机器人 IP | PC 配置 | 说明 |
|------|-----------|---------|------|
| **有线** | `192.168.5.2` | `192.168.5.xxx/24` | DDS（底层）必须用有线 |
| **WiFi** | `192.168.1.6` | 自动 | 仅 gRPC（高层） |

**DDS 环境变量：**
```bash
export CYCLONEDDS_HOME="/usr/local/"
export CYCLONEDDS_URI="file:///path/to/cyclonedds.xml"
```
