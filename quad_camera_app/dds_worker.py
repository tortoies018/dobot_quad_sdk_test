import time
from pathlib import Path

import numpy as np
import cv2

from PySide6.QtCore import QThread, Signal

import dds_middleware_python as dds


CAMERA_CONFIGS = [
    {"name": "前 RGB", "topic": "rt/camera/camera2/image_compressed", "stream": "rgb"},
    {"name": "前 深度", "topic": "rt/camera/camera2/image_depth", "stream": "depth"},
    {"name": "后 RGB", "topic": "rt/camera/camera3/image_compressed", "stream": "rgb"},
    {"name": "后 深度", "topic": "rt/camera/camera3/image_depth", "stream": "depth"},
]

QOS_BEST = {
    "reliability": "best_effort",
    "history_kind": "keep_last",
    "history_depth": 5,
    "durability": "volatile",
}


class DDSSubscriber(QThread):
    frame_ready = Signal(int, np.ndarray)
    imu_ready = Signal(object, object, object, object)
    battery_ready = Signal(int)
    motor_ready = Signal(int, int, float, float, float, int)
    voice_ready = Signal(int, float)
    log_msg = Signal(str)

    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self._config_path = config_path
        self._mw = None
        self._running = True

    def run(self):
        if not Path(self._config_path).exists():
            self.log_msg.emit(f"Config not found: {self._config_path}")
            return

        try:
            self._mw = dds.PyDDSMiddleware(self._config_path)
            self.log_msg.emit(f"DDS middleware initialized (v{dds.__version__ if hasattr(dds, '__version__') else '?'})")
        except Exception as e:
            self.log_msg.emit(f"Middleware init failed: {e}")
            return

        subs_ok = 0
        for i, cfg in enumerate(CAMERA_CONFIGS):
            try:
                if cfg["stream"] == "rgb":
                    self._mw.subscribeCompressedImage(
                        cfg["topic"], self._make_rgb_cb(i)
                    )
                else:
                    self._mw.subscribeImage(
                        cfg["topic"], self._make_depth_cb(i), QOS_BEST
                    )
                subs_ok += 1
            except Exception as e:
                self.log_msg.emit(f"Sub fail {cfg['topic']}: {e}")

        try:
            self._mw.subscribeLowerState("rt/lower/state", self._lower_state_cb)
            subs_ok += 1
        except Exception as e:
            self.log_msg.emit(f"Sub fail rt/lower/state: {e}")

        try:
            self._mw.subscribeVoiceState("rt/voice/state", self._voice_cb, QOS_BEST)
            subs_ok += 1
        except Exception as e:
            self.log_msg.emit(f"Sub fail rt/voice/state: {e}")

        self.log_msg.emit(f"Subscribed {subs_ok} topics, waiting for data...")

    def stop(self):
        self._running = False

    # --- Callback helpers ---

    def _make_rgb_cb(self, idx):
        def cb(data):
            try:
                arr = np.array(data.data(), dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    self.frame_ready.emit(idx, img)
            except Exception:
                pass
        return cb

    def _make_depth_cb(self, idx):
        def cb(msg):
            try:
                if "16UC1" not in msg.encoding():
                    return
                raw = np.array(msg.data(), dtype=np.uint8)
                depth = raw.view(np.uint16).reshape((msg.height(), msg.width()))
                vis = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                color = cv2.applyColorMap(vis, cv2.COLORMAP_JET)
                self.frame_ready.emit(idx, color)
            except Exception:
                pass
        return cb

    def _lower_state_cb(self, state):
        try:
            imu = state.imu_state()
            self.imu_ready.emit(
                list(imu.quaternion()),
                list(imu.gyroscope()),
                list(imu.accelerometer()),
                list(imu.rpy()),
            )
        except Exception:
            pass

        try:
            bms = state.bms_state()
            self.battery_ready.emit(bms.battery_level())
        except Exception:
            pass

        try:
            motors = state.motor_state()
            for i in range(16):
                m = motors[i]
                self.motor_ready.emit(i, m.mode(), m.q(), m.dq(), m.tau_est(), m.motor_temp())
        except Exception:
            pass

    def _voice_cb(self, msg):
        try:
            self.voice_ready.emit(len(msg.data_()), msg.angle_())
        except Exception:
            pass
