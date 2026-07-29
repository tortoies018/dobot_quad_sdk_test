# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'camera_widget.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_CameraWidget(object):
    def setupUi(self, CameraWidget):
        if not CameraWidget.objectName():
            CameraWidget.setObjectName(u"CameraWidget")
        CameraWidget.setStyleSheet(u"background-color: #2a2a2a; border: 1px solid #444; border-radius: 4px;")
        self.verticalLayout = QVBoxLayout(CameraWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(3, 3, 3, 3)
        self.labelTitle = QLabel(CameraWidget)
        self.labelTitle.setObjectName(u"labelTitle")
        self.labelTitle.setStyleSheet(u"font: bold 12px; color: #0af; padding: 2px; background: transparent; border: none;")

        self.verticalLayout.addWidget(self.labelTitle)

        self.labelFrame = QLabel(CameraWidget)
        self.labelFrame.setObjectName(u"labelFrame")
        self.labelFrame.setAlignment(Qt.AlignCenter)
        self.labelFrame.setMinimumSize(QSize(240, 180))
        self.labelFrame.setStyleSheet(u"background-color: #1a1a1a; color: #555; font: 14px; border: none; padding: 0px;")

        self.verticalLayout.addWidget(self.labelFrame)


        self.retranslateUi(CameraWidget)

        QMetaObject.connectSlotsByName(CameraWidget)
    # setupUi

    def retranslateUi(self, CameraWidget):
        self.labelTitle.setText(QCoreApplication.translate("CameraWidget", u"\u76f8\u673a", None))
        self.labelFrame.setText(QCoreApplication.translate("CameraWidget", u"\u7b49\u5f85\u6570\u636e...", None))
        pass
    # retranslateUi

