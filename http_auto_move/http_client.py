"""MH4 HTTP 接口的轻量客户端。

只使用 Python 标准库，避免为了几个 JSON 接口额外引入 requests 依赖。
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


STICK_MIN = -32768
STICK_MAX = 32767


class MH4HttpError(RuntimeError):
    """HTTP、JSON 或接口业务状态异常。"""


def _clamp_stick(value: int) -> int:
    return max(STICK_MIN, min(STICK_MAX, int(value)))


class MH4HttpClient:
    """文档中 22000 MH4 控制接口的同步客户端。"""

    def __init__(self, address: str, timeout: float = 1.5):
        self.control_base = self._normalise_address(address)
        self.timeout = max(0.1, float(timeout))

    @staticmethod
    def _normalise_address(address: str) -> str:
        value = address.strip()
        if not value:
            raise ValueError("HTTP 地址不能为空")
        if "://" not in value:
            value = f"http://{value}"
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("HTTP 地址只支持 http:// 或 https://")
        if not parsed.hostname:
            raise ValueError("HTTP 地址中缺少主机名或 IP")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("请输入 IP/主机和端口，不要附加接口路径")

        host = parsed.hostname
        if ":" in host:  # IPv6 URL 需要方括号
            host = f"[{host}]"
        control_port = parsed.port or 22000
        return f"{parsed.scheme}://{host}:{control_port}"

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(
            f"{self.control_base}{path}", data=body, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            raise MH4HttpError(f"HTTP {exc.code} {method} {path}{suffix}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise MH4HttpError(f"请求失败 {method} {path}: {reason}") from exc

        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            preview = raw[:160].decode("utf-8", errors="replace")
            raise MH4HttpError(f"接口返回的不是有效 JSON: {preview!r}") from exc

    @staticmethod
    def _require_success(result: Any, operation: str) -> Any:
        if not isinstance(result, dict):
            raise MH4HttpError(f"{operation} 返回格式错误: {result!r}")
        if result.get("status") is not True:
            raise MH4HttpError(f"{operation} 被控制器拒绝: {result!r}")
        return result

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

    def connection_state(self) -> dict[str, Any]:
        result = self._request("GET", "/connection/state")
        if not isinstance(result, dict):
            raise MH4HttpError(f"连接状态返回格式错误: {result!r}")
        return result

    def connection_type(self) -> str:
        result = self._request("GET", "/connection/type")
        if not isinstance(result, dict) or result.get("value") not in ("AP", "Station"):
            raise MH4HttpError(f"连接方式返回格式错误: {result!r}")
        return str(result["value"])

    def exchange(self) -> dict[str, Any]:
        result = self._request("GET", "/protocol/exchange")
        if not isinstance(result, dict):
            raise MH4HttpError(f"exchange 返回格式错误: {result!r}")
        return result

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

    def stop_joystick(self) -> dict[str, Any]:
        return self.joystick()

    def movement_action(self, action_id: int) -> dict[str, Any]:
        result = self._request(
            "POST", "/settings/movement/action", {"id": int(action_id)}
        )
        return self._require_success(result, "切换运动状态")

    def emergency_stop(self, enabled: bool) -> dict[str, Any]:
        result = self._request(
            "POST", "/settings/emergencyStop", {"value": bool(enabled)}
        )
        return self._require_success(result, "软急停")
