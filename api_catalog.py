# 说明 API 目录及默认请求示例的数据来源。
"""《MH4 HTTP接口定义》中的接口目录和常用请求示例。"""

# 导入本模块所需的库、类型和外部组件。
from __future__ import annotations

# 导入本模块所需的库、类型和外部组件。
from dataclasses import dataclass
from typing import Any


# 声明下方方法的调用方式或属性行为。
@dataclass(frozen=True)
# 描述一个可由界面调用的 HTTP API 端点。
class ApiEndpoint:
    category: str
    name: str
    method: str
    path: str
    port: int
    payload: Any | None
    dangerous: bool = False

    # 封装 label 对应的独立处理逻辑。
    @property
    def label(self) -> str:
        warning = " ⚠" if self.dangerous else ""
        return (
            f"[{self.port} {self.method}] {self.category} / {self.name}"
            f" — {self.path}{warning}"
        )


# 分类、名称、文档声明的方法、路径。GET/POST 会展开为两个独立选项。
_SPECS = (
    ("连接", "连接状态", "POST,GET", "/connection/state"),
    ("连接", "连接方式", "POST,GET", "/connection/type"),
    ("状态", "周期 exchange", "GET", "/protocol/exchange"),
    ("设置", "版本信息", "GET", "/settings/version"),
    ("设置", "报警清除", "POST", "/settings/clearAlarms"),
    ("安全限制", "位置超限", "POST,GET", "/settings/posLimit"),
    ("安全限制", "速度超限", "POST,GET", "/settings/velLimit"),
    ("安全限制", "力矩超限", "POST,GET", "/settings/torqueLimit"),
    ("安全限制", "KP超限", "POST,GET", "/settings/kpLimit"),
    ("安全限制", "KD超限", "POST,GET", "/settings/kdLimit"),
    ("运动", "软急停", "POST", "/settings/emergencyStop"),
    ("运动", "摇杆控制", "POST", "/settings/movement/joystickControl"),
    ("运动", "常用动作列表", "GET", "/settings/movement/actions"),
    ("运动", "执行动作或姿势", "POST", "/settings/movement/action"),
    ("运动", "动作执行参数", "GET", "/settings/movement/params"),
    ("运动", "高危动作协议申请", "POST", "/settings/movement/apply"),
    ("图传", "开启本地图传", "POST", "/settings/streaming/start"),
    ("图传", "停止图传", "POST", "/settings/streaming/stop"),
    ("图传", "视频录制", "POST", "/settings/streaming/record"),
    ("图传", "录制视频下载", "GET", "/settings/streaming/download"),
    ("OTA", "检查更新", "GET", "/settings/ota/checkUpdate"),
    ("OTA", "判断安装包已下载", "GET", "/settings/ota/download"),
    ("OTA", "下载升级包", "POST", "/settings/ota/download"),
    ("OTA", "通知升级", "POST", "/settings/ota/update"),
    ("OTA", "下载进度", "GET", "/settings/ota/downloadProgress"),
    ("OTA", "升级包校验", "POST", "/settings/ota/verify"),
    ("OTA", "升级进度", "GET", "/settings/ota/updateProgress"),
    ("设备设置", "探照灯", "POST", "/settings/searchLight"),
    ("设备设置", "语言", "POST", "/settings/language"),
    ("设备设置", "UID", "GET,POST", "/settings/uid"),
    ("设备设置", "系统时间", "POST,GET", "/settings/systemTime"),
    ("语音", "音量", "POST,GET", "/settings/voice/volume"),
    ("语音", "助手配置", "POST,GET", "/settings/voice/config"),
    ("设备设置", "锁机状态", "GET", "/settings/lock"),
    ("BMS", "满充校准", "GET", "/settings/bmsCalibration"),
    ("BMS", "日志记录数量", "GET", "/settings/bmsLogCount"),
    ("语音", "音频列表", "GET", "/settings/voice/list"),
    ("语音", "重命名音频", "POST", "/settings/voice/rename"),
    ("语音", "删除音频", "POST", "/settings/voice/delete"),
    ("语音", "任务状态", "GET", "/settings/voice/taskid?taskId=xxxxxx"),
    ("语音", "播放音频", "POST", "/settings/voice/play"),
    ("语音", "停止播放", "POST", "/settings/voice/stop"),
    ("语音", "播放属性", "POST,GET", "/settings/voice/property"),
    ("BMS", "日志最新索引", "GET", "/settings/bmsLogLatestIndex"),
    ("BMS", "指定索引日志", "POST", "/settings/bmsLog"),
    ("图传", "开启云端图传", "POST", "/settings/streaming/agora/start"),
    ("图传", "切换相机", "POST", "/settings/streaming/switch"),
    ("4G", "模块配置", "GET", "/settings/fourgCapacity"),
    ("BMS", "Fg模型有效值", "GET", "/settings/bmsFgModelValid"),
    ("UWB", "设置配对设备", "POST", "/settings/uwbWhitelist"),
    ("UWB", "解除配对设备", "POST", "/settings/uwbUnbind"),
    ("设备设置", "定制参数", "GET,POST", "/settings/customParams"),
    ("标定", "电机/编码器标定", "POST", "/calibrate/joints"),
    ("标定", "IMU校零", "POST", "/calibrate/imu"),
    ("网络", "热点名称和密码", "POST,GET", "/interface/AP"),
    ("设备属性", "伺服报警内容", "GET", "/properties/alarmsServo"),
    ("设备属性", "控制器报警内容", "GET", "/properties/alarmsController"),
    ("设备属性", "名称和备注", "POST,GET", "/properties/deviceProfile"),
    ("设备属性", "机型", "GET", "/properties/robotType"),
    ("设备属性", "定制版本类型", "GET", "/properties/customEdition"),
    ("设备属性", "设备序列号", "GET", "/properties/snCode"),
    ("设备属性", "国家/地区代码", "GET,POST", "/properties/countryCode"),
    ("eSIM", "ICCID", "GET", "/esim/iccid"),
    ("日志", "全部日志信息", "GET", "/download/logs/all"),
    ("日志", "内部日志日期", "GET", "/download/logs/dates"),
    ("日志", "通知上传日志", "POST", "/download/logs/upload"),
    ("上传", "局域网音频上传", "POST", "/upload/formdata/audio"),
    ("上传", "4G音频上传", "POST", "/upload/url/audio"),
    ("上传", "TTS文字转音频", "POST", "/upload/tts/audio"),
    ("工程", "运行程序", "POST", "/project/run"),
    ("工程", "停止程序", "POST", "/project/stop"),
    ("SLAM", "新建地图", "POST", "/algs/slam/new"),
    ("SLAM", "地图列表", "GET", "/algs/slam/list"),
    ("SLAM", "重命名地图", "POST", "/algs/slam/edit"),
    ("SLAM", "删除地图", "POST", "/algs/slam/delete"),
    ("SLAM", "初始化定位", "POST", "/algs/slam/initPosition"),
    ("SLAM", "开启定位", "POST", "/algs/slam/startPosition"),
    ("SLAM", "停止定位", "POST", "/algs/slam/stopPosition"),
    ("SLAM", "实时定位坐标", "POST", "/algs/slam/postion"),
    ("SLAM", "建图进度", "POST", "/algs/slam/queryProgressing"),
    ("SLAM", "获取路网", "GET", "/algs/slam/roadNetwork?name=mapName"),
    ("SLAM", "设置路网", "POST", "/algs/slam/roadNetwork"),
    ("SLAM", "开始路网巡逻", "POST", "/algs/slam/startNetworkPatrol"),
    ("SLAM", "更新路网巡逻状态", "POST", "/algs/slam/updateNetworkPatrolStatus"),
    ("SLAM", "开始单点导航", "POST", "/algs/slam/startSinglePointPatrol"),
    ("SLAM", "更新单点导航状态", "POST", "/algs/slam/updateSinglePointPatrolStatus"),
    ("SLAM", "巡逻状态", "GET", "/algs/slam/patrolStatus"),
    ("算法运动", "避障状态", "GET,POST", "/algs/settings/movement/obstacleAvoidance"),
    ("算法运动", "速度模式", "POST,GET", "/algs/settings/movement/speedMode"),
    ("算法运动", "速度比例", "POST,GET", "/algs/settings/movement/speedRatio"),
    ("智能跟随", "视觉选人配置", "POST", "/algs/settings/autoIntelligence/follow"),
    ("智能跟随", "人物选择框信息", "GET", "/algs/settings/autoIntelligence/follow/getViewPersonInfo"),
    ("标定", "入箱标定", "POST", "/algs/calibrate/box"),
)


# 定义本模块后续逻辑使用的常量或默认配置。
_LEGS = (
    "left_front_leg",
    "right_front_leg",
    "left_rear_leg",
    "right_rear_leg",
)


# 构造指定关节字段的取值范围说明。
def _joint_limits(field: str, limits: list[list[float]]) -> dict[str, Any]:
    return {field: {leg: copy_limits(limits) for leg in _LEGS}}


# 复制关节限位列表以避免共享可变数据。
def copy_limits(limits: list[list[float]]) -> list[list[float]]:
    return [list(pair) for pair in limits]


# 执行本逻辑段的数据处理、状态同步或界面更新。
_PAYLOADS: dict[str, Any] = {
    "/connection/state": {
        "currentClient": 1,
        "clientName": "HTTP Console",
        "connectionType": "Station",
    },
    "/connection/type": {"value": "Station"},
    "/settings/posLimit": _joint_limits(
        "jointsPosLimit", [[-12.5664, 12.5664]] * 4
    ),
    "/settings/velLimit": _joint_limits(
        "jointsVelLimit", [[-34.5575, 34.5575]] * 4
    ),
    "/settings/torqueLimit": _joint_limits(
        "jointsTorqueLimit", [[-20.0, 20.0], [-20.0, 20.0], [-40.0, 20.0], [-20.0, 20.0]]
    ),
    "/settings/kpLimit": _joint_limits("jointsKpLimit", [[0.0, 500.0]] * 4),
    "/settings/kdLimit": _joint_limits("jointsKdLimit", [[0.0, 50.0]] * 4),
    "/settings/emergencyStop": {"value": True},
    "/settings/movement/joystickControl": {
        "btn_move": {"x": 0, "y": 0},
        "btn_turn": {"x": 0, "y": 0},
    },
    "/settings/movement/action": {"id": 20},
    "/settings/movement/apply": {
        "snCode": "xxxx",
        "uid": "xxxx",
        "appliedAt": "2026-01-01 00:00:00",
    },
    "/settings/streaming/record": {"action": "start", "camera": "front"},
    "/settings/searchLight": {"open": True},
    "/settings/language": {"language": "zh-Hans"},
    "/settings/uid": {"uid": ""},
    "/settings/systemTime": {
        "systemTime": "2026-01-01 00:00:00",
        "timeZone": "Asia/Shanghai",
    },
    "/settings/voice/volume": {"volume": 50},
    "/settings/voice/config": {"switch": True, "AITalkSwitch": False, "role": 1},
    "/settings/voice/rename": {"id": "***", "name": "新名称"},
    "/settings/voice/delete": {"id": "***"},
    "/settings/voice/play": {"id": "***"},
    "/settings/voice/property": {"type": 1, "cycleTime": 1},
    "/settings/bmsLog": {"index": 1},
    "/settings/streaming/switch": {"camera": "front"},
    "/settings/streaming/agora/start": {
        "publisherToken": "",
        "publisherId": "",
        "channelName": "",
        "appId": "",
        "expireTime": 0,
        "camera": "front",
    },
    "/settings/uwbWhitelist": {"name": "inffniv1-xxxxxxxx"},
    "/settings/customParams": {"LvYuan": {"welcomeSwitch": True}},
    "/calibrate/joints": {
        "left_front_leg": [False, False, False, False],
        "right_front_leg": [False, False, False, False],
        "left_rear_leg": [False, False, False, False],
        "right_rear_leg": [False, False, False, False],
    },
    "/interface/AP": {"ssid": "ssid_name", "passWd": "password"},
    "/properties/deviceProfile": {"name": "MH4", "remark": ""},
    "/properties/countryCode": {"countryCode": "CN"},
    "/download/logs/upload": {
        "date": "2026-01-01T00",
        "logserver": "https://dobotex-api-dev.dobot.cc",
        "module": "controller",
        "osVersion": "",
        "appVersion": "",
        "deviceModel": "",
        "userAccount": "",
    },
    "/upload/formdata/audio": {
        "name": "audio",
        "type": "audio",
        "time": "2026-01-01 00:00:00",
        "file": "",
    },
    "/upload/url/audio": {
        "name": "audio",
        "type": "audio",
        "time": "2026-01-01 00:00:00",
        "url": "https://example.com/audio.wav",
    },
    "/upload/tts/audio": {
        "name": "tts",
        "type": "tts",
        "time": "2026-01-01 00:00:00",
        "word": "你好",
    },
    "/project/run": {"pythonCode": "# Python code"},
    "/algs/slam/new": {"name": "mapName", "action": "start"},
    "/algs/slam/edit": {"oldName": "old", "newName": "new"},
    "/algs/slam/delete": {"name": "mapName"},
    "/algs/slam/initPosition": {
        "name": "mapName", "x": 0, "y": 0, "z": 0, "rad": 0, "type": "map",
    },
    "/algs/slam/startPosition": {"name": "mapName"},
    "/algs/slam/stopPosition": {"name": "mapName"},
    "/algs/slam/postion": {"name": "mapName"},
    "/algs/slam/queryProgressing": ["mapName"],
    "/algs/slam/roadNetwork": {
        "name": "mapName",
        "roadNetworkPoints": [
            {"id": 1, "name": "point1", "next": 0,
             "pose": {"x": 0.0, "y": 0.0, "z": 0.0, "rad": 0.0, "type": "map"}}
        ],
    },
    "/algs/slam/startNetworkPatrol": {
        "name": "mapName", "roadNetworkPoints": [1], "repeatCount": 1,
    },
    "/algs/slam/updateNetworkPatrolStatus": {"name": "mapName", "status": "pause"},
    "/algs/slam/startSinglePointPatrol": {
        "name": "mapName",
        "position": {"x": 0.0, "y": 0.0, "z": 0.0, "rad": 0.0, "type": "map"},
    },
    "/algs/slam/updateSinglePointPatrolStatus": {"name": "mapName", "status": "pause"},
    "/algs/settings/movement/obstacleAvoidance": {"open": True},
    "/algs/settings/movement/speedMode": {"mode": "low"},
    "/algs/settings/movement/speedRatio": {"ratio": 50},
    "/algs/settings/autoIntelligence/follow": {
        "open": 0, "type": "rear", "distance": 1.5,
        "target_id": 0, "target_x": 0.0, "target_y": 0.0,
    },
}


# 定义本模块后续逻辑使用的常量或默认配置。
_NO_BODY_POSTS = {
    "/settings/clearAlarms",
    "/settings/streaming/start",
    "/settings/streaming/stop",
    "/settings/ota/download",
    "/settings/ota/update",
    "/settings/ota/verify",
    "/settings/voice/stop",
    "/settings/uwbUnbind",
    "/calibrate/imu",
    "/project/stop",
    "/algs/calibrate/box",
}


# 定义本模块后续逻辑使用的常量或默认配置。
_DANGEROUS_PATHS = {
    "/connection/type",
    "/settings/posLimit",
    "/settings/velLimit",
    "/settings/torqueLimit",
    "/settings/kpLimit",
    "/settings/kdLimit",
    "/settings/emergencyStop",
    "/settings/movement/joystickControl",
    "/settings/movement/action",
    "/settings/movement/apply",
    "/settings/ota/download",
    "/settings/ota/update",
    "/settings/ota/verify",
    "/settings/voice/delete",
    "/settings/bmsCalibration",
    "/settings/uwbUnbind",
    "/calibrate/joints",
    "/calibrate/imu",
    "/interface/AP",
    "/project/run",
    "/algs/slam/new",
    "/algs/slam/delete",
    "/algs/slam/startNetworkPatrol",
    "/algs/slam/startSinglePointPatrol",
    "/algs/settings/movement/speedMode",
    "/algs/settings/movement/speedRatio",
    "/algs/settings/autoIntelligence/follow",
    "/algs/calibrate/box",
}


# 为指定 API 方法和路径生成默认请求载荷。
def _payload(method: str, path: str) -> Any | None:
    # 根据当前状态或输入选择对应的处理路径。
    if method != "POST" or path in _NO_BODY_POSTS:
        return None
    value = _PAYLOADS.get(path, {})
    # 目录对象永不被界面直接修改，不过复制一层可以避免可变默认值意外共享。
    if isinstance(value, dict):
        return dict(value)
    # 根据当前状态或输入选择对应的处理路径。
    if isinstance(value, list):
        return list(value)
    return value


# 定义本模块后续逻辑使用的常量或默认配置。
ENDPOINTS = tuple(
    ApiEndpoint(
        category=category,
        name=name,
        method=method,
        path=path,
        port=22002 if path.startswith("/algs/") else 22000,
        payload=_payload(method, path),
        dangerous=path in _DANGEROUS_PATHS,
    )
    for category, name, methods, path in _SPECS
    for method in methods.split(",")
)
