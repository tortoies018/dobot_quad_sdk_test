# 说明轻量 HTTP 客户端的用途与依赖约束。
"""MH4 HTTP 接口的轻量客户端。

只使用 Python 标准库，避免为了几个 JSON 接口额外引入 requests 依赖。
"""

# 导入本模块所需的库、类型和外部组件。
from __future__ import annotations

# 导入本模块所需的库、类型和外部组件。
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


# 定义本模块后续逻辑使用的常量或默认配置。
STICK_MIN = -32768
STICK_MAX = 32767


# 表示机器狗 HTTP 接口返回的业务或通信错误。
class MH4HttpError(RuntimeError):
    """HTTP、JSON 或接口业务状态异常。"""


# 把摇杆数值限制到设备允许的范围内。
def _clamp_stick(value: int) -> int:
    return max(STICK_MIN, min(STICK_MAX, int(value)))


# 封装机器狗 HTTP 控制接口及请求校验。
class MH4HttpClient:
    """文档中 22000 MH4 控制接口的同步客户端。"""

    # 初始化对象状态以及运行所需的资源。
    def __init__(self, address: str, timeout: float = 1.5):
        self.control_base = self._normalise_address(address)
        self.timeout = max(0.1, float(timeout))

    # 规范化服务地址并补全 HTTP 协议前缀。
    @staticmethod
    def _normalise_address(address: str) -> str:
        value = address.strip()
        # 必要条件或数据不满足时执行安全处理。
        if not value:
            raise ValueError("HTTP 地址不能为空")
        # 必要条件或数据不满足时执行安全处理。
        if "://" not in value:
            value = f"http://{value}"
        parsed = urlsplit(value)
        # 必要条件或数据不满足时执行安全处理。
        if parsed.scheme not in ("http", "https"):
            raise ValueError("HTTP 地址只支持 http:// 或 https://")
        # 必要条件或数据不满足时执行安全处理。
        if not parsed.hostname:
            raise ValueError("HTTP 地址中缺少主机名或 IP")
        # 必要条件或数据不满足时执行安全处理。
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("请输入 IP/主机和端口，不要附加接口路径")

        # 准备本逻辑段使用的局部数据和中间状态。
        host = parsed.hostname
        # 根据当前状态或输入选择对应的处理路径。
        if ":" in host:  # IPv6 URL 需要方括号
            host = f"[{host}]"
        control_port = parsed.port or 22000
        return f"{parsed.scheme}://{host}:{control_port}"

    # 发送 HTTP 请求并统一处理网络及响应错误。
    def _request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        allow_non_json: bool = False,
    ) -> Any:
        body = None
        headers = {"Accept": "application/json"}
        # 必要条件或数据不满足时执行安全处理。
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(
            f"{self.control_base}{path}", data=body, headers=headers, method=method
        )
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            # 在受控上下文中安全访问共享资源。
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                headers = getattr(response, "headers", None)
                content_type = (
                    headers.get("Content-Type", "") if headers is not None else ""
                )
        # 捕获异常并执行日志记录或安全降级。
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            raise MH4HttpError(f"HTTP {exc.code} {method} {path}{suffix}") from exc
        # 捕获异常并执行日志记录或安全降级。
        except (URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise MH4HttpError(f"请求失败 {method} {path}: {reason}") from exc

        # 必要条件或数据不满足时执行安全处理。
        if not raw:
            return {}
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            return json.loads(raw.decode("utf-8"))
        # 捕获异常并执行日志记录或安全降级。
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            # 根据当前状态或输入选择对应的处理路径。
            if allow_non_json:
                return {
                    "responseType": "non-json",
                    "contentType": content_type,
                    "size": len(raw),
                    "preview": raw[:512].decode("utf-8", errors="replace"),
                }
            preview = raw[:160].decode("utf-8", errors="replace")
            raise MH4HttpError(f"接口返回的不是有效 JSON: {preview!r}") from exc

    # 按调用方给出的参数发送原始 API 请求。
    def raw_request(self, method: str, path: str, payload: Any | None = None) -> Any:
        """调用目录或用户输入的 JSON 接口，不强制要求 ``status=true``。"""
        method = method.strip().upper()
        # 必要条件或数据不满足时执行安全处理。
        if method not in ("GET", "POST"):
            raise ValueError("手动 HTTP 控制台只支持 GET 或 POST")
        path = path.strip()
        # 必要条件或数据不满足时执行安全处理。
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("接口路径必须以单个 / 开头")
        return self._request(method, path, payload, allow_non_json=True)

    # 读取音频文件并按接口要求完成上传。
    def upload_audio_file(self, payload: dict[str, Any]) -> Any:
        """调用 multipart 音频上传接口。"""
        file_path = Path(str(payload.get("file", ""))).expanduser()
        # 必要条件或数据不满足时执行安全处理。
        if not file_path.is_file():
            raise ValueError("请选择有效的音频文件")
        boundary = f"----MH4HttpConsole{uuid.uuid4().hex}"
        chunks: list[bytes] = []
        # 逐项处理当前集合中的数据。
        for key in ("name", "type", "time"):
            value = str(payload.get(key, ""))
            chunks.extend((
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ))
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ))
        request = Request(
            f"{self.control_base}/upload/formdata/audio",
            data=b"".join(chunks),
            headers={
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            # 在受控上下文中安全访问共享资源。
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        # 捕获异常并执行日志记录或安全降级。
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            raise MH4HttpError(f"HTTP {exc.code} POST /upload/formdata/audio{suffix}") from exc
        # 捕获异常并执行日志记录或安全降级。
        except (URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise MH4HttpError(
                f"请求失败 POST /upload/formdata/audio: {reason}"
            ) from exc
        # 必要条件或数据不满足时执行安全处理。
        if not raw:
            return {}
        # 尝试执行可能失败的操作并交由异常分支处理。
        try:
            return json.loads(raw.decode("utf-8"))
        # 捕获异常并执行日志记录或安全降级。
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            preview = raw[:160].decode("utf-8", errors="replace")
            raise MH4HttpError(f"接口返回的不是有效 JSON: {preview!r}") from exc

    # 校验接口业务状态并返回有效结果。
    @staticmethod
    def _require_success(result: Any, operation: str) -> Any:
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(result, dict):
            raise MH4HttpError(f"{operation} 返回格式错误: {result!r}")
        # 必要条件或数据不满足时执行安全处理。
        if result.get("status") is not True:
            raise MH4HttpError(f"{operation} 被控制器拒绝: {result!r}")
        return result

    # 建立机器人控制连接并登记客户端信息。
    def connect(
        self,
        client_name: str,
        connection_type: str,
        current_client: int = 1,
    ) -> dict[str, Any]:
        result = self._request(
            "POST",
            "/connection/state",
            {
                "currentClient": int(current_client),
                "clientName": client_name,
                "connectionType": connection_type,
            },
        )
        return self._require_success(result, "连接")

    # 读取当前控制连接状态。
    def connection_state(self) -> dict[str, Any]:
        result = self._request("GET", "/connection/state")
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(result, dict):
            raise MH4HttpError(f"连接状态返回格式错误: {result!r}")
        return result

    # 查询机器人当前采用的连接类型。
    def connection_type(self) -> str:
        result = self._request("GET", "/connection/type")
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(result, dict) or result.get("value") not in ("AP", "Station"):
            raise MH4HttpError(f"连接方式返回格式错误: {result!r}")
        return str(result["value"])

    # 执行 exchange 请求以交换状态并维持心跳。
    def exchange(self) -> dict[str, Any]:
        result = self._request("GET", "/protocol/exchange")
        # 必要条件或数据不满足时执行安全处理。
        if not isinstance(result, dict):
            raise MH4HttpError(f"exchange 返回格式错误: {result!r}")
        return result

    # 发送一次移动摇杆控制指令。
    def joystick(
        self,
        move_x: int = 0,
        move_y: int = 0,
        turn_x: int = 0,
        turn_y: int = 0,
    ) -> dict[str, Any]:
        payload = {
            "btn_move": {"x": _clamp_stick(move_x), "y": _clamp_stick(move_y)},
            "btn_turn": {"x": _clamp_stick(turn_x), "y": _clamp_stick(turn_y)},
            # 实机端以毫秒时间戳判断指令是否新鲜；必须每次请求重新生成。
            "timestamp": int(time.time() * 1000),
        }
        result = self._request(
            "POST", "/settings/movement/joystickControl", payload
        )
        return self._require_success(result, "摇杆控制")

    # 将全部摇杆轴归零以停止移动。
    def stop_joystick(self) -> dict[str, Any]:
        return self.joystick()

    # 触发指定编号的机器人动作。
    def movement_action(self, action_id: int) -> dict[str, Any]:
        result = self._request(
            "POST", "/settings/movement/action", {"id": int(action_id)}
        )
        return self._require_success(result, "切换运动状态")

    # 设置或解除机器人软急停。
    def emergency_stop(self, enabled: bool) -> dict[str, Any]:
        result = self._request(
            "POST", "/settings/emergencyStop", {"value": bool(enabled)}
        )
        return self._require_success(result, "软急停")
