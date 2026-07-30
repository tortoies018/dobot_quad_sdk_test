"""标定工作线程——支持 DDS 机器狗相机 和 OpenCV 本地相机两种信号源"""

import time
import numpy as np
import cv2

from PySide6.QtCore import QThread, Signal

import dds_middleware_python as dds

import checkerboard_utils as cb


DDS_TOPICS = {
    "前置 RGB": "rt/camera/camera2/image_compressed",
    "后置 RGB": "rt/camera/camera3/image_compressed",
}


class CalibWorker(QThread):
    """后台线程：获取相机画面、检测棋盘格、执行标定"""

    frame_ready = Signal(np.ndarray)
    corners_detected = Signal(np.ndarray, int, int)
    calib_done = Signal(float, np.ndarray, np.ndarray)
    log_msg = Signal(str)

    # 可供选择的信号源
    SOURCES = ["DDS 前置 RGB", "DDS 后置 RGB", "OpenCV 相机 0", "OpenCV 相机 1"]

    def __init__(self, config_path="config/dds_config.yaml", parent=None):
        super().__init__(parent)
        self._source = "DDS 前置 RGB"
        self._config_path = config_path
        self._running = True
        self._capture_enabled = False
        self._mw = None
        self._cap = None

        # 标定数据
        self._obj_points = []
        self._img_points = []
        self._image_size = None
        self._frame_count = 0

        cfg = cb.get_calib_config()
        self._pattern_size = cfg["pattern_size"]
        self._square_size = cfg["square_size_mm"]

    def set_source(self, name: str):
        """切换信号源"""
        self._source = name
        self.log_msg.emit(f"信号源切换为: {name}")

    def capture_frame(self):
        """标记下一帧用于捕获"""
        self._capture_enabled = True

    def reset(self):
        self._obj_points.clear()
        self._img_points.clear()
        self._image_size = None
        self._frame_count = 0
        self.log_msg.emit("已重置标定数据")

    # ─── 线程主循环 ──────────────────────────────────

    def run(self):
        if self._source.startswith("DDS"):
            self._run_dds()
        else:
            self._run_opencv()

    def _run_dds(self):
        """DDS 信号源：订阅机器狗相机话题"""
        try:
            self._mw = dds.PyDDSMiddleware(self._config_path)
        except Exception as e:
            self.log_msg.emit(f"DDS 初始化失败: {e}")
            self.log_msg.emit("提示: 请在组合框切换为 OpenCV 相机")
            return

        key = self._source.replace("DDS ", "")
        topic = DDS_TOPICS.get(key)
        if not topic:
            self.log_msg.emit(f"未知 DDS 话题: {key}")
            return

        def cb(data):
            try:
                arr = np.array(data.data(), dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    self._process_frame(img)
            except Exception:
                pass

        try:
            self._mw.subscribeCompressedImage(topic, cb)
            self.log_msg.emit(f"已订阅 {topic}")
        except Exception as e:
            self.log_msg.emit(f"DDS 订阅失败: {e}")
            self.log_msg.emit("提示: 请切换为 OpenCV 相机")
            return

        while self._running:
            time.sleep(1)

    def _run_opencv(self):
        """OpenCV 信号源：打开本地 USB 相机"""
        idx = 0 if "0" in self._source else 1
        self._cap = cv2.VideoCapture(idx)
        if not self._cap.isOpened():
            self.log_msg.emit(f"无法打开 OpenCV 相机 {idx}")
            return
        self.log_msg.emit(f"OpenCV 相机 {idx} 已打开")

        while self._running:
            ret, img = self._cap.read()
            if ret:
                self._process_frame(img)
            time.sleep(0.03)

    # ─── 帧处理（DDS 和 OpenCV 共用） ────────────────

    def _process_frame(self, img):
        """对帧进行棋盘格检测并发送到 UI"""
        if self._image_size is None:
            self._image_size = (img.shape[1], img.shape[0])
            self.log_msg.emit(f"图像尺寸: {self._image_size[0]}×{self._image_size[1]}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(
            gray, self._pattern_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        detect = img.copy()

        if found:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            cv2.drawChessboardCorners(detect, self._pattern_size, corners, found)
            self.corners_detected.emit(corners, self._pattern_size[0], self._pattern_size[1])

            if self._capture_enabled:
                self._capture_enabled = False
                objp = np.zeros((self._pattern_size[0] * self._pattern_size[1], 3), np.float32)
                objp[:, :2] = np.mgrid[0:self._pattern_size[0],
                                        0:self._pattern_size[1]].T.reshape(-1, 2)
                objp *= self._square_size

                self._obj_points.append(objp)
                self._img_points.append(corners.reshape(-1, 2))
                self._frame_count += 1
                self.log_msg.emit(f"已捕获第 {self._frame_count} 帧")

        self.frame_ready.emit(detect)

    # ─── 停止 ────────────────────────────────────────

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()

    # ─── 标定 ────────────────────────────────────────

    def calibrate(self):
        if self._frame_count < 3:
            self.log_msg.emit("至少需要 3 帧才能标定")
            return

        self.log_msg.emit(f"正在标定 ({self._frame_count} 帧)...")

        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self._obj_points, self._img_points,
            self._image_size, None, None
        )

        self.calib_done.emit(ret, mtx, dist)

        import json
        from pathlib import Path
        result = {
            "source": self._source,
            "image_size": list(self._image_size),
            "pattern_size": list(self._pattern_size),
            "square_size_mm": self._square_size,
            "num_frames": self._frame_count,
            "reprojection_error": float(ret),
            "camera_matrix": mtx.tolist(),
            "distortion_coefficients": dist.tolist(),
        }
        out = Path(__file__).resolve().parent / "calibration_result.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        self.log_msg.emit(f"结果已保存: {out}")
