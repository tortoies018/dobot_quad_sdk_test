"""DDS 双相机订阅线程（帧率限制，避免 UI 卡死）"""

import time
import numpy as np
import cv2

from PySide6.QtCore import QThread, Signal

import dds_middleware_python as dds


FRAME_INTERVAL = 0.15  # 每 150ms 发送一帧（~7fps，留足检测时间）


class DualCamWorker(QThread):
    """同时订阅前后相机，限制帧率后发送到主线程"""

    front_ready = Signal(np.ndarray)
    rear_ready = Signal(np.ndarray)
    log_msg = Signal(str)

    def __init__(self, config_path="config/dds_config.yaml", parent=None):
        super().__init__(parent)
        self._config = config_path
        self._mw = None
        self._running = True
        self._last_front = 0.0
        self._last_rear = 0.0

    def _should_emit(self, side):
        """限制每侧相机最多 FRAME_INTERVAL 秒发一帧"""
        now = time.monotonic()
        if side == "front":
            if now - self._last_front < FRAME_INTERVAL:
                return False
            self._last_front = now
        else:
            if now - self._last_rear < FRAME_INTERVAL:
                return False
            self._last_rear = now
        return True

    def run(self):
        try:
            self._mw = dds.PyDDSMiddleware(self._config)
        except Exception as e:
            self.log_msg.emit(f"DDS 初始化失败: {e}")
            return

        def make_cb(side):
            def cb(data):
                if not self._should_emit(side):
                    return
                try:
                    arr = np.array(data.data(), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        if side == "front":
                            self.front_ready.emit(img)
                        else:
                            self.rear_ready.emit(img)
                except Exception:
                    pass
            return cb

        try:
            self._mw.subscribeCompressedImage(
                "rt/camera/camera2/image_compressed", make_cb("front")
            )
            self.log_msg.emit("已订阅 前置 RGB  camera2")
        except Exception as e:
            self.log_msg.emit(f"订阅失败 camera2: {e}")

        try:
            self._mw.subscribeCompressedImage(
                "rt/camera/camera3/image_compressed", make_cb("rear")
            )
            self.log_msg.emit("已订阅 后置 RGB  camera3")
        except Exception as e:
            self.log_msg.emit(f"订阅失败 camera3: {e}")

        while self._running:
            time.sleep(1)

    def stop(self):
        self._running = False
