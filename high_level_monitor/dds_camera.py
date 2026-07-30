"""DDS 四相机订阅线程——RGB + 深度，前后各二"""

import time
import numpy as np
import cv2

from PySide6.QtCore import QThread, Signal

import dds_middleware_python as dds


# 四个相机流：[名称, 话题, 类型]
CAMERA_STREAMS = [
    ("前 RGB",       "rt/camera/camera2/image_compressed", "rgb"),
    ("前 深度",      "rt/camera/camera2/image_depth",      "depth"),
    ("后 RGB",       "rt/camera/camera3/image_compressed", "rgb"),
    ("后 深度",      "rt/camera/camera3/image_depth",      "depth"),
]

QOS_BEST = {"reliability": "best_effort", "history_kind": "keep_last",
            "history_depth": 1, "durability": "volatile"}


class FourCamWorker(QThread):
    """同时订阅四个相机流，限帧发送"""

    frame_ready = Signal(int, np.ndarray)
    log_msg = Signal(str)

    def __init__(self, config_path="config/dds_config.yaml", parent=None):
        super().__init__(parent)
        self._config = config_path
        self._running = True
        self._last = [0.0, 0.0, 0.0, 0.0]
        self._interval = 0.1

    def run(self):
        try:
            mw = dds.PyDDSMiddleware(self._config)
        except Exception as e:
            self.log_msg.emit(f"DDS 初始化失败: {e}")
            return

        for idx, (name, topic, stype) in enumerate(CAMERA_STREAMS):
            def make_cb(i, t):
                def cb(data):
                    now = time.monotonic()
                    if now - self._last[i] < self._interval:
                        return
                    self._last[i] = now
                    try:
                        if t == "rgb":
                            arr = np.frombuffer(bytes(data.data()), dtype=np.uint8)
                            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                            if img is not None:
                                self.frame_ready.emit(i, img)
                        else:
                            if "16UC1" not in data.encoding():
                                return
                            raw = np.frombuffer(bytes(data.data()), dtype=np.uint8)
                            depth = raw.view(np.uint16).reshape((data.height(), data.width()))
                            vis = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                            color = cv2.applyColorMap(vis, cv2.COLORMAP_JET)
                            self.frame_ready.emit(i, color)
                    except Exception:
                        pass
                return cb

            try:
                if stype == "rgb":
                    mw.subscribeCompressedImage(topic, make_cb(idx, "rgb"))
                else:
                    mw.subscribeImage(topic, make_cb(idx, "depth"), QOS_BEST)
                self.log_msg.emit(f"已订阅 {name}  {topic}")
            except Exception as e:
                self.log_msg.emit(f"订阅失败 {topic}: {e}")

        while self._running:
            time.sleep(1)

    def stop(self):
        self._running = False
