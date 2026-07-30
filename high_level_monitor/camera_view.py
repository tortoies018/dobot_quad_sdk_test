"""相机画面控件——显示 DDS 相机图像"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox


class CameraView(QWidget):
    """显示 DDS 相机画面的面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1a1a1a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标题 + 切换栏
        bar = QHBoxLayout()
        title = QLabel("  相机画面")
        title.setStyleSheet("color: #0af; font: bold 14px; padding: 6px; background: #222;")
        bar.addWidget(title)

        self.cam_switch = QComboBox()
        self.cam_switch.addItems(["前置 RGB", "后置 RGB"])
        self.cam_switch.setStyleSheet("""
            QComboBox { background: #333; color: #fff; padding: 4px 8px;
                        border: 1px solid #555; border-radius: 4px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #333; color: #fff;
                                          selection-background-color: #0af; }
        """)
        bar.addWidget(self.cam_switch)
        bar.addStretch()
        layout.addLayout(bar)

        # 图像显示
        self.label_frame = QLabel("等待相机数据...")
        self.label_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_frame.setStyleSheet(
            "background-color: #111; color: #555; font: 16px; border: none;"
        )
        layout.addWidget(self.label_frame, 1)

    def update_frame(self, cv_img):
        """用 OpenCV BGR 图像更新画面"""
        h, w, ch = cv_img.shape
        qt_img = QImage(cv_img.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(qt_img)

        scaled = pix.scaled(
            self.label_frame.width(),
            self.label_frame.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.label_frame.setPixmap(scaled)
