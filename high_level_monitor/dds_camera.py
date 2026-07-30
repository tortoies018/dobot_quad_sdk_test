"""DDS 相机订阅线程——通过 CycloneDDS 获取 RGB 相机画面"""

import time
import numpy as np
import cv2

from PySide6.QtCore import QThread, Signal

import dds_middleware_python as dds


CAMERA_TOPICS = [
    ("前 RGB", "rt/camera/camera2/image_compressed"),
    ("后 RGB", "rt/camera/camera3/image_compressed"),
]


class DDSCamera(QThread):
    """后台线程：订阅 DDS 相机话题，发送 OpenCV 图像帧"""

    frame_ready = Signal(np.ndarray)
    camera_switched = Signal(str)
    log_msg = Signal(str)

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self._camera_index = camera_index  # 0=前, 1=后
        self._running = True
        self._mw = None

    def switch(self, index: int):
        """切换相机 0=前, 1=后"""
        self._camera_index = index
        self.camera_switched.emit(CAMERA_TOPICS[index][0])

    def run(self):
        try:
            self._mw = dds.PyDDSMiddleware(0)
            self.log_msg.emit("DDS 相机中间件已初始化")
        except Exception as e:
            self.log_msg.emit(f"DDS 初始化失败: {e}")
            return

        name, topic = CAMERA_TOPICS[self._camera_index]

        def cb(data):
            try:
                arr = np.array(data.data(), dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    self.frame_ready.emit(img)
            except Exception:
                pass

        try:
            self._mw.subscribeCompressedImage(topic, cb)
            self.log_msg.emit(f"已订阅 {name}  {topic}")
        except Exception as e:
            self.log_msg.emit(f"订阅失败 {topic}: {e}")
            return

        while self._running:
            time.sleep(1)

    def stop(self):
        self._running = False
