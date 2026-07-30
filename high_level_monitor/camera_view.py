"""四相机画面——2×2 网格显示四个 DDS 相机流"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout


class CameraView(QWidget):
    """以 2×2 网格显示四个相机画面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1a1a1a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title = QLabel("  四相机")
        title.setStyleSheet("color: #0af; font: bold 14px; padding: 4px; background: #222;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(2)

        self._labels = []
        for i, name in enumerate(["前 RGB", "前 深度", "后 RGB", "后 深度"]):
            lbl = QLabel("等待...")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumSize(160, 120)
            lbl.setStyleSheet("background-color: #111; color: #555; font: 12px; border: 1px solid #333;")
            row, col = divmod(i, 2)
            grid.addWidget(lbl, row, col)
            self._labels.append(lbl)

        layout.addLayout(grid)

    def update_frame(self, idx, cv_img):
        """用原始分辨率显示画面，不缩放"""
        if idx < 0 or idx >= len(self._labels):
            return
        h, w, ch = cv_img.shape
        qt = QImage(cv_img.data, w, h, ch * w, QImage.Format.Format_BGR888)
        label = self._labels[idx]
        label.setFixedSize(w, h)
        label.setPixmap(QPixmap.fromImage(qt))
