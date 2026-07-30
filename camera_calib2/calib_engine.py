"""标定引擎——管理每台相机的角点采集和标定计算"""

import json
from pathlib import Path

import numpy as np
import cv2


class CalibEngine:
    """单台相机的标定数据采集和计算"""

    def __init__(self, camera_name: str, pattern_size=(9, 6), square_mm=25):
        self.camera_name = camera_name
        self.pattern_size = pattern_size
        self.square_mm = square_mm

        self._obj_points = []   # 世界坐标系棋盘格点
        self._img_points = []   # 图像角点
        self._image_size = None
        self._frame_count = 0

    def detect_and_capture(self, img, capture=False):
        """检测棋盘格，如需捕获则保存角点。返回画了检测结果的图。"""
        if self._image_size is None:
            self._image_size = (img.shape[1], img.shape[0])

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(
            gray, self.pattern_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        result = img.copy()
        detected = False

        if found:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            cv2.drawChessboardCorners(result, self.pattern_size, corners, found)
            detected = True

            if capture:
                objp = np.zeros((self.pattern_size[0] * self.pattern_size[1], 3), np.float32)
                objp[:, :2] = np.mgrid[0:self.pattern_size[0],
                                        0:self.pattern_size[1]].T.reshape(-1, 2)
                objp *= self.square_mm
                self._obj_points.append(objp)
                self._img_points.append(corners.reshape(-1, 2))
                self._frame_count += 1

        return result, detected, corners if found else None

    def calibrate(self):
        """执行标定，返回 (error, camera_matrix, distortion)"""
        if self._frame_count < 3:
            return None

        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self._obj_points, self._img_points, self._image_size, None, None
        )
        return ret, mtx, dist

    def save_result(self, error, mtx, dist):
        """保存标定结果到 JSON"""
        result = {
            "camera": self.camera_name,
            "image_size": list(self._image_size),
            "pattern_size": list(self.pattern_size),
            "square_size_mm": self.square_mm,
            "num_frames": self._frame_count,
            "reprojection_error": float(error),
            "camera_matrix": mtx.tolist(),
            "distortion_coefficients": dist.tolist(),
        }
        out = Path(__file__).resolve().parent / f"calib_{self.camera_name}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return out

    def reset(self):
        self._obj_points.clear()
        self._img_points.clear()
        self._image_size = None
        self._frame_count = 0

    @property
    def frame_count(self):
        return self._frame_count

    @property
    def ready_to_calibrate(self):
        return self._frame_count >= 3
