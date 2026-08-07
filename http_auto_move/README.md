# MH4 HTTP Auto Move

这是 `auto_move` 的 HTTP 接口版本，不依赖 `dobot_quad` gRPC SDK。程序使用
《MH4 HTTP接口定义》中的以下接口：

- `POST /connection/state`：声明客户端连接；
- `GET /protocol/exchange`：以 5 Hz 获取状态并保持连接占用；
- `POST /settings/movement/joystickControl`：以 2～50 Hz 发送摇杆值；
- `POST /settings/emergencyStop`：触发或解除软急停；
- `POST :22002/algs/settings/movement/speedRatio`：可选的算法速度比例设置。

## 启动

在仓库根目录运行：

```bash
python3 -m http_auto_move.main
```

也可以直接运行：

```bash
python3 http_auto_move/main.py
```

只需要项目已有的 `PySide6`；HTTP 客户端使用 Python 标准库。

接口文档给出的默认地址：

- AP：`192.168.1.6:22000`
- 网线直连：`192.168.5.2:22000`

## 首次使用

1. 让机器人处在开阔、安全并可随时断电的位置。
2. 先连接，确认右侧 `exchange` 心跳和急停状态持续更新。
3. 用“原始摇杆”页签和较小数值（建议 2000～5000）短时验证正负方向。
4. 如果方向相反，在自动动作页签勾选“反转该方向的摇杆正负号”。
5. 实测满幅速度/角速度，填到“满幅标定速度”后再使用距离或角度动作。

当前默认映射采用常见屏幕摇杆坐标：

| 动作 | HTTP 字段 | 默认值符号 |
| --- | --- | --- |
| 前进 / 后退 | `btn_move.y` | 负 / 正 |
| 左移 / 右移 | `btn_move.x` | 负 / 正 |
| 左转 / 右转 | `btn_turn.x` | 负 / 正 |

## 与原 `auto_move` 的差异

HTTP 文档没有按距离/角度执行的接口，也没有世界坐标或机身速度反馈。因此：

- 距离和角度按 `目标 ÷ (满幅标定速度 × 摇杆幅值比例)` 换算持续时间；
- 这是开环估算，会受地面、步态、电量和速度设置影响；
- `exchange.imu` 只用于显示姿态，不能提供可靠的位置闭环或精度统计；
- “摇杆归零”会中止当前动作并重复发送全零摇杆值；“急停”另外调用软急停接口。

程序不会自动解除软急停。解除前请先确认现场安全。

## 测试

```bash
python3 -m unittest discover -s http_auto_move/tests -v
```

