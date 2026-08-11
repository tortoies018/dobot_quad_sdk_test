# Dobot Quad SDK 测试与控制工具集

本项目是一组面向 Dobot 四足/轮足机器人的 Python 桌面工具，覆盖高层 gRPC
控制、底层 DDS 数据订阅、MH4 HTTP 控制、相机标定、AprilTag 定位、状态监控、
自动移动和运动精度记录。各目录是独立程序，共用本地 `dobot_quad_sdk`、机器人
网络和 Qt/OpenGL 运行环境。

> **安全提示**
>
> 项目包含行走、旋转、急停解除、后空翻、底层控制等真实机器人指令。首次运行
> 必须在开阔场地使用低速度/低摇杆幅值，设置实体隔离区，并安排人员随时执行
> 实体急停或断电。HTTP 随机巡逻的围栏是依赖定位数据的软件保护，不能替代实体
> 围栏、避障系统或现场监护。

## 项目组成

机器人与本项目之间有三条相互独立的通信链路：

```text
Dobot 机器人
├── gRPC :50051 ── 高层状态、规划动作、实际世界坐标
├── DDS / CycloneDDS ── RGB/深度相机、IMU、电机、电池、语音
└── HTTP :22000 / :22002 ── MH4 摇杆、状态、配置及算法接口
```

| 目录 | 功能 | 通信方式 | 启动命令 |
| --- | --- | --- | --- |
| `quad_camera_app/` | 前后 RGB/深度四画面，以及 IMU、电池、电机、语音仪表盘 | DDS | `python3 quad_camera_app/main.py` |
| `camera_calib/` | 单相机棋盘格标定，支持 DDS 相机和本地 USB 相机 | DDS / OpenCV | `python3 camera_calib/main.py` |
| `camera_calib2/` | 前后 RGB 双相机同时预览、分别采样和标定 | DDS | `python3 camera_calib2/main.py` |
| `apriltag_tracker/` | AprilTag 36h11 检测、PnP 定位、轨迹、录像和视频逐帧回放 | DDS / 视频文件 | `python3 apriltag_tracker/main.py` |
| `high_level_monitor/` | 机器人状态、关节/接触力、3D 位姿和四相机只读监控 | gRPC + DDS | `python3 high_level_monitor/main.py` |
| `command_center/` | 状态切换、动作控制、四相机、3D 轨迹和指令日志 | gRPC + DDS | `python3 command_center/main.py` |
| `auto_move/` | gRPC 动作 API 测试、循环移动、自动回中和精度 CSV | gRPC | `python3 auto_move/main.py` |
| `http_auto_move/` | HTTP 摇杆动作、范围限制、随机巡逻、软急停及全 HTTP API 控制台 | HTTP + 只读 gRPC | `python3 -m http_auto_move.main` |
| `dobot_quad_intro/` | SDK 介绍和 API 速查资料 | — | 直接阅读 Markdown |
| `dobot_quad_sdk/` | 官方 SDK 的本地副本，提供 `dobot_quad` 和 DDS 中间件 | gRPC + DDS | 参见其自带文档 |

`http_auto_move/` 的所有参数和 HTTP 接口说明见
[http_auto_move/README.md](http_auto_move/README.md)。

## 环境要求

- Ubuntu 22.04；
- Python 3.10。高层 SDK 支持 Python 3.10+，但仓库中随附的 DDS wheel 是
  `cp310`，使用 DDS 工具时应保持 Python 3.10；
- x86_64 或 ARM64；
- 支持 OpenGL 的桌面环境；
- Dobot Quad 官方 SDK；
- DDS 功能需要 PC 与机器人有线网络互通；gRPC/HTTP 可按机器人实际网络使用
  Wi-Fi、有线或 Station 网络。

`dobot_quad_sdk/` 在本仓库的 `.gitignore` 中，不随本项目提交。新环境中如果没有
该目录，请先取得与机器人固件匹配的官方 SDK，并放到项目根目录：

```text
dobot_quad_sdk_test/
└── dobot_quad_sdk/
    ├── high_level/python/
    ├── dist/
    └── setup_cyclonedds_env.sh
```

## 安装

### 1. 创建 Python 环境

在项目根目录执行：

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  PySide6 pyqtgraph PyOpenGL numpy opencv-contrib-python \
  pupil-apriltags Pillow
```

这里使用 `opencv-contrib-python`，因为 AprilTag 图片生成需要 `cv2.aruco`。
`Pillow` 用于给打印图写入 DPI 信息。

### 2. 安装高层 gRPC SDK

```bash
python -m pip install -e ./dobot_quad_sdk/high_level/python
```

安装后可检查：

```bash
python -c "from dobot_quad import RobotClient; print('dobot_quad OK')"
```

只使用 `auto_move/`，或只使用 HTTP 控制台而不显示实际位置时，到这里即可。
HTTP 随机巡逻、范围判断和实际轨迹仍需要 `:50051` 的 gRPC 世界坐标。

### 3. 安装 DDS 中间件

DDS 程序还需要官方二进制中间件、CycloneDDS 开发包和与 CPU 架构匹配的 Python
wheel。以下文件名以当前 SDK 的 `0.23.3`、Python 3.10 为例：

```bash
sudo apt update
sudo apt install cyclonedds-dev

# x86_64
sudo dpkg -i ./dobot_quad_sdk/dist/dds-middleware-with-thirdparty_0.23.3_amd64.deb
python -m pip install \
  ./dobot_quad_sdk/dist/dds_middleware_python-0.23.3-cp310-cp310-linux_x86_64.whl

# ARM64 请改用 arm64 deb 和 linux_aarch64 wheel
```

如果 SDK 版本不同，请以 `dobot_quad_sdk/dist/` 中的实际文件名为准。安装后检查：

```bash
python -c "import dds_middleware_python as dds; print('DDS OK', getattr(dds, '__version__', ''))"
```

## 网络配置

### 常用地址

| 链路 | 常用地址 | 说明 |
| --- | --- | --- |
| gRPC | `机器人IP:50051` | 高层状态与动作；官方 AP 常用 `192.168.1.6:50051` |
| HTTP 控制器 | `机器人IP:22000` | 连接心跳、摇杆、动作、配置、软急停 |
| HTTP 算法服务 | `机器人IP:22002` | `/algs/*` 接口，由 HTTP 控制台自动选端口 |
| DDS | 有线网段，机器人常用 `192.168.5.2` | 图像及底层状态，必须选择正确有线网卡 |

源码中的 `10.30.12.*` 是开发网络示例，不是所有机器人的固定地址。优先使用界面
里的地址输入框；没有输入框的程序需修改下列默认值：

| 程序 | 默认地址位置 |
| --- | --- |
| `auto_move` | 界面“机器人地址”，默认 `10.30.12.21:50051`，可直接修改 |
| `http_auto_move` | 界面“控制接口”和“轨迹端口”，主机用于 HTTP 与只读 gRPC |
| `high_level_monitor` | `high_level_monitor/main_window.py` 中的 `RobotPoller(addr=...)` |
| `command_center` | `command_center/main.py` 中的 `RobotWorker(addr=...)` |

### DDS 网卡

先把 PC 有线网卡配置到机器人所在子网，并确认能访问机器人。每个新终端中，在
项目根目录执行：

```bash
source ./dobot_quad_sdk/setup_cyclonedds_env.sh
echo "$CYCLONEDDS_URI"
cyclonedds ps
```

脚本会根据到 `192.168.5.2` 的路由选择网卡，并在 `/tmp` 生成 CycloneDDS 配置。
如果机器人 DDS 地址不是 `192.168.5.2`，请修改脚本中的 `DOBOT_IP`，或手动设置
`CYCLONEDDS_URI`。各应用的 `config/dds_config.yaml` 使用 DDS Domain 0，并定义
默认 QoS；它不负责选择系统网卡。

## 快速开始

所有命令均建议从项目根目录运行，并先激活虚拟环境。

### 只读查看 DDS 数据

```bash
source .venv/bin/activate
source ./dobot_quad_sdk/setup_cyclonedds_env.sh
python3 quad_camera_app/main.py
```

该界面订阅：

- `rt/camera/camera2/image_compressed`：前置 RGB；
- `rt/camera/camera2/image_depth`：前置深度；
- `rt/camera/camera3/image_compressed`：后置 RGB；
- `rt/camera/camera3/image_depth`：后置深度；
- `rt/lower/state`：IMU、电池与电机状态；
- `rt/voice/state`：语音数据状态。

### gRPC 自动移动与精度测试

```bash
python3 auto_move/main.py
```

在界面中填写 `IP:50051` 并连接，然后选择：

- `line_walk` 前后或左右移动；
- `rotate` 原地旋转；
- `velocity_sequence` 速度序列；
- 循环次数、稳定等待和自动回中；
- 是否记录精度数据。

程序用实际 `pos_body`/姿态绘制 3D 轨迹。启用精度记录后，原始记录和统计汇总
保存在 `auto_move/results/`。`auto_move/precision_test.py` 是同一窗口的精度测试
入口：

```bash
python3 auto_move/precision_test.py
```

### HTTP 范围内随机巡逻

```bash
python3 -m http_auto_move.main
```

推荐操作顺序：

1. 输入机器人的 `:22000` 地址，保持“自动检测”连接方式，连接后确认
   `/protocol/exchange` 持续更新；
2. 使用“以当前位置设定矩形”，或在至少三个位置分别“记录当前位置”后生成
   多点凸包围栏；
3. 选择“随机巡逻”，从较低的巡逻速度和较短的每段长度开始；
4. 先执行有限路段，确认转向、前进、归零和越界回中心均符合现场坐标方向；
5. 确认安全后再考虑无限循环。

当前选点策略是在安全内缩后的矩形/凸多边形中**按面积随机抽取一个目标点**：

- 固定保留 0.15 m 软件安全边距；
- 仅排除与当前位置小于定位容差、无法形成有效动作的点；
- 不生成一批候选点，也不选择最远点；
- 机器人先根据 HTTP IMU 转向随机点，再向前移动“每段长度”；
- 若随机点更近，本段自动缩短并停在该点；停车后才抽取下一点；
- 发现越界会先归零，再闭环返回范围中心，然后重新规划当前路段；
- gRPC 位置或 HTTP IMU 过期时会停车等待，持续不可用则中止。

界面同时显示本次自动动作的总里程和总时间：里程按 gRPC 世界坐标的 XY 实际
轨迹累计，用时从点击“开始”持续到完成、停止或急停。每次开始新任务时自动清零。

“摇杆归零”与“软急停”不是同一操作。程序不会自行解除软急停，解除前必须确认
现场安全。更完整的参数、接口路由和误差日志说明见
[HTTP 工具文档](http_auto_move/README.md)。

## 相机标定与 AprilTag

### 生成棋盘格

```bash
python3 camera_calib/generate_checkerboard.py
```

生成的 `camera_calib/checkerboard.png` 为 9×6 内角点、25 mm 方格。打印时应选择
100%/实际尺寸，禁止“适应纸张”缩放，并测量实物方格确认仍为 25 mm。

### 单相机标定

```bash
python3 camera_calib/main.py
```

可选 DDS 前置/后置 RGB 或本地 OpenCV 相机 0/1。让棋盘覆盖画面的不同位置、距离
和倾角，检测成功时捕获帧；程序至少需要 3 帧，完成后写入：

```text
camera_calib/calibration_result.json
```

### 双相机标定

```bash
python3 camera_calib2/main.py
```

前置 `camera2` 与后置 `camera3` 独立捕获、独立计算，结果分别写入：

```text
camera_calib2/calib_camera2.json
camera_calib2/calib_camera3.json
```

### AprilTag 追踪

先生成可打印的 tag36h11 标签：

```bash
python3 apriltag_tracker/tag_generator.py
```

默认生成 ID 0～5 的 A4 图片，编码区边长约 155 mm。打印必须保持原尺寸；PnP
计算使用的 `TAG_SIZE_MM` 必须与实物编码区边长一致。然后运行：

```bash
python3 apriltag_tracker/main.py
```

程序支持 DDS 实时相机、视频文件回放、逐帧检查、EMA 轨迹平滑、录像和轨迹 JSON。
轨迹默认保存到 `apriltag_tracker/trajectory.json`。标定文件映射目前定义在
`apriltag_tracker/main.py` 的 `CALIB_FILES`，其中是本机绝对路径；换目录或换机器后
必须改为实际的 `calib_camera2.json`、`calib_camera3.json` 路径。找不到标定文件时
程序会使用估算内参，定位精度会明显下降。

## 状态监控与指令中心

```bash
# 只读高级状态 + 3D 位姿 + 四相机
python3 high_level_monitor/main.py

# 完整动作按钮 + 3D 位姿 + 四相机 + 日志
python3 command_center/main.py
```

这两个程序的 gRPC 地址目前写在源码中。若只连接 gRPC 而未配置 DDS，相机区域会
无数据；若只连接 DDS 而 gRPC 地址不通，高层状态/控制不可用。`command_center`
包含高风险动作按钮，确认机器人型号、动作支持情况和周围空间后再使用。

## 配置和生成文件

| 路径 | 用途 |
| --- | --- |
| `*/config/dds_config.yaml` | DDS Domain 与默认 QoS |
| `camera_calib/checkerboard_utils.py` | 棋盘格内角点、方格尺寸和打印 DPI |
| `camera_calib2/checkerboard_utils.py` | 双相机标定板参数 |
| `apriltag_tracker/tag_generator.py` | Tag 字典、尺寸、ID 和打印 DPI |
| `apriltag_tracker/main.py` | 相机话题、标定文件、PnP 和滤波参数 |
| `auto_move/results/` | gRPC 动作精度明细与汇总 CSV |
| `http_auto_move/MH4 HTTP接口定义.md` | MH4 HTTP 原始接口定义 |
| `http_auto_move/api_catalog.py` | HTTP 控制台按钮和参数目录 |

Qt Designer 源文件位于各模块的 `ui/`，`generated/` 是生成的 Python 文件。修改
`.ui` 后需重新生成对应文件，例如：

```bash
pyside6-uic camera_calib/ui/main_window.ui \
  -o camera_calib/generated/ui_main_window.py
```

不要直接在运行程序的同时覆盖生成文件。

## 测试

HTTP 客户端、接口目录、围栏几何、面积随机采样、巡逻时序和回中心逻辑有独立单元
测试，不连接真实机器人即可运行：

```bash
python3 -m unittest discover -s http_auto_move/tests -v
```

真实机器人联调应按“只读 DDS → 只读 gRPC → 单次低速动作 → 有限随机巡逻”的顺序
逐级进行。单元测试通过只代表软件逻辑符合预期，不代表现场运动安全。

## 常见问题

### `ModuleNotFoundError: dobot_quad`

高层 SDK 未安装，或当前终端没有激活安装它的虚拟环境：

```bash
source .venv/bin/activate
python -m pip install -e ./dobot_quad_sdk/high_level/python
```

### `ModuleNotFoundError: dds_middleware_python`

确认 Python 是 3.10、CPU 架构与 wheel 一致，并按“安装 DDS 中间件”一节同时安装
官方 deb 和 wheel。

### DDS 初始化成功但没有画面

依次检查网线、PC 子网、机器人电源、`CYCLONEDDS_URI`、`cyclonedds ps`、Domain 0
和防火墙。切换终端后需要重新 `source setup_cyclonedds_env.sh`。

### gRPC 状态或轨迹没有数据

确认填写的是 `:50051`，PC 能访问该 IP，机器人高层服务已启动。HTTP 程序即使
`:22000` 已连接，随机巡逻仍会因为缺少 gRPC 世界坐标而停止。

### Qt 启动时报 OpenGL/xcb 错误

确认在本地图形桌面运行并已安装显卡/OpenGL、Qt xcb 相关系统库。通过 SSH 运行
时需要正确配置 X11 转发或远程桌面；纯终端环境无法显示这些 GUI。

## 资料与许可

- [Dobot Quad SDK 介绍](dobot_quad_intro/Dobot_Quad_SDK_介绍.md)
- [项目内 API 速查](dobot_quad_intro/api_reference.md)
- [官方 SDK 中文 README](dobot_quad_sdk/README.zh-CN.md)（本地 SDK 存在时）

本仓库根目录目前没有单独的许可证文件；嵌入的官方 SDK 使用其目录中的许可证。
复制、发布或商用前请分别确认项目代码、官方 SDK、模型资源和第三方依赖的许可。
