# Dobot Quad SDK 介绍

## 一、概述

**Dobot Quad SDK** 是越疆科技（Dobot Robotics）推出的四足机器人二次开发套件。它提供了一套完整的高性能机器人控制接口，支持点足（Legged）与轮足（Wheel-Legged）两种构型，帮助开发者快速构建基于 Dobot 四足机器人的应用程序。

### 适用机器人型号

| 型号 | 构型 | 说明 |
|------|------|------|
| **MINI_QUAD** | 点足（Legged） | 标准四足机器人，支持行走、小跑、跳跃、后空翻等动作 |
| **MINI_QUAD_WHEEL** | 轮足（Wheel-Legged） | 轮腿复合机器人，兼具轮式移动与足式越障能力 |

SDK 能够自动检测连接的机器人类型（`is_quad_wheel()`），同一套 API 可根据构型自适应切换可用指令。

---

## 二、架构设计

SDK 采用**双层解耦架构**，将机器人控制抽象为两个独立层级，均同时提供 **Python** 和 **C++** 接口：

```
┌──────────────────────────────────────────────────┐
│                  您的应用程序                       │
├──────────────────────────────────────────────────┤
│                 Dobot Quad SDK                    │
├─────────────────────┬────────────────────────────┤
│  高层控制 (gRPC)     │   底层控制 (CycloneDDS)     │
│  · 状态机管理         │   · RGB / 深度相机          │
│  · 运动规划与执行      │   · IMU / 电机 / 电池      │
│  · 速度序列控制       │   · LED 灯效               │
│  · 平衡姿态控制       │   · 语音播放与采集          │
│  · 轮足运动模式       │   · 直接电机控制            │
│  · 机器人状态查询      │                            │
├─────────────────────┴────────────────────────────┤
│        gRPC + CycloneDDS 通信层                   │
├──────────────────────────────────────────────────┤
│              机器人主控系统                         │
└──────────────────────────────────────────────────┘
```

### 2.1 高层控制（gRPC）

通过 **gRPC** 协议与机器人主控程序通信，提供面向任务的运动规划接口。开发者无需关注底层运动学与动力学细节。

**核心功能：**

| 功能 | 说明 |
|------|------|
| **状态机管理** | 20+ 状态（PASSIVE、READY、STAND_DOWN、BALANCE_STAND、WALK、FLYING_TROT 等），支持手动切换与自动寻路 |
| **运动序列执行** | 单个动作或复合运动序列编排，实时返回执行进度，支持 Ctrl+C 安全中断 |
| **速度序列控制** | 时间序列指令 `(vx, vy, vyaw, duration)`，适用于自主导航集成 |
| **平衡姿态控制** | 独立调节俯仰/偏航/横滚/机身高度，支持动态/静态姿态（仅点足） |
| **轮足运动控制** | `wheel_loco()`、`drift()`、`handstand()` 等轮足专用功能 |
| **状态查询** | 关节状态、机体姿态、足端力、电池、FSM 状态等实时数据 |
| **安全机制** | `enable_safety_ready()` 在程序退出时自动切换至安全状态 |
| **构型检测** | `is_quad_wheel()` 自动识别机器人型号 |

### 2.2 底层控制（CycloneDDS）

通过 **Eclipse Cyclone DDS** 实时发布/订阅中间件直接访问硬件，**不依赖机器人主控程序**，提供最高级别的硬件访问权限。

**核心功能：**

| 功能 | 说明 |
|------|------|
| **RGB 相机** | 订阅前后摄像头 JPEG 图像流 |
| **深度相机** | 订阅 16 位深度图，支持伪彩色可视化 |
| **IMU 数据** | 四元数、陀螺仪、加速度计、欧拉角 |
| **电机状态** | 16 个电机的位置/速度/力矩/温度，1kHz 采样 |
| **BMS 电池** | 实时电池电量 |
| **LED 灯效** | 6 颗独立 RGB LED，支持呼吸效果 |
| **语音播放** | WAV/FLAC/MP3 文件播放或实时 PCM 流推送 |
| **语音采集** | 24kHz/16-bit/单声道麦克风音频 |
| **直接电机控制** | 位置/速度/力矩指令，可配置 PID 增益 |

> ⚠️ 直接电机控制前须使用 `kill_robot` 工具停止主控程序。

---

## 三、多语言支持

所有功能均提供 Python 和 C++ 完整实现，API 设计保持一致：

| 特性 | Python | C++ |
|------|--------|-----|
| 高层客户端库 | `dobot_quad` 包（pip 安装） | `robot_client.h` 头文件库（CMake 构建） |
| 高层示例 | 10 个 | 11 个（含 kill_robot） |
| 底层示例 | 9 个 | 9 个 |
| 单元测试 | pytest | GoogleTest |

---

## 四、快速上手

### 环境要求

- **OS**: Ubuntu 22.04
- **Python**: 3.10+, **CMake**: 3.16+, **GCC/G++**: 9+
- **OpenCV**: 4.5.4

### 网络连接

| 方式 | 机器人 IP | 子网 | 说明 |
|------|-----------|------|------|
| **有线** | `192.168.5.2` | PC 设为 `192.168.5.xxx/24` | DDS 必须用有线 |
| **WiFi** (`Rover-*`, 密码 `12345678`) | `192.168.1.6` | 自动 | 仅 gRPC |

### 安装

```bash
# 高层 Python
cd high_level/python && pip install .

# 高层 C++
sudo apt-get install -y libgrpc++-dev protobuf-compiler-grpc libprotobuf-dev pkg-config
cd high_level/cpp && mkdir -p build && cd build && cmake .. && make -j

# DDS 中间件
cd dist && sudo dpkg -i dds-middleware-with-thirdparty*.deb
export CYCLONEDDS_HOME="/usr/local/"

# 底层 Python
sudo apt install -y cyclonedds-dev
pip install dds_middleware_python-*.whl cyclonedds opencv-python

# 底层 C++
sudo apt install -y libboost-dev libopencv-dev libyaml-cpp-dev cmake build-essential
cd low_level/cpp && mkdir -p build && cd build && cmake .. && make -j
```

配置 DDS 网络（`cyclonedds.xml` 中替换网卡名）：

```bash
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds.xml
cyclonedds ps   # 验证
```

### 运行示例

```bash
# 高层：查询动作
python3 high_level/python/examples/e1_get_available_motions.py

# 底层：订阅 IMU
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds.xml
python3 low_level/python/e4_imu_state_sub.py
```

---

## 五、项目结构

```
dobot_quad_sdk/
├── high_level/           # gRPC 高层控制
│   ├── cpp/              # C++ 客户端库 + 示例
│   ├── python/           # pip 可安装的 Python 包 + 示例
│   └── test/             # 单元测试
├── low_level/            # DDS 底层控制
│   ├── cpp/              # C++ 示例
│   └── python/           # Python 示例
├── resources/            # URDF 模型文件
├── docs/                 # MkDocs 文档站点
├── assets/               # 封面图 + 测试音频
├── dist/                 # 预编译 DDS 中间件
├── utils/                # 工具脚本
├── Dockerfile            # Docker 构建
├── cyclonedds.xml        # DDS 网络配置
└── pyproject.toml        # Python 工具配置
```

---

## 六、技术栈

| 技术 | 用途 |
|------|------|
| **gRPC** (Protocol Buffers) | 高层控制通信协议 |
| **Eclipse Cyclone DDS** | 底层实时发布/订阅中间件 |
| **OpenCV 4.5.4** | 图像采集与处理 |
| **MkDocs** (Material 主题) | 文档站点生成 |
| **CMake 3.16+** | C++ 构建系统 |
| **pytest** | Python 单元测试 |
| **GoogleTest** | C++ 单元测试 |

---

## 七、主要特性

- **双层解耦架构** — 高层与底层独立运作，按需选择控制粒度
- **双构型兼容** — 点足与轮足自动适配
- **双语言支持** — Python + C++ 完全对应
- **实时高性能** — CycloneDDS 微秒级延迟
- **丰富示例** — 19 个可运行示例覆盖核心功能
- **安全设计** — 多层保护机制
- **完善文档** — 中英双语 API 文档
- **MIT 许可** — 自由使用与分发

---

## 八、许可证

本 SDK 基于 **MIT License** 开源。

---

<div align="center">
<sub>越疆科技 Dobot Robotics — Dobot Quad SDK</sub>
</div>
