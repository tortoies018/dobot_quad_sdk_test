from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget

from generated.ui_camera_widget import Ui_CameraWidget


class CameraWidget(QWidget, Ui_CameraWidget):
    def __init__(self, title, topic, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.labelTitle.setText(f"[{title}]")
        self.setToolTip(topic)

    def update_frame(self, cv_img):
        h, w, ch = cv_img.shape
        qt_img = QImage(cv_img.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(qt_img)
        scaled = pix.scaled(
            self.labelFrame.width(),
            self.labelFrame.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.labelFrame.setPixmap(scaled)
